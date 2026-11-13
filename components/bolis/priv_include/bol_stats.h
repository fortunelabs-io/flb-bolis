/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file bol_stats.h
 * @brief The counters of a sender and the bins of its histogram (decision
 *        record 2026-11-13-the-sending-loop-of-a-pass.md).
 *
 * The counters hold what one pass produced, and the stats reply states them
 * under the names that decision record
 * 2026-11-11-control-line-command-fields.md fixes.
 *
 * This module touches no radio and no task. It holds arithmetic, so the
 * reader tests drive it on the host.
 */

#ifndef BOL_STATS_H
#define BOL_STATS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/** @brief The bins of every histogram. */
#define BOL_HISTOGRAM_BINS 16U

/** @brief The lower edge of bin 1, in microseconds. */
#define BOL_HISTOGRAM_FIRST_EDGE_US 64U

/** @brief The distinct error codes that one pass records. */
#define BOL_SEND_ERROR_SLOTS 8U

/** @brief One ESP-IDF error code and the sends that returned it. */
typedef struct {
    esp_err_t code;  /*!< The code that the send returned. */
    uint32_t count;  /*!< The sends that returned it. */
} bol_send_error_t;

/**
 * @brief The counters that a sender reports for one pass.
 *
 * The names match the keys of the stats reply, so the host copies them
 * without a second table.
 */
typedef struct {
    uint32_t messages_sent;    /*!< Whole messages that the pass put on the air. */
    uint32_t packets_sent;     /*!< Packets that the pass put on the air. */
    uint32_t callback_ok;      /*!< Send callbacks that reported success. */
    uint32_t callback_failed;  /*!< Send callbacks that reported a failure. */
    uint32_t no_mem_events;    /*!< Sends that returned a no-memory error. */
    uint32_t dropped_packets;  /*!< Packets that every attempt failed to send. */
    /*! The send-to-callback time, in the bins that the record fixes. */
    uint32_t send_to_callback_us_histogram[BOL_HISTOGRAM_BINS];
    /*! One entry per distinct error code, filled from the lowest index. */
    bol_send_error_t send_errors[BOL_SEND_ERROR_SLOTS];
    uint32_t send_error_kinds;  /*!< The entries of send_errors that hold a code. */
} bol_sender_counters_t;

/**
 * @brief Returns the bin that one send-to-callback time falls in.
 *
 * Bin 0 holds every value below BOL_HISTOGRAM_FIRST_EDGE_US. Bin k, for k
 * from 1 to 14, holds every value from 64 times 2 to the power k minus 1, up
 * to 64 times 2 to the power k, excluding the upper edge. Bin 15 holds every
 * value at or above its lower edge.
 *
 * @param[in] microseconds  The time from the send to its callback.
 *
 * @return The bin index, 0 to BOL_HISTOGRAM_BINS minus 1.
 */
uint32_t bol_stats_histogram_bin(uint32_t microseconds);

/**
 * @brief Clears every counter of one pass.
 *
 * @param[out] counters  The counters to clear.
 */
void bol_stats_reset(bol_sender_counters_t *counters);

/**
 * @brief Counts one send that returned an error code.
 *
 * The table holds BOL_SEND_ERROR_SLOTS distinct codes. A code that arrives
 * when every slot holds another code raises the count of the last slot, so
 * the total of the table stays equal to the sends that failed.
 *
 * @param[in,out] counters  The counters of the pass.
 * @param[in]     code      The code that the send returned.
 */
void bol_stats_count_send_error(bol_sender_counters_t *counters, esp_err_t code);

/**
 * @brief Counts one send callback and the time that it took.
 *
 * @param[in,out] counters      The counters of the pass.
 * @param[in]     is_ok         Whether the callback reported success.
 * @param[in]     microseconds  The time from the send to the callback.
 */
void bol_stats_count_callback(bol_sender_counters_t *counters, bool is_ok,
                              uint32_t microseconds);

/**
 * @brief Returns the packets that one message of a payload takes.
 *
 * A message of p bytes takes n(p) packets, where n(p) is p divided by the
 * payload limit, rounded up (thinkbook section 3.1).
 *
 * @param[in] payload_bytes       The payload of one message, 1 or more.
 * @param[in] payload_limit_bytes The packet payload limit L, 1 or more.
 *
 * @return The packets of one message, or 0 when either argument is 0.
 */
uint32_t bol_stats_packets_per_message(uint32_t payload_bytes,
                                       uint32_t payload_limit_bytes);

/**
 * @brief Returns the whole messages that fit inside a frame budget.
 *
 * A pass sends whole messages only, because a message cut short at the
 * budget reaches the receiver with a missing fragment and raises the message
 * loss of a link that did not cause it.
 *
 * @param[in] frames              The frame budget of the pass.
 * @param[in] packets_per_message The packets of one message, 1 or more.
 *
 * @return The whole messages that fit, or 0 when packets_per_message is 0.
 */
uint32_t bol_stats_messages_that_fit(uint32_t frames, uint32_t packets_per_message);

#ifdef __cplusplus
}
#endif

#endif /* BOL_STATS_H */
