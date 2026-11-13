/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file bol_stats.c
 * @brief The counters of a sender and the bins of its histogram (decision
 *        record 2026-11-13-the-sending-loop-of-a-pass.md).
 *
 * The histogram scale doubles from 64 microseconds. A send callback cannot
 * return before the airtime of its frame, so the airtime of the swept
 * payload list falls in the middle of the range: 648 microseconds at 14
 * bytes in bin 4, 2536 at 250 bytes in bin 6, and 12576 at 1470 bytes in
 * bin 8. The bins above those hold the retry structure that a unicast pass
 * adds.
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "esp_err.h"

#include "bol_stats.h"

/** @brief The highest bin index, which holds every value above the scale. */
#define BOL_STATS_LAST_BIN (BOL_HISTOGRAM_BINS - 1U)

// cppcheck-suppress misra-c2012-8.7 ; the sender task calls this in a later
// change, so the module keeps external linkage
void bol_stats_reset(bol_sender_counters_t *counters)
{
    if (counters != NULL) {
        /* The counters hold no pointer, so one clear sets every field. The
         * return value is the destination, which the caller already holds. */
        (void)memset(counters, 0, sizeof(*counters));
    }
}

uint32_t bol_stats_histogram_bin(uint32_t microseconds)
{
    uint32_t bin = 0U;

    if (microseconds >= (uint32_t)BOL_HISTOGRAM_FIRST_EDGE_US) {
        uint32_t edge = (uint32_t)BOL_HISTOGRAM_FIRST_EDGE_US;

        bin = 1U;
        while ((bin < BOL_STATS_LAST_BIN) && (microseconds >= (edge * 2U))) {
            edge = edge * 2U;
            bin++;
        }
    }

    return bin;
}

// cppcheck-suppress misra-c2012-8.7 ; the sender task calls this in a later
// change, so the module keeps external linkage
void bol_stats_count_send_error(bol_sender_counters_t *counters, esp_err_t code)
{
    if (counters != NULL) {
        uint32_t index = 0U;
        bool is_counted = false;

        while ((index < counters->send_error_kinds) && !is_counted) {
            if (counters->send_errors[index].code == code) {
                counters->send_errors[index].count++;
                is_counted = true;
            } else {
                index++;
            }
        }

        if (!is_counted) {
            if (counters->send_error_kinds < BOL_SEND_ERROR_SLOTS) {
                const uint32_t slot = counters->send_error_kinds;

                counters->send_errors[slot].code = code;
                counters->send_errors[slot].count = 1U;
                counters->send_error_kinds++;
            } else {
                /* Every slot holds another code. The last slot takes the
                 * count, so the total of the table stays equal to the sends
                 * that failed. */
                counters->send_errors[BOL_SEND_ERROR_SLOTS - 1U].count++;
            }
        }
    }
}

// cppcheck-suppress misra-c2012-8.7 ; the sender task calls this in a later
// change, so the module keeps external linkage
void bol_stats_count_callback(bol_sender_counters_t *counters, bool is_ok,
                              uint32_t microseconds)
{
    if (counters != NULL) {
        const uint32_t bin = bol_stats_histogram_bin(microseconds);

        if (is_ok) {
            counters->callback_ok++;
        } else {
            counters->callback_failed++;
        }
        counters->send_to_callback_us_histogram[bin]++;
    }
}

// cppcheck-suppress misra-c2012-8.7 ; the sender task calls this in a later
// change, so the module keeps external linkage
uint32_t bol_stats_packets_per_message(uint32_t payload_bytes,
                                       uint32_t payload_limit_bytes)
{
    uint32_t packets = 0U;

    if ((payload_bytes > 0U) && (payload_limit_bytes > 0U)) {
        packets = ((payload_bytes - 1U) / payload_limit_bytes) + 1U;
    }

    return packets;
}

// cppcheck-suppress misra-c2012-8.7 ; the sender task calls this in a later
// change, so the module keeps external linkage
uint32_t bol_stats_messages_that_fit(uint32_t frames, uint32_t packets_per_message)
{
    uint32_t messages = 0U;

    if (packets_per_message > 0U) {
        messages = frames / packets_per_message;
    }

    return messages;
}
