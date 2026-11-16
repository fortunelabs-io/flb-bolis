/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file bol_rxstats.h
 * @brief The counters of a receiver and the bins of its run-length
 *        histogram (decision record
 *        2026-11-13-the-receiving-loop-of-a-pass.md).
 *
 * The receiver derives the position of a packet inside its pass from the
 * message ID and the fragment index of its header. A position above the
 * highest one seen opens a gap, and the packets of that gap are one loss
 * run. A position that the window already marks is a duplicate.
 *
 * This module touches no radio and no task. It holds the state machine of a
 * pass, so the reader tests drive it on the host.
 */

#ifndef BOL_RXSTATS_H
#define BOL_RXSTATS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "bol_stats.h"

#ifdef __cplusplus
extern "C" {
#endif

/** @brief The positions that the duplicate window remembers. */
#define BOL_RX_WINDOW_POSITIONS 64U

/** @brief The longest run that its own bin holds. A longer run overflows. */
#define BOL_RX_RUN_LENGTH_MAX 15U

/**
 * @brief The counters that a receiver reports for one pass.
 *
 * The names match the keys of the stats reply. The window fields hold the
 * state of the pass and reach no reply.
 */
typedef struct {
    uint32_t packets_received;     /*!< Packets that passed the header check. */
    uint32_t duplicates;           /*!< Packets of a position already seen. */
    uint32_t foreign_packets;      /*!< Packets of another sender or another run. */
    uint32_t messages_complete;    /*!< Messages whose every fragment arrived. */
    uint32_t messages_incomplete;  /*!< Messages that ended with a fragment missing. */
    uint32_t corrupt_packets;      /*!< Packets that failed the fill or the length. */
    uint32_t dropped_packets;      /*!< Packets that the node did not process. */
    /*! The lost runs, in the bins that the record fixes. */
    uint32_t loss_run_length_histogram[BOL_HISTOGRAM_BINS];
    int32_t rssi_min_dbm;          /*!< The weakest packet, in dBm. */
    int32_t rssi_max_dbm;          /*!< The strongest packet, in dBm. */
    int64_t rssi_sum_dbm;          /*!< The sum that the mean divides. */
    uint32_t rssi_count;           /*!< The packets that the sum holds. */
    uint64_t window;               /*!< The positions that the window marks. */
    uint32_t highest_position;     /*!< The highest position that arrived. */
    bool has_position;             /*!< Whether any packet arrived. */
} bol_receiver_counters_t;

/**
 * @brief Returns the bin that one loss run falls in.
 *
 * Bin k holds a run of exactly k plus one packets, for k from 0 to 14. Bin
 * 15 holds every run of BOL_RX_RUN_LENGTH_MAX plus one packets or more.
 *
 * @param[in] run_length  The consecutive packets that the pass lost, 1 or more.
 *
 * @return The bin index, 0 to BOL_HISTOGRAM_BINS minus 1. A run of 0 returns 0.
 */
uint32_t bol_rxstats_run_length_bin(uint32_t run_length);

/**
 * @brief Clears every counter and the window of one pass.
 *
 * @param[out] counters  The counters to clear.
 */
void bol_rxstats_reset(bol_receiver_counters_t *counters);

/**
 * @brief Returns the position of one packet inside its pass.
 *
 * @param[in] message_id         The message that the header states.
 * @param[in] fragment_index     The fragment that the header states.
 * @param[in] packets_per_message The packets of one message, 1 or more.
 *
 * @return The position, counting from 0.
 */
uint32_t bol_rxstats_position(uint32_t message_id, uint8_t fragment_index,
                              uint32_t packets_per_message);

/**
 * @brief Counts one packet that passed the header check.
 *
 * A position above the highest one seen opens a gap, and this function adds
 * that gap to the histogram as one loss run. A position that the window
 * marks, or one below the floor of the window, counts as a duplicate.
 *
 * @param[in,out] counters  The counters of the pass.
 * @param[in]     position  The position of the packet inside its pass.
 * @param[in]     rssi_dbm  The strength that the driver reported, in dBm.
 *
 * @return True when the packet is new, and false when it repeats a position.
 */
bool bol_rxstats_accept(bol_receiver_counters_t *counters, uint32_t position,
                        int32_t rssi_dbm);

/**
 * @brief Closes a pass and counts the run that its end left open.
 *
 * A pass that stops before its last position lost every packet after the
 * highest one that arrived, and that gap is one further loss run.
 *
 * @param[in,out] counters   The counters of the pass.
 * @param[in]     positions  The positions that the pass sent.
 */
void bol_rxstats_finish(bol_receiver_counters_t *counters, uint32_t positions);

/**
 * @brief Returns the mean strength of the packets that arrived.
 *
 * @param[in]  counters      The counters of the pass.
 * @param[out] out_mean_dbm  The arithmetic mean, in dBm.
 *
 * @return True when at least one packet arrived, and false otherwise. A pass
 *         that received none states no mean.
 */
bool bol_rxstats_mean_rssi_dbm(const bol_receiver_counters_t *counters,
                               double *out_mean_dbm);

#ifdef __cplusplus
}
#endif

#endif /* BOL_RXSTATS_H */
