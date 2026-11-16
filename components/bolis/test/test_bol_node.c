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
 * @file test_bol_node.c
 * @brief Tests of the node state and the positions of a pass (decision
 *        record 2026-11-16-the-arm-and-finish-of-a-receiver-pass.md).
 *
 * The positions of a pass reach the finish of a receiver, and a wrong count
 * there states a loss that the link did not cause. The cases therefore state
 * the payload sizes of the sweep that do not divide the frame budget.
 */

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "unity.h"

#include "bol_node.h"

/** @brief The v2.0 packet payload limit, in bytes. */
#define BOL_TEST_LIMIT_V2 1470U

/** @brief The frames of one pass (thinkbook section 8). */
#define BOL_TEST_FRAMES 2000U

/** @brief The address that the receiver states in its role reply. */
#define BOL_TEST_MAC_TEXT "a1:b2:c3:d4:e5:f6"

/**
 * @brief Returns a condition that every field check accepts.
 */
static bol_node_cell_t bol_test_cell(void)
{
    bol_node_cell_t cell = {
        .cell_id = 12U,
        .channel = 6U,
        .power_set_value = 44U,
        .payload_bytes = 128U,
        .pass = BOL_PASS_BROADCAST,
        .frames = BOL_TEST_FRAMES
    };

    return cell;
}

/**
 * @brief Gives a node the receiver role and one condition.
 */
static void bol_test_arm(bol_node_t *node, uint32_t payload_bytes)
{
    bol_node_cell_t cell = bol_test_cell();

    cell.payload_bytes = payload_bytes;
    bol_node_reset(node);
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_set_role(node, BOL_ROLE_RECEIVER, 7U, NULL));
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_set_cell(node, &cell, BOL_TEST_LIMIT_V2));
}

TEST_CASE("the reader takes a well-formed address", "[bol_node]")
{
    uint8_t mac[BOL_MAC_BYTES];

    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_parse_mac(BOL_TEST_MAC_TEXT, mac));
    TEST_ASSERT_EQUAL_UINT8(0xA1U, mac[0]);
    TEST_ASSERT_EQUAL_UINT8(0xB2U, mac[1]);
    TEST_ASSERT_EQUAL_UINT8(0xC3U, mac[2]);
    TEST_ASSERT_EQUAL_UINT8(0xD4U, mac[3]);
    TEST_ASSERT_EQUAL_UINT8(0xE5U, mac[4]);
    TEST_ASSERT_EQUAL_UINT8(0xF6U, mac[5]);
}

TEST_CASE("the reader takes an address in either letter case", "[bol_node]")
{
    uint8_t upper[BOL_MAC_BYTES];
    uint8_t lower[BOL_MAC_BYTES];

    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_parse_mac("A1:B2:C3:D4:E5:F6", upper));
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_parse_mac("a1:b2:c3:d4:e5:f6", lower));
    TEST_ASSERT_EQUAL_UINT8_ARRAY(lower, upper, BOL_MAC_BYTES);
}

TEST_CASE("the reader rejects an address that is not an address", "[bol_node]")
{
    uint8_t mac[BOL_MAC_BYTES];

    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, bol_node_parse_mac("a1:b2:c3:d4:e5", mac));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, bol_node_parse_mac("a1:b2:c3:d4:e5:f6:a7", mac));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, bol_node_parse_mac("a1-b2-c3-d4-e5-f6", mac));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, bol_node_parse_mac("a1:b2:c3:d4:e5:g6", mac));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, bol_node_parse_mac("", mac));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, bol_node_parse_mac(BOL_TEST_MAC_TEXT, NULL));
}

TEST_CASE("the writer states an address in lowercase", "[bol_node]")
{
    uint8_t mac[BOL_MAC_BYTES];
    char text[BOL_MAC_TEXT_BYTES];

    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_parse_mac("A1:B2:C3:D4:E5:F6", mac));
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_format_mac(mac, text, sizeof(text)));
    TEST_ASSERT_EQUAL_STRING(BOL_TEST_MAC_TEXT, text);
}

TEST_CASE("the writer refuses a buffer that the address does not fit", "[bol_node]")
{
    uint8_t mac[BOL_MAC_BYTES];
    char text[BOL_MAC_TEXT_BYTES];

    (void)memset(mac, 0, sizeof(mac));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_SIZE,
                          bol_node_format_mac(mac, text, BOL_MAC_TEXT_BYTES - 1U));
}

TEST_CASE("the reader takes each role name", "[bol_node]")
{
    bol_role_t role = BOL_ROLE_NONE;

    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_parse_role("sender", &role));
    TEST_ASSERT_EQUAL_INT(BOL_ROLE_SENDER, role);
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_parse_role("receiver", &role));
    TEST_ASSERT_EQUAL_INT(BOL_ROLE_RECEIVER, role);
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, bol_node_parse_role("listener", &role));
    TEST_ASSERT_EQUAL_STRING("sender", bol_node_role_name(BOL_ROLE_SENDER));
    TEST_ASSERT_EQUAL_STRING("receiver", bol_node_role_name(BOL_ROLE_RECEIVER));
}

TEST_CASE("the reader takes each pass name", "[bol_node]")
{
    bol_pass_t pass = BOL_PASS_UNICAST;

    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_parse_pass("broadcast", &pass));
    TEST_ASSERT_EQUAL_INT(BOL_PASS_BROADCAST, pass);
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_parse_pass("unicast", &pass));
    TEST_ASSERT_EQUAL_INT(BOL_PASS_UNICAST, pass);
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, bol_node_parse_pass("multicast", &pass));
    TEST_ASSERT_EQUAL_STRING("broadcast", bol_node_pass_name(BOL_PASS_BROADCAST));
    TEST_ASSERT_EQUAL_STRING("unicast", bol_node_pass_name(BOL_PASS_UNICAST));
}

TEST_CASE("a sender takes the address of its peer", "[bol_node]")
{
    bol_node_t node;
    uint8_t mac[BOL_MAC_BYTES];

    bol_node_reset(&node);
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_parse_mac(BOL_TEST_MAC_TEXT, mac));
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_set_role(&node, BOL_ROLE_SENDER, 9U, mac));
    TEST_ASSERT_TRUE(node.has_peer);
    TEST_ASSERT_EQUAL_UINT32(9U, node.run_id);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(mac, node.peer_mac, BOL_MAC_BYTES);
}

TEST_CASE("a sender without an address takes no role", "[bol_node]")
{
    bol_node_t node;

    bol_node_reset(&node);
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          bol_node_set_role(&node, BOL_ROLE_SENDER, 9U, NULL));
    TEST_ASSERT_EQUAL_INT(BOL_ROLE_NONE, node.role);
}

TEST_CASE("a receiver takes no address", "[bol_node]")
{
    bol_node_t node;

    bol_node_reset(&node);
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_set_role(&node, BOL_ROLE_RECEIVER, 9U, NULL));
    TEST_ASSERT_FALSE(node.has_peer);
    TEST_ASSERT_EQUAL_INT(BOL_ROLE_RECEIVER, node.role);
}

TEST_CASE("a node takes no role of none", "[bol_node]")
{
    bol_node_t node;

    bol_node_reset(&node);
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          bol_node_set_role(&node, BOL_ROLE_NONE, 9U, NULL));
}

TEST_CASE("a role command clears the condition of the run before it", "[bol_node]")
{
    bol_node_t node;

    bol_test_arm(&node, 128U);
    TEST_ASSERT_TRUE(node.has_cell);
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_set_role(&node, BOL_ROLE_RECEIVER, 11U, NULL));
    TEST_ASSERT_FALSE(node.has_cell);
    TEST_ASSERT_EQUAL_UINT32(11U, node.run_id);
}

TEST_CASE("a cell command before a role command names an error", "[bol_node]")
{
    bol_node_t node;
    const bol_node_cell_t cell = bol_test_cell();

    bol_node_reset(&node);
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_STATE,
                          bol_node_set_cell(&node, &cell, BOL_TEST_LIMIT_V2));
}

TEST_CASE("a condition outside its range names an error", "[bol_node]")
{
    bol_node_t node;
    bol_node_cell_t cell = bol_test_cell();

    bol_node_reset(&node);
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_set_role(&node, BOL_ROLE_RECEIVER, 7U, NULL));

    cell = bol_test_cell();
    cell.cell_id = (uint16_t)(BOL_FRAME_CELL_ID_MAX + 1U);
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          bol_node_set_cell(&node, &cell, BOL_TEST_LIMIT_V2));

    cell = bol_test_cell();
    cell.payload_bytes = BOL_FRAME_HEADER_BYTES - 1U;
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          bol_node_set_cell(&node, &cell, BOL_TEST_LIMIT_V2));

    cell = bol_test_cell();
    cell.frames = 0U;
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          bol_node_set_cell(&node, &cell, BOL_TEST_LIMIT_V2));

    cell = bol_test_cell();
    cell.channel = 256U;
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          bol_node_set_cell(&node, &cell, BOL_TEST_LIMIT_V2));

    cell = bol_test_cell();
    cell.power_set_value = 128U;
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          bol_node_set_cell(&node, &cell, BOL_TEST_LIMIT_V2));

    cell = bol_test_cell();
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, bol_node_set_cell(&node, &cell, 0U));
}

TEST_CASE("a payload at the limit takes one packet per message", "[bol_node]")
{
    bol_node_t node;

    bol_test_arm(&node, BOL_TEST_LIMIT_V2);
    TEST_ASSERT_EQUAL_UINT32(1U, node.packets_per_message);
}

TEST_CASE("a payload above the limit takes the packets of its fragments", "[bol_node]")
{
    bol_node_t node;

    bol_test_arm(&node, BOL_TEST_LIMIT_V2 + 1U);
    TEST_ASSERT_EQUAL_UINT32(2U, node.packets_per_message);

    bol_test_arm(&node, 2941U);
    TEST_ASSERT_EQUAL_UINT32(3U, node.packets_per_message);
}

TEST_CASE("a budget that the message divides states every frame", "[bol_node]")
{
    bol_node_t node;
    uint32_t positions = 0U;

    bol_test_arm(&node, BOL_TEST_LIMIT_V2);
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_positions(&node, &positions));
    TEST_ASSERT_EQUAL_UINT32(BOL_TEST_FRAMES, positions);

    bol_test_arm(&node, BOL_TEST_LIMIT_V2 + 1U);
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_positions(&node, &positions));
    TEST_ASSERT_EQUAL_UINT32(BOL_TEST_FRAMES, positions);
}

TEST_CASE("a budget that the message does not divide falls short of it", "[bol_node]")
{
    bol_node_t node;
    uint32_t positions = 0U;

    // A pass sends whole messages only, so a budget of 2000 packets at three
    // packets per message puts 666 messages, or 1998 packets, on the air.
    bol_test_arm(&node, 2941U);
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_positions(&node, &positions));
    TEST_ASSERT_EQUAL_UINT32(1998U, positions);
    TEST_ASSERT_TRUE(positions < BOL_TEST_FRAMES);
    TEST_ASSERT_TRUE((BOL_TEST_FRAMES - positions) < node.packets_per_message);
}

TEST_CASE("the positions of a node without a condition name an error", "[bol_node]")
{
    bol_node_t node;
    uint32_t positions = 0U;

    bol_node_reset(&node);
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_STATE, bol_node_positions(&node, &positions));
}

TEST_CASE("a command of another cell or another pass names an error", "[bol_node]")
{
    bol_node_t node;

    bol_test_arm(&node, 128U);
    TEST_ASSERT_EQUAL_INT(ESP_OK, bol_node_check_cell(&node, 12U, BOL_PASS_BROADCAST));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_STATE,
                          bol_node_check_cell(&node, 13U, BOL_PASS_BROADCAST));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_STATE,
                          bol_node_check_cell(&node, 12U, BOL_PASS_UNICAST));

    bol_node_reset(&node);
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_STATE,
                          bol_node_check_cell(&node, 12U, BOL_PASS_BROADCAST));
}
