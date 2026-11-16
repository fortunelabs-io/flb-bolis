/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file bol_sender.c
 * @brief The sending loop of one pass (decision records
 *        2026-11-13-the-sending-loop-of-a-pass.md and
 *        2026-11-16-the-mapping-of-a-message-to-its-frames.md).
 */

#include "bol_sender.h"

/**
 * @brief Reports whether every member of a port holds a function.
 *
 * @param[in] port  The port to check.
 *
 * @return True when the loop can call every member.
 */
static bool bol_sender_port_is_whole(const bol_sender_port_t *port)
{
    return (port->send != NULL) && (port->await_callback != NULL) &&
           (port->wait_ms != NULL) && (port->now_ms != NULL) && (port->progress != NULL);
}

/**
 * @brief Sends one frame, with the attempts that a no-memory error takes.
 *
 * @param[in]     port         The radio of this pass.
 * @param[in]     frame        The bytes to send.
 * @param[in]     frame_bytes  The bytes of that frame.
 * @param[in,out] counters     The counters of this pass.
 *
 * @return True when the frame reached the air.
 */
static bool bol_sender_send_one(const bol_sender_port_t *port, const uint8_t *frame,
                                size_t frame_bytes, bol_sender_counters_t *counters)
{
    bool is_sent = false;
    bool is_done = false;
    uint32_t attempt = 0U;

    while (!is_done) {
        esp_err_t ret;

        attempt++;
        ret = port->send(port->context, frame, frame_bytes);

        if (ret == ESP_OK) {
            bool is_ok = false;
            uint32_t microseconds = 0U;
            const esp_err_t callback_ret = port->await_callback(port->context, &is_ok,
                                                                &microseconds);

            if (callback_ret == ESP_OK) {
                bol_stats_count_callback(counters, is_ok, microseconds);
            }

            counters->packets_sent++;
            is_sent = true;
            is_done = true;
        } else if ((ret == port->no_mem_code) && (attempt < BOL_SENDER_ATTEMPTS)) {
            counters->no_mem_events++;
            port->wait_ms(port->context, BOL_SENDER_NO_MEM_WAIT_MS);
        } else {
            if (ret == port->no_mem_code) {
                counters->no_mem_events++;
            }

            // The packet reached neither the air nor the receiver, so the pass
            // moves to the next packet rather than stopping on one error.
            bol_stats_count_send_error(counters, ret);
            counters->dropped_packets++;
            is_done = true;
        }
    }

    return is_sent;
}

/**
 * @brief Writes a progress reply when the interval of one has passed.
 *
 * @param[in]     port              The port that writes the reply.
 * @param[in]     counters          The counters of this pass.
 * @param[in,out] last_progress_ms  The time of the last line of this pass.
 */
static void bol_sender_report_progress(const bol_sender_port_t *port,
                                       const bol_sender_counters_t *counters,
                                       uint32_t *last_progress_ms)
{
    const uint32_t now_ms = port->now_ms(port->context);

    // Both values are unsigned, so the difference states the elapsed time even
    // when the counter of the node wraps.
    if ((now_ms - *last_progress_ms) >= BOL_SENDER_PROGRESS_MS) {
        port->progress(port->context, counters->packets_sent);
        *last_progress_ms = now_ms;
    }
}

/**
 * @brief Sends one message and counts it when every frame of it reached the air.
 *
 * @param[in]     port              The radio and the clock of this pass.
 * @param[in]     pass              The pass that holds this message.
 * @param[in]     message_id        The message to send.
 * @param[in]     packets           The frames of one message.
 * @param[in,out] counters          The counters of this pass.
 * @param[in,out] last_progress_ms  The time of the last line of this pass.
 *
 * @retval ESP_OK  The message reached the end of its frames.
 * @retval Other   The code that the sizing or the encoder returned.
 */
static esp_err_t bol_sender_send_message(const bol_sender_port_t *port,
                                         const bol_sender_pass_t *pass, uint32_t message_id,
                                         uint32_t packets, bol_sender_counters_t *counters,
                                         uint32_t *last_progress_ms)
{
    esp_err_t ret = ESP_OK;
    uint32_t fragment = 0U;
    uint32_t sent_of_message = 0U;

    while ((ret == ESP_OK) && (fragment < packets)) {
        uint32_t frame_bytes = 0U;

        ret = bol_sender_frame_bytes(pass->payload_bytes, pass->payload_limit_bytes, fragment,
                                     &frame_bytes);

        if ((ret == ESP_OK) && ((size_t)frame_bytes > pass->frame_capacity_bytes)) {
            ret = ESP_ERR_INVALID_SIZE;
        }

        if (ret == ESP_OK) {
            const bol_frame_header_t header = {
                .run_id = pass->run_id,
                .cell_id = pass->cell_id,
                .pass = pass->pass,
                .message_id = message_id,
                .fragment_index = (uint8_t)fragment,
                .fragment_count = (uint8_t)packets
            };

            ret = bol_frame_encode(&header, pass->frame, (size_t)frame_bytes);
        }

        if (ret == ESP_OK) {
            if (bol_sender_send_one(port, pass->frame, (size_t)frame_bytes, counters)) {
                sent_of_message++;
            }

            bol_sender_report_progress(port, counters, last_progress_ms);
            fragment++;
        }
    }

    if ((ret == ESP_OK) && (sent_of_message == packets)) {
        counters->messages_sent++;
    }

    return ret;
}

esp_err_t bol_sender_frame_bytes(uint32_t payload_bytes, uint32_t payload_limit_bytes,
                                 uint32_t fragment_index, uint32_t *out_frame_bytes)
{
    esp_err_t ret = ESP_OK;
    const uint32_t packets = bol_stats_packets_per_message(payload_bytes, payload_limit_bytes);

    if (out_frame_bytes == NULL) {
        ret = ESP_ERR_INVALID_ARG;
    } else if (packets == 0U) {
        ret = ESP_ERR_INVALID_ARG;
    } else if (fragment_index >= packets) {
        ret = ESP_ERR_INVALID_ARG;
    } else {
        // The frames divide the message as evenly as they can, so the first
        // remainder frames each hold one byte more than the rest.
        const uint32_t base_bytes = payload_bytes / packets;
        const uint32_t remainder = payload_bytes % packets;

        if (fragment_index < remainder) {
            *out_frame_bytes = base_bytes + 1U;
        } else {
            *out_frame_bytes = base_bytes;
        }
    }

    return ret;
}

esp_err_t bol_sender_run_pass(const bol_sender_port_t *port, const bol_sender_pass_t *pass,
                              bol_sender_counters_t *counters)
{
    esp_err_t ret = ESP_OK;

    if ((port == NULL) || (pass == NULL) || (counters == NULL)) {
        ret = ESP_ERR_INVALID_ARG;
    } else if (!bol_sender_port_is_whole(port)) {
        ret = ESP_ERR_INVALID_ARG;
    } else if (pass->frame == NULL) {
        ret = ESP_ERR_INVALID_ARG;
    } else {
        const uint32_t packets = bol_stats_packets_per_message(pass->payload_bytes,
                                                               pass->payload_limit_bytes);

        if (packets == 0U) {
            ret = ESP_ERR_INVALID_ARG;
        } else if (packets > (uint32_t)UINT8_MAX) {
            // The fragment count field holds one byte (decision record
            // 2026-11-12-frame-header-encoding.md).
            ret = ESP_ERR_INVALID_ARG;
        } else {
            const uint32_t messages = bol_stats_messages_that_fit(pass->frames, packets);
            uint32_t message_id = 0U;
            uint32_t last_progress_ms;

            bol_stats_reset(counters);
            last_progress_ms = port->now_ms(port->context);

            while ((ret == ESP_OK) && (message_id < messages)) {
                ret = bol_sender_send_message(port, pass, message_id, packets, counters,
                                              &last_progress_ms);
                message_id++;
            }
        }
    }

    return ret;
}
