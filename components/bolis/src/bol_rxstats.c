/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file bol_rxstats.c
 * @brief The counters of a receiver and the bins of its run-length
 *        histogram (decision record
 *        2026-11-13-the-receiving-loop-of-a-pass.md).
 *
 * The histogram is linear, because the mass of a healthy pass sits at the
 * shortest runs and the burst model of thinkbook section 3.6 needs
 * resolution there.
 *
 * The window holds the 64 most recent positions in one unsigned value of 64
 * bits, so the memory of a pass does not grow with its frame budget.
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "bol_rxstats.h"
#include "bol_stats.h"

/** @brief The highest bin index, which holds every run above the scale. */
#define BOL_RXSTATS_LAST_BIN (BOL_HISTOGRAM_BINS - 1U)

/** @brief The one bit that marks the newest position of the window. */
#define BOL_RXSTATS_ONE 1ULL

// cppcheck-suppress misra-c2012-8.7 ; the receiver task calls this in a later
// change, so the module keeps external linkage
uint32_t bol_rxstats_run_length_bin(uint32_t run_length)
{
    uint32_t bin = 0U;

    if (run_length > BOL_RX_RUN_LENGTH_MAX) {
        bin = BOL_RXSTATS_LAST_BIN;
    } else if (run_length > 0U) {
        bin = run_length - 1U;
    } else {
        bin = 0U;
    }

    return bin;
}

// cppcheck-suppress misra-c2012-8.7 ; the receiver task calls this in a later
// change, so the module keeps external linkage
void bol_rxstats_reset(bol_receiver_counters_t *counters)
{
    if (counters != NULL) {
        /* The counters hold no pointer, so one clear sets every field. */
        (void)memset(counters, 0, sizeof(*counters));
    }
}

// cppcheck-suppress misra-c2012-8.7 ; the receiver task calls this in a later
// change, so the module keeps external linkage
uint32_t bol_rxstats_position(uint32_t message_id, uint8_t fragment_index,
                              uint32_t packets_per_message)
{
    uint32_t position = 0U;

    if (packets_per_message > 0U) {
        position = (message_id * packets_per_message) + (uint32_t)fragment_index;
    }

    return position;
}

/**
 * @brief Adds one loss run of the given length to the histogram.
 */
static void bol_rxstats_add_run(bol_receiver_counters_t *counters, uint32_t run_length)
{
    if (run_length > 0U) {
        counters->loss_run_length_histogram[bol_rxstats_run_length_bin(run_length)]++;
    }
}

/**
 * @brief Records the strength of one packet that passed the header check.
 */
static void bol_rxstats_add_rssi(bol_receiver_counters_t *counters, int32_t rssi_dbm)
{
    if (counters->rssi_count == 0U) {
        counters->rssi_min_dbm = rssi_dbm;
        counters->rssi_max_dbm = rssi_dbm;
    } else {
        if (rssi_dbm < counters->rssi_min_dbm) {
            counters->rssi_min_dbm = rssi_dbm;
        }
        if (rssi_dbm > counters->rssi_max_dbm) {
            counters->rssi_max_dbm = rssi_dbm;
        }
    }
    counters->rssi_sum_dbm += (int64_t)rssi_dbm;
    counters->rssi_count++;
}

/**
 * @brief Reports whether the window already marks one position.
 *
 * A position below the floor of the window counts as seen, because a pass
 * sends each position once and the node already passed that position.
 */
static bool bol_rxstats_window_holds(const bol_receiver_counters_t *counters,
                                     uint32_t position)
{
    const uint32_t behind = counters->highest_position - position;
    bool is_held = true;

    if (behind < BOL_RX_WINDOW_POSITIONS) {
        is_held = ((counters->window >> behind) & BOL_RXSTATS_ONE) != 0ULL;
    }

    return is_held;
}

// cppcheck-suppress misra-c2012-8.7 ; the receiver task calls this in a later
// change, so the module keeps external linkage
bool bol_rxstats_accept(bol_receiver_counters_t *counters, uint32_t position,
                        int32_t rssi_dbm)
{
    bool is_new = false;

    if (counters != NULL) {
        if (!counters->has_position) {
            /* The first packet of a pass opens the run that precedes it. */
            bol_rxstats_add_run(counters, position);
            counters->has_position = true;
            counters->highest_position = position;
            counters->window = BOL_RXSTATS_ONE;
            is_new = true;
        } else if (position > counters->highest_position) {
            const uint32_t step = position - counters->highest_position;

            bol_rxstats_add_run(counters, step - 1U);
            if (step < BOL_RX_WINDOW_POSITIONS) {
                counters->window = (counters->window << step) | BOL_RXSTATS_ONE;
            } else {
                counters->window = BOL_RXSTATS_ONE;
            }
            counters->highest_position = position;
            is_new = true;
        } else if (!bol_rxstats_window_holds(counters, position)) {
            const uint32_t behind = counters->highest_position - position;

            counters->window |= (BOL_RXSTATS_ONE << behind);
            is_new = true;
        } else {
            counters->duplicates++;
        }

        if (is_new) {
            counters->packets_received++;
            bol_rxstats_add_rssi(counters, rssi_dbm);
        }
    }

    return is_new;
}

// cppcheck-suppress misra-c2012-8.7 ; the receiver task calls this in a later
// change, so the module keeps external linkage
void bol_rxstats_finish(bol_receiver_counters_t *counters, uint32_t positions)
{
    if (counters != NULL) {
        if (!counters->has_position) {
            bol_rxstats_add_run(counters, positions);
        } else if (positions > (counters->highest_position + 1U)) {
            bol_rxstats_add_run(counters,
                                positions - counters->highest_position - 1U);
        } else {
            /* The pass ended on the position that it sent last. */
        }
    }
}

// cppcheck-suppress misra-c2012-8.7 ; the receiver task calls this in a later
// change, so the module keeps external linkage
bool bol_rxstats_mean_rssi_dbm(const bol_receiver_counters_t *counters,
                               double *out_mean_dbm)
{
    bool has_mean = false;

    if ((counters != NULL) && (out_mean_dbm != NULL) && (counters->rssi_count > 0U)) {
        *out_mean_dbm = (double)counters->rssi_sum_dbm / (double)counters->rssi_count;
        has_mean = true;
    }

    return has_mean;
}
