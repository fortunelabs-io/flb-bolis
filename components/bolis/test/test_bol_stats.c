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
 * @file test_bol_stats.c
 * @brief Tests of the sender counters and the histogram bins (decision
 *        record 2026-11-13-the-sending-loop-of-a-pass.md).
 *
 * The bin edges bind every record that a corpus stores, so the cases state
 * each edge rather than reading it back from the module. The airtime figures
 * come from the model of thinkbook section 3, which states 12.58 ms at 1470
 * bytes.
 */

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "unity.h"

#include "bol_stats.h"

/** @brief The airtime of a 14-byte frame, in microseconds (thinkbook 3.3). */
#define BOL_TEST_AIRTIME_14_US 648U

/** @brief The airtime of a 250-byte frame, in microseconds. */
#define BOL_TEST_AIRTIME_250_US 2536U

/** @brief The airtime of a 1470-byte frame, in microseconds. */
#define BOL_TEST_AIRTIME_1470_US 12576U

/** @brief The frames of one pass (thinkbook section 8). */
#define BOL_TEST_FRAMES 2000U

/** @brief The v2.0 packet payload limit, in bytes. */
#define BOL_TEST_LIMIT_V2 1470U

TEST_CASE("every histogram holds sixteen bins", "[bol_stats]")
{
    TEST_ASSERT_EQUAL_UINT(16U, BOL_HISTOGRAM_BINS);
}

TEST_CASE("bin zero holds every value below the first edge", "[bol_stats]")
{
    TEST_ASSERT_EQUAL_UINT32(0U, bol_stats_histogram_bin(0U));
    TEST_ASSERT_EQUAL_UINT32(0U, bol_stats_histogram_bin(63U));
    TEST_ASSERT_EQUAL_UINT32(1U, bol_stats_histogram_bin(64U));
}

TEST_CASE("the scale doubles from the first edge", "[bol_stats]")
{
    TEST_ASSERT_EQUAL_UINT32(1U, bol_stats_histogram_bin(127U));
    TEST_ASSERT_EQUAL_UINT32(2U, bol_stats_histogram_bin(128U));
    TEST_ASSERT_EQUAL_UINT32(2U, bol_stats_histogram_bin(255U));
    TEST_ASSERT_EQUAL_UINT32(3U, bol_stats_histogram_bin(256U));
    TEST_ASSERT_EQUAL_UINT32(4U, bol_stats_histogram_bin(512U));
}

TEST_CASE("the airtime of each swept payload falls mid scale", "[bol_stats]")
{
    TEST_ASSERT_EQUAL_UINT32(4U, bol_stats_histogram_bin(BOL_TEST_AIRTIME_14_US));
    TEST_ASSERT_EQUAL_UINT32(6U, bol_stats_histogram_bin(BOL_TEST_AIRTIME_250_US));
    TEST_ASSERT_EQUAL_UINT32(8U, bol_stats_histogram_bin(BOL_TEST_AIRTIME_1470_US));
}

TEST_CASE("the last bin holds every value at or above its edge", "[bol_stats]")
{
    TEST_ASSERT_EQUAL_UINT32(14U, bol_stats_histogram_bin(1048575U));
    TEST_ASSERT_EQUAL_UINT32(15U, bol_stats_histogram_bin(1048576U));
    TEST_ASSERT_EQUAL_UINT32(15U, bol_stats_histogram_bin(UINT32_MAX));
}

TEST_CASE("a reset clears every counter", "[bol_stats]")
{
    bol_sender_counters_t counters;

    (void)memset(&counters, 0xFF, sizeof(counters));
    bol_stats_reset(&counters);

    TEST_ASSERT_EQUAL_UINT32(0U, counters.packets_sent);
    TEST_ASSERT_EQUAL_UINT32(0U, counters.messages_sent);
    TEST_ASSERT_EQUAL_UINT32(0U, counters.callback_ok);
    TEST_ASSERT_EQUAL_UINT32(0U, counters.callback_failed);
    TEST_ASSERT_EQUAL_UINT32(0U, counters.no_mem_events);
    TEST_ASSERT_EQUAL_UINT32(0U, counters.send_error_kinds);
    TEST_ASSERT_EQUAL_UINT32(0U, counters.send_to_callback_us_histogram[0]);
}

TEST_CASE("a callback raises one bin and one outcome", "[bol_stats]")
{
    bol_sender_counters_t counters;

    bol_stats_reset(&counters);
    bol_stats_count_callback(&counters, true, BOL_TEST_AIRTIME_1470_US);
    bol_stats_count_callback(&counters, false, BOL_TEST_AIRTIME_1470_US);

    TEST_ASSERT_EQUAL_UINT32(1U, counters.callback_ok);
    TEST_ASSERT_EQUAL_UINT32(1U, counters.callback_failed);
    TEST_ASSERT_EQUAL_UINT32(2U, counters.send_to_callback_us_histogram[8]);
}

TEST_CASE("one code takes one slot however often it arrives", "[bol_stats]")
{
    bol_sender_counters_t counters;

    bol_stats_reset(&counters);
    bol_stats_count_send_error(&counters, ESP_ERR_NO_MEM);
    bol_stats_count_send_error(&counters, ESP_ERR_NO_MEM);
    bol_stats_count_send_error(&counters, ESP_ERR_INVALID_ARG);

    TEST_ASSERT_EQUAL_UINT32(2U, counters.send_error_kinds);
    TEST_ASSERT_EQUAL_INT(ESP_ERR_NO_MEM, counters.send_errors[0].code);
    TEST_ASSERT_EQUAL_UINT32(2U, counters.send_errors[0].count);
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, counters.send_errors[1].code);
    TEST_ASSERT_EQUAL_UINT32(1U, counters.send_errors[1].count);
}

TEST_CASE("a table that is full keeps the total of the failures", "[bol_stats]")
{
    bol_sender_counters_t counters;
    uint32_t index = 0U;
    uint32_t total = 0U;

    bol_stats_reset(&counters);
    while (index < (BOL_SEND_ERROR_SLOTS + 3U)) {
        /* The sum is a composite expression, so it takes a name before the
         * cast to the error type (MISRA Rule 10.8). */
        const int code = 0x100 + (int)index;

        bol_stats_count_send_error(&counters, (esp_err_t)code);
        index++;
    }

    TEST_ASSERT_EQUAL_UINT32(BOL_SEND_ERROR_SLOTS, counters.send_error_kinds);
    index = 0U;
    while (index < BOL_SEND_ERROR_SLOTS) {
        total += counters.send_errors[index].count;
        index++;
    }
    TEST_ASSERT_EQUAL_UINT32(BOL_SEND_ERROR_SLOTS + 3U, total);
}

TEST_CASE("a payload at or below the limit takes one packet", "[bol_stats]")
{
    TEST_ASSERT_EQUAL_UINT32(1U, bol_stats_packets_per_message(14U, BOL_TEST_LIMIT_V2));
    TEST_ASSERT_EQUAL_UINT32(1U, bol_stats_packets_per_message(1470U, BOL_TEST_LIMIT_V2));
}

TEST_CASE("a payload above the limit fragments", "[bol_stats]")
{
    TEST_ASSERT_EQUAL_UINT32(2U, bol_stats_packets_per_message(1471U, BOL_TEST_LIMIT_V2));
    TEST_ASSERT_EQUAL_UINT32(2U, bol_stats_packets_per_message(2940U, BOL_TEST_LIMIT_V2));
    TEST_ASSERT_EQUAL_UINT32(3U, bol_stats_packets_per_message(2941U, BOL_TEST_LIMIT_V2));
}

TEST_CASE("a pass sends whole messages only", "[bol_stats]")
{
    /* A budget of 2000 divides into 1000 messages of two packets, and into
     * 666 messages of three packets with two packets left over. */
    TEST_ASSERT_EQUAL_UINT32(2000U, bol_stats_messages_that_fit(BOL_TEST_FRAMES, 1U));
    TEST_ASSERT_EQUAL_UINT32(1000U, bol_stats_messages_that_fit(BOL_TEST_FRAMES, 2U));
    TEST_ASSERT_EQUAL_UINT32(666U, bol_stats_messages_that_fit(BOL_TEST_FRAMES, 3U));
}

TEST_CASE("a budget shorter than one message sends nothing", "[bol_stats]")
{
    TEST_ASSERT_EQUAL_UINT32(0U, bol_stats_messages_that_fit(2U, 3U));
    TEST_ASSERT_EQUAL_UINT32(0U, bol_stats_messages_that_fit(BOL_TEST_FRAMES, 0U));
}

TEST_CASE("a NULL pointer changes nothing", "[bol_stats]")
{
    bol_stats_reset(NULL);
    bol_stats_count_callback(NULL, true, 1U);
    bol_stats_count_send_error(NULL, ESP_ERR_NO_MEM);
    TEST_ASSERT_EQUAL_UINT32(0U, bol_stats_packets_per_message(0U, BOL_TEST_LIMIT_V2));
}
