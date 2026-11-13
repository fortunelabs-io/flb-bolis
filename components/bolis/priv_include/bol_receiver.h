/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file bol_receiver.h
 * @brief The receive callback, its queue, and the task that drains it
 *        (decision record 2026-11-13-the-receiving-loop-of-a-pass.md).
 *
 * The receive callback runs in the WiFi task, so it copies the header, the
 * length, and the strength of a packet to a queue and returns (thinkbook
 * section 7). A lower-priority task checks the header and the fill and
 * updates the counters.
 *
 * A packet that arrives when the queue is full raises `dropped_packets`.
 * That counter states that the node did not keep up, and the host reads it
 * apart from a frame that the link lost.
 */

#ifndef BOL_RECEIVER_H
#define BOL_RECEIVER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#include "bol_frame.h"
#include "bol_rxstats.h"

#ifdef __cplusplus
extern "C" {
#endif

/** @brief The entries that the queue behind the callback holds. */
#define BOL_RECEIVER_QUEUE_ENTRIES 32U

/**
 * @brief Starts the receive callback and the task that drains its queue.
 *
 * @pre ESP-NOW is initialized.
 * @note Call once, from a task.
 *
 * @retval ESP_OK                 The callback and the task run.
 * @retval ESP_ERR_INVALID_STATE  The task already runs.
 * @retval ESP_ERR_NO_MEM         The task did not start.
 * @retval Other                  The code that the failing ESP-IDF call returned.
 */
esp_err_t bol_receiver_start(void);

/**
 * @brief Arms the receiver for one pass and clears its counters.
 *
 * A packet of another run, another cell, or another pass counts as a
 * foreign packet, so the receiver takes all three before the first frame
 * arrives.
 *
 * @param[in] run_id              The run that the role command carried.
 * @param[in] cell_id             The cell of this pass.
 * @param[in] pass                The pass that follows.
 * @param[in] packets_per_message The packets of one message of this cell.
 *
 * @retval ESP_OK               The receiver counts the frames of that pass.
 * @retval ESP_ERR_INVALID_ARG  The packets of one message is 0.
 */
esp_err_t bol_receiver_arm(uint32_t run_id, uint16_t cell_id, bol_pass_t pass,
                           uint32_t packets_per_message);

/**
 * @brief Closes the pass and counts the run that its end left open.
 *
 * @param[in] positions  The positions that the sender put on the air.
 *
 * @retval ESP_OK                 The counters state the whole pass.
 * @retval ESP_ERR_INVALID_STATE  No pass is armed.
 */
esp_err_t bol_receiver_finish(uint32_t positions);

/**
 * @brief Copies the counters of the pass that the receiver last armed.
 *
 * @param[out] out_counters  The counters of that pass.
 *
 * @retval ESP_OK               The copy holds the counters.
 * @retval ESP_ERR_INVALID_ARG  The pointer is NULL.
 */
esp_err_t bol_receiver_counters(bol_receiver_counters_t *out_counters);

#ifdef __cplusplus
}
#endif

#endif /* BOL_RECEIVER_H */
