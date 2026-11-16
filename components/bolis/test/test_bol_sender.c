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
 * @file test_bol_sender.c
 * @brief Tests of the sending loop and the frame sizes of a message
 *        (decision records 2026-11-13-the-sending-loop-of-a-pass.md and
 *        2026-11-16-the-mapping-of-a-message-to-its-frames.md).
 *
 * The frame sizes bind every run that a corpus stores, so the cases state the
 * sizes of the fragmentation record rather than reading them back from the
 * module. A fake port stands in for the radio and the clock, so the loop runs
 * on the host.
 */

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "unity.h"

#include "bol_sender.h"

/** @brief The v2.0 packet payload limit, in bytes. */
#define BOL_TEST_LIMIT_V2 1470U

/** @brief The v1.0 packet payload limit, in bytes. */
#define BOL_TEST_LIMIT_V1 250U

/** @brief The frames of one pass (thinkbook section 8). */
#define BOL_TEST_FRAMES 2000U

/** @brief The airtime of a 14-byte frame, in microseconds (thinkbook 3.3). */
#define BOL_TEST_AIRTIME_14_US 648U

/** @brief A code that the fake radio returns when it holds no buffer. */
#define BOL_TEST_NO_MEM 0x3064

/** @brief A code that the fake radio returns for a failure that no retry fixes. */
#define BOL_TEST_OTHER_ERROR 0x3065

/** @brief The state that the fake port holds between its calls. */
typedef struct {
    uint32_t send_calls;          /*!< The sends that the loop made. */
    uint32_t await_calls;         /*!< The callbacks that the loop waited for. */
    uint32_t wait_calls;          /*!< The waits that a no-memory error caused. */
    uint32_t progress_calls;      /*!< The progress replies that the loop asked for. */
    uint32_t last_progress_frames; /*!< The frames that the last progress reply stated. */
    esp_err_t send_result;        /*!< The code that a failing send returns. */
    uint32_t failures_left;       /*!< The sends that fail before one succeeds. */
    uint32_t now_ms;              /*!< The clock of the fake node. */
    uint32_t advance_ms;          /*!< The milliseconds that each send takes. */
    bool callback_is_ok;          /*!< The result that each callback reports. */
    uint32_t callback_us;         /*!< The time that each callback reports. */
    uint32_t total_frame_bytes;   /*!< The bytes of every frame that reached the air. */
    uint32_t last_frame_bytes;    /*!< The bytes of the last frame that reached it. */
} bol_test_port_ctx_t;

static esp_err_t bol_test_send(void *context, const uint8_t *frame, size_t frame_bytes)
{
    // cppcheck-suppress misra-c2012-11.5 ; the port passes its context as void *
    bol_test_port_ctx_t *ctx = (bol_test_port_ctx_t *)context;
    esp_err_t ret = ESP_OK;

    (void)frame;
    ctx->send_calls++;
    ctx->now_ms += ctx->advance_ms;

    if (ctx->failures_left > 0U) {
        ctx->failures_left--;
        ret = ctx->send_result;
    } else {
        ctx->last_frame_bytes = (uint32_t)frame_bytes;
        ctx->total_frame_bytes += (uint32_t)frame_bytes;
    }

    return ret;
}

static esp_err_t bol_test_await(void *context, bool *out_is_ok, uint32_t *out_microseconds)
{
    // cppcheck-suppress misra-c2012-11.5 ; the port passes its context as void *
    bol_test_port_ctx_t *ctx = (bol_test_port_ctx_t *)context;

    ctx->await_calls++;
    *out_is_ok = ctx->callback_is_ok;
    *out_microseconds = ctx->callback_us;

    return ESP_OK;
}

static void bol_test_wait_ms(void *context, uint32_t milliseconds)
{
    // cppcheck-suppress misra-c2012-11.5 ; the port passes its context as void *
    bol_test_port_ctx_t *ctx = (bol_test_port_ctx_t *)context;

    ctx->wait_calls++;
    ctx->now_ms += milliseconds;
}

static uint32_t bol_test_now_ms(void *context)
{
    // cppcheck-suppress misra-c2012-11.5 ; the port passes its context as void *
    const bol_test_port_ctx_t *ctx = (const bol_test_port_ctx_t *)context;

    return ctx->now_ms;
}

static void bol_test_progress(void *context, uint32_t frames_sent)
{
    // cppcheck-suppress misra-c2012-11.5 ; the port passes its context as void *
    bol_test_port_ctx_t *ctx = (bol_test_port_ctx_t *)context;

    ctx->progress_calls++;
    ctx->last_progress_frames = frames_sent;
}

/**
 * @brief Clears the state of the fake port and gives it a working radio.
 */
static void bol_test_ctx_reset(bol_test_port_ctx_t *ctx)
{
    (void)memset(ctx, 0, sizeof(*ctx));
    ctx->send_result = BOL_TEST_NO_MEM;
    ctx->callback_is_ok = true;
    ctx->callback_us = BOL_TEST_AIRTIME_14_US;
}

/**
 * @brief Returns a port that reaches the fake radio and the fake clock.
 */
static bol_sender_port_t bol_test_port(bol_test_port_ctx_t *ctx)
{
    bol_sender_port_t port = {
        .send = bol_test_send,
        .await_callback = bol_test_await,
        .wait_ms = bol_test_wait_ms,
        .now_ms = bol_test_now_ms,
        .progress = bol_test_progress,
        .no_mem_code = BOL_TEST_NO_MEM,
        .context = ctx
    };

    return port;
}

/**
 * @brief Returns a pass of one payload, with the buffer that the loop fills.
 */
static bol_sender_pass_t bol_test_pass(uint8_t *frame, size_t capacity_bytes,
                                       uint32_t payload_bytes, uint32_t limit_bytes,
                                       uint32_t frames)
{
    bol_sender_pass_t pass = {
        .run_id = 7U,
        .cell_id = 12U,
        .pass = BOL_PASS_BROADCAST,
        .frames = frames,
        .payload_bytes = payload_bytes,
        .payload_limit_bytes = limit_bytes,
        .frame = frame,
        .frame_capacity_bytes = capacity_bytes
    };

    return pass;
}

/**
 * @brief States the bytes of one frame of a message.
 */
static uint32_t bol_test_frame_bytes(uint32_t payload_bytes, uint32_t limit_bytes,
                                     uint32_t fragment_index)
{
    uint32_t frame_bytes = 0U;

    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_sender_frame_bytes(payload_bytes, limit_bytes,
                                                         fragment_index, &frame_bytes));
    return frame_bytes;
}

TEST_CASE("a message of one frame holds every byte of its payload", "[bol_sender]")
{
    TEST_ASSERT_EQUAL_UINT32(14U, bol_test_frame_bytes(14U, BOL_TEST_LIMIT_V2, 0U));
    TEST_ASSERT_EQUAL_UINT32(1470U, bol_test_frame_bytes(1470U, BOL_TEST_LIMIT_V2, 0U));
    TEST_ASSERT_EQUAL_UINT32(250U, bol_test_frame_bytes(250U, BOL_TEST_LIMIT_V1, 0U));
}

TEST_CASE("the frames of a message divide it as evenly as they can", "[bol_sender]")
{
    // The fragmentation record states each row of this table.
    TEST_ASSERT_EQUAL_UINT32(736U, bol_test_frame_bytes(1471U, BOL_TEST_LIMIT_V2, 0U));
    TEST_ASSERT_EQUAL_UINT32(735U, bol_test_frame_bytes(1471U, BOL_TEST_LIMIT_V2, 1U));

    TEST_ASSERT_EQUAL_UINT32(981U, bol_test_frame_bytes(2941U, BOL_TEST_LIMIT_V2, 0U));
    TEST_ASSERT_EQUAL_UINT32(980U, bol_test_frame_bytes(2941U, BOL_TEST_LIMIT_V2, 1U));
    TEST_ASSERT_EQUAL_UINT32(980U, bol_test_frame_bytes(2941U, BOL_TEST_LIMIT_V2, 2U));

    TEST_ASSERT_EQUAL_UINT32(126U, bol_test_frame_bytes(251U, BOL_TEST_LIMIT_V1, 0U));
    TEST_ASSERT_EQUAL_UINT32(125U, bol_test_frame_bytes(251U, BOL_TEST_LIMIT_V1, 1U));

    TEST_ASSERT_EQUAL_UINT32(167U, bol_test_frame_bytes(501U, BOL_TEST_LIMIT_V1, 0U));
    TEST_ASSERT_EQUAL_UINT32(167U, bol_test_frame_bytes(501U, BOL_TEST_LIMIT_V1, 1U));
    TEST_ASSERT_EQUAL_UINT32(167U, bol_test_frame_bytes(501U, BOL_TEST_LIMIT_V1, 2U));
}

TEST_CASE("every frame of a message holds its header", "[bol_sender]")
{
    static const uint32_t payloads_v2[] = {14U, 250U, 251U, 1469U, 1470U, 1471U, 2940U, 2941U};
    static const uint32_t payloads_v1[] = {14U, 128U, 249U, 250U, 251U, 499U, 500U, 501U};
    size_t index = 0U;

    while (index < (sizeof(payloads_v2) / sizeof(payloads_v2[0]))) {
        const uint32_t payload = payloads_v2[index];
        const uint32_t packets = (payload + BOL_TEST_LIMIT_V2 - 1U) / BOL_TEST_LIMIT_V2;
        uint32_t fragment = 0U;
        uint32_t total = 0U;

        while (fragment < packets) {
            const uint32_t bytes = bol_test_frame_bytes(payload, BOL_TEST_LIMIT_V2, fragment);

            TEST_ASSERT_TRUE(bytes >= BOL_FRAME_HEADER_BYTES);
            TEST_ASSERT_TRUE(bytes <= BOL_TEST_LIMIT_V2);
            total += bytes;
            fragment++;
        }

        TEST_ASSERT_EQUAL_UINT32(payload, total);
        index++;
    }

    index = 0U;
    while (index < (sizeof(payloads_v1) / sizeof(payloads_v1[0]))) {
        const uint32_t payload = payloads_v1[index];
        const uint32_t packets = (payload + BOL_TEST_LIMIT_V1 - 1U) / BOL_TEST_LIMIT_V1;
        uint32_t fragment = 0U;
        uint32_t total = 0U;

        while (fragment < packets) {
            const uint32_t bytes = bol_test_frame_bytes(payload, BOL_TEST_LIMIT_V1, fragment);

            TEST_ASSERT_TRUE(bytes >= BOL_FRAME_HEADER_BYTES);
            TEST_ASSERT_TRUE(bytes <= BOL_TEST_LIMIT_V1);
            total += bytes;
            fragment++;
        }

        TEST_ASSERT_EQUAL_UINT32(payload, total);
        index++;
    }
}

TEST_CASE("a fragment outside the message names an error", "[bol_sender]")
{
    uint32_t frame_bytes = 0U;

    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          bol_sender_frame_bytes(1471U, BOL_TEST_LIMIT_V2, 2U, &frame_bytes));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          bol_sender_frame_bytes(14U, BOL_TEST_LIMIT_V2, 1U, &frame_bytes));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          bol_sender_frame_bytes(14U, 0U, 0U, &frame_bytes));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          bol_sender_frame_bytes(14U, BOL_TEST_LIMIT_V2, 0U, NULL));
}

TEST_CASE("a pass of one frame per message reaches its budget", "[bol_sender]")
{
    uint8_t frame[BOL_TEST_LIMIT_V2];
    bol_test_port_ctx_t ctx;
    bol_sender_counters_t counters;
    const bol_sender_port_t port = bol_test_port(&ctx);
    const bol_sender_pass_t pass = bol_test_pass(frame, sizeof(frame), BOL_TEST_LIMIT_V2,
                                                 BOL_TEST_LIMIT_V2, BOL_TEST_FRAMES);

    bol_test_ctx_reset(&ctx);
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_sender_run_pass(&port, &pass, &counters));
    TEST_ASSERT_EQUAL_UINT32(BOL_TEST_FRAMES, counters.packets_sent);
    TEST_ASSERT_EQUAL_UINT32(BOL_TEST_FRAMES, counters.messages_sent);
    TEST_ASSERT_EQUAL_UINT32(BOL_TEST_FRAMES, counters.callback_ok);
    TEST_ASSERT_EQUAL_UINT32(0U, counters.dropped_packets);
}

TEST_CASE("a pass sends whole messages and falls short of its budget", "[bol_sender]")
{
    uint8_t frame[BOL_TEST_LIMIT_V2];
    bol_test_port_ctx_t ctx;
    bol_sender_counters_t counters;
    const bol_sender_port_t port = bol_test_port(&ctx);
    const bol_sender_pass_t pass = bol_test_pass(frame, sizeof(frame), 2941U, BOL_TEST_LIMIT_V2,
                                                 BOL_TEST_FRAMES);

    bol_test_ctx_reset(&ctx);
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_sender_run_pass(&port, &pass, &counters));

    // A budget of 2000 packets at three packets per message carries 666 whole
    // messages, which is 1998 packets.
    TEST_ASSERT_EQUAL_UINT32(666U, counters.messages_sent);
    TEST_ASSERT_EQUAL_UINT32(1998U, counters.packets_sent);
    TEST_ASSERT_TRUE(counters.packets_sent < BOL_TEST_FRAMES);

    // Every frame of every message reached the air, so the bytes equal the
    // payload of each message.
    TEST_ASSERT_EQUAL_UINT32(666U * 2941U, ctx.total_frame_bytes);
}

TEST_CASE("a message of two frames puts both of them on the air", "[bol_sender]")
{
    uint8_t frame[BOL_TEST_LIMIT_V2];
    bol_test_port_ctx_t ctx;
    bol_sender_counters_t counters;
    const bol_sender_port_t port = bol_test_port(&ctx);
    const bol_sender_pass_t pass = bol_test_pass(frame, sizeof(frame), 1471U, BOL_TEST_LIMIT_V2,
                                                 BOL_TEST_FRAMES);

    bol_test_ctx_reset(&ctx);
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_sender_run_pass(&port, &pass, &counters));
    TEST_ASSERT_EQUAL_UINT32(1000U, counters.messages_sent);
    TEST_ASSERT_EQUAL_UINT32(BOL_TEST_FRAMES, counters.packets_sent);
    TEST_ASSERT_EQUAL_UINT32(1000U * 1471U, ctx.total_frame_bytes);
    TEST_ASSERT_EQUAL_UINT32(735U, ctx.last_frame_bytes);
}

TEST_CASE("the callback time of each frame reaches its bin", "[bol_sender]")
{
    uint8_t frame[BOL_TEST_LIMIT_V2];
    bol_test_port_ctx_t ctx;
    bol_sender_counters_t counters;
    const bol_sender_port_t port = bol_test_port(&ctx);
    const bol_sender_pass_t pass = bol_test_pass(frame, sizeof(frame), 14U, BOL_TEST_LIMIT_V2,
                                                 4U);

    bol_test_ctx_reset(&ctx);
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_sender_run_pass(&port, &pass, &counters));

    // The sending loop record places the airtime of a 14-byte frame in bin 4.
    TEST_ASSERT_EQUAL_UINT32(4U, counters.send_to_callback_us_histogram[4]);
    TEST_ASSERT_EQUAL_UINT32(4U, counters.callback_ok);
    TEST_ASSERT_EQUAL_UINT32(0U, counters.callback_failed);
}

TEST_CASE("a no-memory error waits and sends that packet again", "[bol_sender]")
{
    uint8_t frame[BOL_TEST_LIMIT_V2];
    bol_test_port_ctx_t ctx;
    bol_sender_counters_t counters;
    const bol_sender_port_t port = bol_test_port(&ctx);
    const bol_sender_pass_t pass = bol_test_pass(frame, sizeof(frame), 14U, BOL_TEST_LIMIT_V2,
                                                 1U);

    bol_test_ctx_reset(&ctx);
    ctx.failures_left = 3U;
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_sender_run_pass(&port, &pass, &counters));

    TEST_ASSERT_EQUAL_UINT32(3U, counters.no_mem_events);
    TEST_ASSERT_EQUAL_UINT32(3U, ctx.wait_calls);
    TEST_ASSERT_EQUAL_UINT32(4U, ctx.send_calls);
    TEST_ASSERT_EQUAL_UINT32(1U, counters.packets_sent);
    TEST_ASSERT_EQUAL_UINT32(1U, counters.messages_sent);
    TEST_ASSERT_EQUAL_UINT32(0U, counters.dropped_packets);
}

TEST_CASE("a packet that every attempt fails counts under its code", "[bol_sender]")
{
    uint8_t frame[BOL_TEST_LIMIT_V2];
    bol_test_port_ctx_t ctx;
    bol_sender_counters_t counters;
    const bol_sender_port_t port = bol_test_port(&ctx);
    const bol_sender_pass_t pass = bol_test_pass(frame, sizeof(frame), 14U, BOL_TEST_LIMIT_V2,
                                                 1U);

    bol_test_ctx_reset(&ctx);
    ctx.failures_left = UINT32_MAX;
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_sender_run_pass(&port, &pass, &counters));

    TEST_ASSERT_EQUAL_UINT32(BOL_SENDER_ATTEMPTS, ctx.send_calls);
    TEST_ASSERT_EQUAL_UINT32(BOL_SENDER_ATTEMPTS, counters.no_mem_events);
    TEST_ASSERT_EQUAL_UINT32(BOL_SENDER_ATTEMPTS - 1U, ctx.wait_calls);
    TEST_ASSERT_EQUAL_UINT32(0U, counters.packets_sent);
    TEST_ASSERT_EQUAL_UINT32(0U, counters.messages_sent);
    TEST_ASSERT_EQUAL_UINT32(1U, counters.dropped_packets);
    TEST_ASSERT_EQUAL_UINT32(1U, counters.send_error_kinds);
    TEST_ASSERT_EQUAL_INT(BOL_TEST_NO_MEM, counters.send_errors[0].code);
    TEST_ASSERT_EQUAL_UINT32(1U, counters.send_errors[0].count);
}

TEST_CASE("an error that no retry fixes moves the pass on at once", "[bol_sender]")
{
    uint8_t frame[BOL_TEST_LIMIT_V2];
    bol_test_port_ctx_t ctx;
    bol_sender_counters_t counters;
    const bol_sender_port_t port = bol_test_port(&ctx);
    const bol_sender_pass_t pass = bol_test_pass(frame, sizeof(frame), 14U, BOL_TEST_LIMIT_V2,
                                                 2U);

    bol_test_ctx_reset(&ctx);
    ctx.send_result = BOL_TEST_OTHER_ERROR;
    ctx.failures_left = UINT32_MAX;
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_sender_run_pass(&port, &pass, &counters));

    // One send per packet, with no wait and no second attempt.
    TEST_ASSERT_EQUAL_UINT32(2U, ctx.send_calls);
    TEST_ASSERT_EQUAL_UINT32(0U, ctx.wait_calls);
    TEST_ASSERT_EQUAL_UINT32(0U, counters.no_mem_events);
    TEST_ASSERT_EQUAL_UINT32(2U, counters.dropped_packets);
    TEST_ASSERT_EQUAL_UINT32(1U, counters.send_error_kinds);
    TEST_ASSERT_EQUAL_UINT32(2U, counters.send_errors[0].count);
}

TEST_CASE("a pass longer than the interval writes a progress reply", "[bol_sender]")
{
    uint8_t frame[BOL_TEST_LIMIT_V2];
    bol_test_port_ctx_t ctx;
    bol_sender_counters_t counters;
    const bol_sender_port_t port = bol_test_port(&ctx);
    const bol_sender_pass_t pass = bol_test_pass(frame, sizeof(frame), 14U, BOL_TEST_LIMIT_V2,
                                                 4U);

    bol_test_ctx_reset(&ctx);
    ctx.advance_ms = 600U;
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_sender_run_pass(&port, &pass, &counters));

    // The interval passes after the second frame and again after the fourth.
    TEST_ASSERT_EQUAL_UINT32(2U, ctx.progress_calls);
    TEST_ASSERT_EQUAL_UINT32(4U, ctx.last_progress_frames);
}

TEST_CASE("a pass shorter than the interval writes no progress reply", "[bol_sender]")
{
    uint8_t frame[BOL_TEST_LIMIT_V2];
    bol_test_port_ctx_t ctx;
    bol_sender_counters_t counters;
    const bol_sender_port_t port = bol_test_port(&ctx);
    const bol_sender_pass_t pass = bol_test_pass(frame, sizeof(frame), 14U, BOL_TEST_LIMIT_V2,
                                                 BOL_TEST_FRAMES);

    bol_test_ctx_reset(&ctx);
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_sender_run_pass(&port, &pass, &counters));
    TEST_ASSERT_EQUAL_UINT32(0U, ctx.progress_calls);
}

TEST_CASE("a pass refuses a buffer that a frame does not fit", "[bol_sender]")
{
    uint8_t frame[64];
    bol_test_port_ctx_t ctx;
    bol_sender_counters_t counters;
    const bol_sender_port_t port = bol_test_port(&ctx);
    const bol_sender_pass_t pass = bol_test_pass(frame, sizeof(frame), 250U, BOL_TEST_LIMIT_V2,
                                                 4U);

    bol_test_ctx_reset(&ctx);
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_SIZE, bol_sender_run_pass(&port, &pass, &counters));
}

TEST_CASE("a pass refuses a port that holds no radio", "[bol_sender]")
{
    uint8_t frame[BOL_TEST_LIMIT_V2];
    bol_test_port_ctx_t ctx;
    bol_sender_counters_t counters;
    bol_sender_port_t port = bol_test_port(&ctx);
    const bol_sender_pass_t pass = bol_test_pass(frame, sizeof(frame), 14U, BOL_TEST_LIMIT_V2,
                                                 4U);

    bol_test_ctx_reset(&ctx);
    port.send = NULL;
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, bol_sender_run_pass(&port, &pass, &counters));

    port = bol_test_port(&ctx);
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, bol_sender_run_pass(NULL, &pass, &counters));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, bol_sender_run_pass(&port, NULL, &counters));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, bol_sender_run_pass(&port, &pass, NULL));
}
