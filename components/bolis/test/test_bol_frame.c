/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * The TEST_CASE macro of unity builds the name of each generated function from
 * __LINE__, so a case at one line number collides with a case at the same line
 * number in another test file. The collision comes from the expansion of an
 * adopted macro, which deviation D-002 covers. A suppression on one line would
 * move the collision to the next matching line rather than remove it, because
 * the added line shifts every case below it.
 */
/* cppcheck-suppress-file misra-c2012-5.9 */

/**
 * @file test_bol_frame.c
 * @brief Tests of the frame header and the fill (decision record
 *        2026-11-12-frame-header-encoding.md).
 *
 * A received frame is untrusted, so every test states what the decoder does
 * with bytes that the contract does not allow. The byte order, the magic, the
 * pass bit, and the fill each bind every released image, so each one has a
 * test that states its value rather than reading it back from the encoder.
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "unity.h"

#include "bol_frame.h"

/** @brief A frame long enough to carry a header and some fill. */
#define BOL_TEST_FRAME_BYTES 32U

/** @brief The run ID that the cases encode, with four distinct bytes. */
#define BOL_TEST_RUN_ID 0x01020304U

/** @brief The message ID that the cases encode, with four distinct bytes. */
#define BOL_TEST_MESSAGE_ID 0x0A0B0C0DU

/** @brief The cell that the cases encode. */
#define BOL_TEST_CELL_ID 300U

/**
 * @brief Builds the header that most cases encode.
 */
static bol_frame_header_t test_header(void)
{
    bol_frame_header_t header;

    header.run_id = BOL_TEST_RUN_ID;
    header.cell_id = (uint16_t)BOL_TEST_CELL_ID;
    header.pass = BOL_PASS_BROADCAST;
    header.message_id = BOL_TEST_MESSAGE_ID;
    header.fragment_index = 1U;
    header.fragment_count = 3U;

    return header;
}

TEST_CASE("the header measures fourteen bytes", "[bol_frame]")
{
    TEST_ASSERT_EQUAL_UINT(14U, BOL_FRAME_HEADER_BYTES);
}

TEST_CASE("the encoder writes the magic first", "[bol_frame]")
{
    const bol_frame_header_t header = test_header();
    uint8_t frame[BOL_TEST_FRAME_BYTES];

    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_frame_encode(&header, frame, sizeof(frame)));
    TEST_ASSERT_EQUAL_HEX8(0x42, frame[0]);
    TEST_ASSERT_EQUAL_HEX8(0x4F, frame[1]);
}

TEST_CASE("every multi-byte field is big-endian", "[bol_frame]")
{
    const bol_frame_header_t header = test_header();
    uint8_t frame[BOL_TEST_FRAME_BYTES];

    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_frame_encode(&header, frame, sizeof(frame)));

    /* The run ID reads in field order, most significant byte first. */
    TEST_ASSERT_EQUAL_HEX8(0x01, frame[2]);
    TEST_ASSERT_EQUAL_HEX8(0x02, frame[3]);
    TEST_ASSERT_EQUAL_HEX8(0x03, frame[4]);
    TEST_ASSERT_EQUAL_HEX8(0x04, frame[5]);

    /* The message ID reads the same way. */
    TEST_ASSERT_EQUAL_HEX8(0x0A, frame[8]);
    TEST_ASSERT_EQUAL_HEX8(0x0B, frame[9]);
    TEST_ASSERT_EQUAL_HEX8(0x0C, frame[10]);
    TEST_ASSERT_EQUAL_HEX8(0x0D, frame[11]);
}

TEST_CASE("the top bit of the cell field holds zero for a broadcast pass", "[bol_frame]")
{
    bol_frame_header_t header = test_header();
    uint8_t frame[BOL_TEST_FRAME_BYTES];

    header.pass = BOL_PASS_BROADCAST;
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_frame_encode(&header, frame, sizeof(frame)));
    TEST_ASSERT_EQUAL_HEX8(0x01, frame[6]);
    TEST_ASSERT_EQUAL_HEX8(0x2C, frame[7]);
}

TEST_CASE("the top bit of the cell field holds one for a unicast pass", "[bol_frame]")
{
    bol_frame_header_t header = test_header();
    uint8_t frame[BOL_TEST_FRAME_BYTES];

    header.pass = BOL_PASS_UNICAST;
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_frame_encode(&header, frame, sizeof(frame)));
    TEST_ASSERT_EQUAL_HEX8(0x81, frame[6]);
}

TEST_CASE("the fragment index and the count take one byte each", "[bol_frame]")
{
    const bol_frame_header_t header = test_header();
    uint8_t frame[BOL_TEST_FRAME_BYTES];

    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_frame_encode(&header, frame, sizeof(frame)));
    TEST_ASSERT_EQUAL_HEX8(1U, frame[12]);
    TEST_ASSERT_EQUAL_HEX8(3U, frame[13]);
}

TEST_CASE("the decoder reads back every field that the encoder wrote", "[bol_frame]")
{
    bol_frame_header_t header = test_header();
    bol_frame_header_t read;
    uint8_t frame[BOL_TEST_FRAME_BYTES];

    header.pass = BOL_PASS_UNICAST;
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_frame_encode(&header, frame, sizeof(frame)));
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_frame_decode(frame, sizeof(frame), &read));

    TEST_ASSERT_EQUAL_UINT32(header.run_id, read.run_id);
    TEST_ASSERT_EQUAL_UINT16(header.cell_id, read.cell_id);
    TEST_ASSERT_EQUAL_INT(BOL_PASS_UNICAST, read.pass);
    TEST_ASSERT_EQUAL_UINT32(header.message_id, read.message_id);
    TEST_ASSERT_EQUAL_UINT8(header.fragment_index, read.fragment_index);
    TEST_ASSERT_EQUAL_UINT8(header.fragment_count, read.fragment_count);
}

TEST_CASE("the widest cell leaves the pass bit alone", "[bol_frame]")
{
    bol_frame_header_t header = test_header();
    bol_frame_header_t read;
    uint8_t frame[BOL_TEST_FRAME_BYTES];

    header.cell_id = (uint16_t)BOL_FRAME_CELL_ID_MAX;
    header.pass = BOL_PASS_BROADCAST;
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_frame_encode(&header, frame, sizeof(frame)));
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_frame_decode(frame, sizeof(frame), &read));

    TEST_ASSERT_EQUAL_UINT16(BOL_FRAME_CELL_ID_MAX, read.cell_id);
    TEST_ASSERT_EQUAL_INT(BOL_PASS_BROADCAST, read.pass);
}

TEST_CASE("a cell above its range reaches no frame", "[bol_frame]")
{
    bol_frame_header_t header = test_header();
    uint8_t frame[BOL_TEST_FRAME_BYTES];

    header.cell_id = (uint16_t)(BOL_FRAME_CELL_ID_MAX + 1U);

    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          bol_frame_encode(&header, frame, sizeof(frame)));
}

TEST_CASE("a buffer shorter than the header draws a size error", "[bol_frame]")
{
    const bol_frame_header_t header = test_header();
    uint8_t frame[BOL_FRAME_HEADER_BYTES];

    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_SIZE,
                          bol_frame_encode(&header, frame, BOL_FRAME_HEADER_BYTES - 1U));
}

TEST_CASE("a frame shorter than the header decodes to a size error", "[bol_frame]")
{
    uint8_t frame[BOL_FRAME_HEADER_BYTES];
    bol_frame_header_t read;

    (void)memset(frame, 0, sizeof(frame));

    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_SIZE,
                          bol_frame_decode(frame, BOL_FRAME_HEADER_BYTES - 1U, &read));
}

TEST_CASE("a frame of another sender draws a not found error", "[bol_frame]")
{
    const bol_frame_header_t header = test_header();
    uint8_t frame[BOL_TEST_FRAME_BYTES];
    bol_frame_header_t read;

    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_frame_encode(&header, frame, sizeof(frame)));
    frame[0] = 0x00U;

    TEST_ASSERT_EQUAL_INT(ESP_ERR_NOT_FOUND,
                          bol_frame_decode(frame, sizeof(frame), &read));
}

TEST_CASE("an erased buffer is not a Bolis frame", "[bol_frame]")
{
    uint8_t frame[BOL_TEST_FRAME_BYTES];
    bol_frame_header_t read;

    (void)memset(frame, 0xFF, sizeof(frame));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_NOT_FOUND,
                          bol_frame_decode(frame, sizeof(frame), &read));

    (void)memset(frame, 0x00, sizeof(frame));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_NOT_FOUND,
                          bol_frame_decode(frame, sizeof(frame), &read));
}

TEST_CASE("a NULL pointer draws an argument error", "[bol_frame]")
{
    const bol_frame_header_t header = test_header();
    uint8_t frame[BOL_TEST_FRAME_BYTES];
    bol_frame_header_t read;

    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          bol_frame_encode(NULL, frame, sizeof(frame)));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          bol_frame_encode(&header, NULL, sizeof(frame)));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          bol_frame_decode(NULL, sizeof(frame), &read));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          bol_frame_decode(frame, sizeof(frame), NULL));
}

TEST_CASE("the fill counts up from the seed of its frame", "[bol_frame]")
{
    const bol_frame_header_t header = test_header();
    uint8_t frame[BOL_TEST_FRAME_BYTES];
    const uint8_t seed = (uint8_t)((BOL_TEST_MESSAGE_ID + 1U) % 256U);

    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_frame_encode(&header, frame, sizeof(frame)));

    TEST_ASSERT_EQUAL_HEX8(seed, frame[BOL_FRAME_HEADER_BYTES]);
    TEST_ASSERT_EQUAL_HEX8((uint8_t)(seed + 1U), frame[BOL_FRAME_HEADER_BYTES + 1U]);
    TEST_ASSERT_EQUAL_HEX8((uint8_t)(seed + 2U), frame[BOL_FRAME_HEADER_BYTES + 2U]);
}

TEST_CASE("the fill of a whole frame passes its check", "[bol_frame]")
{
    const bol_frame_header_t header = test_header();
    uint8_t frame[BOL_TEST_FRAME_BYTES];

    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_frame_encode(&header, frame, sizeof(frame)));
    TEST_ASSERT_TRUE(bol_frame_fill_is_intact(&header, frame, sizeof(frame)));
}

TEST_CASE("a change to any fill byte fails the check", "[bol_frame]")
{
    const bol_frame_header_t header = test_header();
    uint8_t frame[BOL_TEST_FRAME_BYTES];
    size_t offset = BOL_FRAME_HEADER_BYTES;

    while (offset < BOL_TEST_FRAME_BYTES) {
        TEST_ASSERT_EQUAL_INT(ESP_OK, bol_frame_encode(&header, frame, sizeof(frame)));
        frame[offset] = (uint8_t)(frame[offset] ^ 0xFFU);
        TEST_ASSERT_FALSE(bol_frame_fill_is_intact(&header, frame, sizeof(frame)));
        offset++;
    }
}

TEST_CASE("a truncated frame fails the check of its stated length", "[bol_frame]")
{
    const bol_frame_header_t header = test_header();
    uint8_t frame[BOL_TEST_FRAME_BYTES];

    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_frame_encode(&header, frame, sizeof(frame)));
    (void)memset(&frame[BOL_TEST_FRAME_BYTES - 4U], 0, 4U);

    TEST_ASSERT_FALSE(bol_frame_fill_is_intact(&header, frame, sizeof(frame)));
}

TEST_CASE("a frame of the smallest payload holds a header and no fill", "[bol_frame]")
{
    const bol_frame_header_t header = test_header();
    uint8_t frame[BOL_FRAME_HEADER_BYTES];

    TEST_ASSERT_EQUAL_INT(ESP_OK,
                          bol_frame_encode(&header, frame, BOL_FRAME_HEADER_BYTES));
    TEST_ASSERT_TRUE(bol_frame_fill_is_intact(&header, frame, BOL_FRAME_HEADER_BYTES));
}

TEST_CASE("the fill of two fragments of one message differs", "[bol_frame]")
{
    bol_frame_header_t first = test_header();
    bol_frame_header_t second = test_header();
    uint8_t frame_first[BOL_TEST_FRAME_BYTES];
    uint8_t frame_second[BOL_TEST_FRAME_BYTES];

    first.fragment_index = 0U;
    second.fragment_index = 1U;

    TEST_ASSERT_EQUAL_INT(ESP_OK,
                          bol_frame_encode(&first, frame_first, sizeof(frame_first)));
    TEST_ASSERT_EQUAL_INT(ESP_OK,
                          bol_frame_encode(&second, frame_second, sizeof(frame_second)));

    TEST_ASSERT_NOT_EQUAL_UINT8(frame_first[BOL_FRAME_HEADER_BYTES],
                                frame_second[BOL_FRAME_HEADER_BYTES]);
}
