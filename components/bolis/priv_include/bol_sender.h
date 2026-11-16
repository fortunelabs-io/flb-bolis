/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file bol_sender.h
 * @brief The sending loop of one pass (decision records
 *        2026-11-13-the-sending-loop-of-a-pass.md and
 *        2026-11-16-the-mapping-of-a-message-to-its-frames.md).
 *
 * The loop sends whole messages only, and it sends the next packet after the
 * callback of the previous packet returns. It reaches the radio and the clock
 * through a port of function pointers, so this module needs no driver header
 * and the reader tests drive it on the host.
 */

#ifndef BOL_SENDER_H
#define BOL_SENDER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#include "bol_frame.h"
#include "bol_stats.h"

#ifdef __cplusplus
extern "C" {
#endif

/** @brief The milliseconds that the sender waits after a no-memory error. */
#define BOL_SENDER_NO_MEM_WAIT_MS 10U

/** @brief The attempts that one packet takes before the pass moves past it. */
#define BOL_SENDER_ATTEMPTS 10U

/** @brief The milliseconds between two progress replies of one pass. */
#define BOL_SENDER_PROGRESS_MS 1000U

/**
 * @brief The radio and the clock that one pass reaches.
 *
 * Every member holds a function that the caller supplies. The firmware passes
 * the ESP-NOW calls and the node clock. A test passes its own, so the loop
 * runs with no radio.
 */
typedef struct {
    /*! Puts one frame on the air. Returns the code of the driver. */
    esp_err_t (*send)(void *context, const uint8_t *frame, size_t frame_bytes);
    /*! Waits for the send callback and states its result and its time. */
    esp_err_t (*await_callback)(void *context, bool *out_is_ok, uint32_t *out_microseconds);
    /*! Waits the stated milliseconds. */
    void (*wait_ms)(void *context, uint32_t milliseconds);
    /*! Returns a millisecond counter that rises. */
    uint32_t (*now_ms)(void *context);
    /*! Writes a progress reply that states the frames sent so far. */
    void (*progress)(void *context, uint32_t frames_sent);
    /*! The code that the driver returns when it holds no buffer. */
    esp_err_t no_mem_code;
    /*! The value that every member above takes as its first argument. */
    void *context;
} bol_sender_port_t;

/** @brief The pass that the loop sends. */
typedef struct {
    uint32_t run_id;               /*!< The run that each header states. */
    uint16_t cell_id;              /*!< The cell that each header states. */
    bol_pass_t pass;               /*!< The pass that each header states. */
    uint32_t frames;               /*!< The frame budget, in packets. */
    uint32_t payload_bytes;        /*!< The payload of one message, in bytes. */
    uint32_t payload_limit_bytes;  /*!< The packet payload limit L, in bytes. */
    uint8_t *frame;                /*!< The buffer that the loop fills and sends. */
    size_t frame_capacity_bytes;   /*!< The size of that buffer, in bytes. */
} bol_sender_pass_t;

/**
 * @brief Returns the bytes of one frame of a message.
 *
 * A message of p bytes maps to n(p) frames, and those frames divide p as
 * evenly as they can. With b as p divided by n(p) and r as the remainder, the
 * first r frames hold b plus 1 bytes and the rest hold b bytes. The count
 * holds the whole frame, which is the header and the fill after it.
 *
 * @param[in]  payload_bytes        The payload of one message, in bytes.
 * @param[in]  payload_limit_bytes  The packet payload limit L, 1 or more.
 * @param[in]  fragment_index       The fragment, counting from 0.
 * @param[out] out_frame_bytes      The bytes of that frame.
 *
 * @retval ESP_OK               out_frame_bytes holds the count.
 * @retval ESP_ERR_INVALID_ARG  The pointer is NULL, an argument is 0, or the
 *                              fragment sits at or above the frames of the
 *                              message.
 */
esp_err_t bol_sender_frame_bytes(uint32_t payload_bytes, uint32_t payload_limit_bytes,
                                 uint32_t fragment_index, uint32_t *out_frame_bytes);

/**
 * @brief Sends one pass and fills the counters of that pass.
 *
 * Clears the counters, then sends whole messages while the packets of the
 * next message fit the remaining budget. A send that returns the no-memory
 * code counts one event, waits BOL_SENDER_NO_MEM_WAIT_MS, and repeats, for at
 * most BOL_SENDER_ATTEMPTS attempts of one packet. After the last attempt the
 * loop counts the code and moves to the next packet.
 *
 * `messages_sent` counts the messages whose every frame reached the air.
 * `packets_sent` counts the frames that reached it, so a `go` reply states
 * `packets_sent` as its `frames_sent`.
 *
 * The loop calls the progress member between two frames, and never between a
 * send and its callback, so a console write stays outside the window that
 * `send_to_callback_us_histogram` measures.
 *
 * @param[in]  port      The radio and the clock of this pass.
 * @param[in]  pass      The pass to send.
 * @param[out] counters  The counters of this pass.
 *
 * @retval ESP_OK                 The pass reached the end of its budget.
 * @retval ESP_ERR_INVALID_ARG    A pointer is NULL, a member of the port is
 *                                NULL, or the payload of the message takes
 *                                more frames than one header byte states.
 * @retval ESP_ERR_INVALID_SIZE   A frame of this message does not fit the
 *                                buffer that the caller supplied.
 * @retval Other                  The code that the frame encoder returned.
 */
esp_err_t bol_sender_run_pass(const bol_sender_port_t *port, const bol_sender_pass_t *pass,
                              bol_sender_counters_t *counters);

#ifdef __cplusplus
}
#endif

#endif /* BOL_SENDER_H */
