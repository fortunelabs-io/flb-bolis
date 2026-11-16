/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * The TEST_CASE macro of unity builds the name of each generated function
 * from __LINE__, so a case at one line number collides with a case at the
 * same line number in another test file. The collision comes from the
 * expansion of an adopted macro, which deviation D-002 covers. It belongs to
 * the set of test files rather than to one of them, so each one carries this
 * suppression.
 */
/* cppcheck-suppress-file misra-c2012-5.9 */

/**
 * @file test_bol_rxstats.c
 * @brief Tests of the receiver counters and the run-length histogram
 *        (decision record 2026-11-13-the-receiving-loop-of-a-pass.md).
 *
 * The bin edges bind every record that a corpus stores, so the cases state
 * each edge. The window cases state what a gap, a repeat, and a reordered
 * pair each count as, because a wrong answer there reports the node as a
 * property of the link.
 */

#include <stdbool.h>
#include <stdint.h>

#include "unity.h"

#include "bol_rxstats.h"

/** @brief A strength that the cases report, in dBm. */
#define BOL_TEST_RSSI (-63)

/** @brief The positions of a short pass. */
#define BOL_TEST_POSITIONS 10U

TEST_CASE("a run of one packet fills the first bin", "[bol_rxstats]")
{
    TEST_ASSERT_EQUAL_UINT32(0U, bol_rxstats_run_length_bin(1U));
    TEST_ASSERT_EQUAL_UINT32(1U, bol_rxstats_run_length_bin(2U));
    TEST_ASSERT_EQUAL_UINT32(14U, bol_rxstats_run_length_bin(15U));
}

TEST_CASE("a run of sixteen or more fills the last bin", "[bol_rxstats]")
{
    TEST_ASSERT_EQUAL_UINT32(15U, bol_rxstats_run_length_bin(16U));
    TEST_ASSERT_EQUAL_UINT32(15U, bol_rxstats_run_length_bin(2000U));
}

TEST_CASE("the position of a packet follows its message and fragment",
          "[bol_rxstats]")
{
    TEST_ASSERT_EQUAL_UINT32(0U, bol_rxstats_position(0U, 0U, 3U));
    TEST_ASSERT_EQUAL_UINT32(2U, bol_rxstats_position(0U, 2U, 3U));
    TEST_ASSERT_EQUAL_UINT32(3U, bol_rxstats_position(1U, 0U, 3U));
    TEST_ASSERT_EQUAL_UINT32(7U, bol_rxstats_position(7U, 0U, 1U));
}

TEST_CASE("a pass with no loss records no run", "[bol_rxstats]")
{
    bol_receiver_counters_t counters;
    uint32_t position = 0U;

    bol_rxstats_reset(&counters);
    while (position < BOL_TEST_POSITIONS) {
        TEST_ASSERT_TRUE(bol_rxstats_accept(&counters, position, BOL_TEST_RSSI));
        position++;
    }
    bol_rxstats_finish(&counters, BOL_TEST_POSITIONS);

    TEST_ASSERT_EQUAL_UINT32(BOL_TEST_POSITIONS, counters.packets_received);
    TEST_ASSERT_EQUAL_UINT32(0U, counters.duplicates);
    TEST_ASSERT_EQUAL_UINT32(0U, counters.loss_run_length_histogram[0]);
    TEST_ASSERT_EQUAL_UINT32(0U, counters.loss_run_length_histogram[15]);
}

TEST_CASE("a gap of one packet records a run of one", "[bol_rxstats]")
{
    bol_receiver_counters_t counters;

    bol_rxstats_reset(&counters);
    (void)bol_rxstats_accept(&counters, 0U, BOL_TEST_RSSI);
    (void)bol_rxstats_accept(&counters, 2U, BOL_TEST_RSSI);
    bol_rxstats_finish(&counters, 3U);

    TEST_ASSERT_EQUAL_UINT32(2U, counters.packets_received);
    TEST_ASSERT_EQUAL_UINT32(1U, counters.loss_run_length_histogram[0]);
}

TEST_CASE("a gap of three packets records a run of three", "[bol_rxstats]")
{
    bol_receiver_counters_t counters;

    bol_rxstats_reset(&counters);
    (void)bol_rxstats_accept(&counters, 0U, BOL_TEST_RSSI);
    (void)bol_rxstats_accept(&counters, 4U, BOL_TEST_RSSI);

    TEST_ASSERT_EQUAL_UINT32(1U, counters.loss_run_length_histogram[2]);
}

TEST_CASE("a pass that starts late records the run before it", "[bol_rxstats]")
{
    bol_receiver_counters_t counters;

    bol_rxstats_reset(&counters);
    (void)bol_rxstats_accept(&counters, 2U, BOL_TEST_RSSI);

    TEST_ASSERT_EQUAL_UINT32(1U, counters.loss_run_length_histogram[1]);
}

TEST_CASE("a pass that ends early records the run after it", "[bol_rxstats]")
{
    bol_receiver_counters_t counters;

    bol_rxstats_reset(&counters);
    (void)bol_rxstats_accept(&counters, 0U, BOL_TEST_RSSI);
    bol_rxstats_finish(&counters, 4U);

    TEST_ASSERT_EQUAL_UINT32(1U, counters.loss_run_length_histogram[2]);
}

TEST_CASE("a pass that received nothing lost every position", "[bol_rxstats]")
{
    bol_receiver_counters_t counters;

    bol_rxstats_reset(&counters);
    bol_rxstats_finish(&counters, 5U);

    TEST_ASSERT_EQUAL_UINT32(0U, counters.packets_received);
    TEST_ASSERT_EQUAL_UINT32(1U, counters.loss_run_length_histogram[4]);
}

TEST_CASE("one position twice counts one duplicate", "[bol_rxstats]")
{
    bol_receiver_counters_t counters;

    bol_rxstats_reset(&counters);
    TEST_ASSERT_TRUE(bol_rxstats_accept(&counters, 3U, BOL_TEST_RSSI));
    TEST_ASSERT_FALSE(bol_rxstats_accept(&counters, 3U, BOL_TEST_RSSI));

    TEST_ASSERT_EQUAL_UINT32(1U, counters.packets_received);
    TEST_ASSERT_EQUAL_UINT32(1U, counters.duplicates);
}

TEST_CASE("a reordered pair inside the window is no loss", "[bol_rxstats]")
{
    bol_receiver_counters_t counters;

    bol_rxstats_reset(&counters);
    (void)bol_rxstats_accept(&counters, 0U, BOL_TEST_RSSI);
    (void)bol_rxstats_accept(&counters, 2U, BOL_TEST_RSSI);
    /* Position 1 arrives after position 2, and it fills the gap. */
    TEST_ASSERT_TRUE(bol_rxstats_accept(&counters, 1U, BOL_TEST_RSSI));
    bol_rxstats_finish(&counters, 3U);

    TEST_ASSERT_EQUAL_UINT32(3U, counters.packets_received);
    TEST_ASSERT_EQUAL_UINT32(0U, counters.duplicates);
}

TEST_CASE("a packet below the window counts as a duplicate", "[bol_rxstats]")
{
    bol_receiver_counters_t counters;

    bol_rxstats_reset(&counters);
    (void)bol_rxstats_accept(&counters, 0U, BOL_TEST_RSSI);
    (void)bol_rxstats_accept(&counters, BOL_RX_WINDOW_POSITIONS + 10U, BOL_TEST_RSSI);
    TEST_ASSERT_FALSE(bol_rxstats_accept(&counters, 1U, BOL_TEST_RSSI));

    TEST_ASSERT_EQUAL_UINT32(1U, counters.duplicates);
}

TEST_CASE("the strength of a pass covers the packets that arrived",
          "[bol_rxstats]")
{
    bol_receiver_counters_t counters;
    double mean = 0.0;

    bol_rxstats_reset(&counters);
    (void)bol_rxstats_accept(&counters, 0U, -70);
    (void)bol_rxstats_accept(&counters, 1U, -60);
    (void)bol_rxstats_accept(&counters, 2U, -50);

    TEST_ASSERT_EQUAL_INT32(-70, counters.rssi_min_dbm);
    TEST_ASSERT_EQUAL_INT32(-50, counters.rssi_max_dbm);
    TEST_ASSERT_TRUE(bol_rxstats_mean_rssi_dbm(&counters, &mean));
    TEST_ASSERT_EQUAL_DOUBLE(-60.0, mean);
}

TEST_CASE("a duplicate changes no strength", "[bol_rxstats]")
{
    bol_receiver_counters_t counters;
    double mean = 0.0;

    bol_rxstats_reset(&counters);
    (void)bol_rxstats_accept(&counters, 0U, -70);
    (void)bol_rxstats_accept(&counters, 0U, -10);

    TEST_ASSERT_EQUAL_INT32(-70, counters.rssi_max_dbm);
    TEST_ASSERT_TRUE(bol_rxstats_mean_rssi_dbm(&counters, &mean));
    TEST_ASSERT_EQUAL_DOUBLE(-70.0, mean);
}

TEST_CASE("a pass that received nothing states no strength", "[bol_rxstats]")
{
    bol_receiver_counters_t counters;
    double mean = 0.0;

    bol_rxstats_reset(&counters);

    TEST_ASSERT_FALSE(bol_rxstats_mean_rssi_dbm(&counters, &mean));
}

TEST_CASE("a dropped packet is no loss and no corrupt frame", "[bol_rxstats]")
{
    bol_receiver_counters_t counters;

    bol_rxstats_reset(&counters);
    counters.dropped_packets++;

    TEST_ASSERT_EQUAL_UINT32(1U, counters.dropped_packets);
    TEST_ASSERT_EQUAL_UINT32(0U, counters.corrupt_packets);
    TEST_ASSERT_EQUAL_UINT32(0U, counters.loss_run_length_histogram[0]);
}

TEST_CASE("a NULL pointer changes nothing", "[bol_rxstats]")
{
    double mean = 0.0;

    bol_rxstats_reset(NULL);
    bol_rxstats_finish(NULL, 1U);
    TEST_ASSERT_FALSE(bol_rxstats_accept(NULL, 0U, BOL_TEST_RSSI));
    TEST_ASSERT_FALSE(bol_rxstats_mean_rssi_dbm(NULL, &mean));
}
