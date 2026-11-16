/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file bol_node.c
 * @brief The state that a node holds between control commands (decision
 *        record 2026-11-16-the-arm-and-finish-of-a-receiver-pass.md).
 */

#include <string.h>

#include "bol_node.h"
#include "bol_stats.h"

/** @brief The digits that a MAC address uses in its text. */
static const char s_hex_digits[] = "0123456789abcdef";

/**
 * @brief Returns the value of one hexadecimal digit.
 *
 * @param[in]  digit      The character to read.
 * @param[out] out_value  The value, 0 to 15, written only on success.
 *
 * @return True when the character is a hexadecimal digit.
 */
static bool bol_hex_value(char digit, uint8_t *out_value)
{
    bool is_hex = true;

    if ((digit >= '0') && (digit <= '9')) {
        *out_value = (uint8_t)((uint32_t)digit - (uint32_t)'0');
    } else if ((digit >= 'a') && (digit <= 'f')) {
        *out_value = (uint8_t)(((uint32_t)digit - (uint32_t)'a') + 10U);
    } else if ((digit >= 'A') && (digit <= 'F')) {
        *out_value = (uint8_t)(((uint32_t)digit - (uint32_t)'A') + 10U);
    } else {
        is_hex = false;
    }

    return is_hex;
}

void bol_node_reset(bol_node_t *node)
{
    if (node != NULL) {
        // The clear holds every field defined, and the two assignments name the
        // state that a cleared node holds.
        // The return value of memset is the destination, which the caller already holds.
        (void)memset(node, 0, sizeof(*node));
        node->role = BOL_ROLE_NONE;
        node->cell.pass = BOL_PASS_BROADCAST;
    }
}

esp_err_t bol_node_parse_role(const char *text, bol_role_t *out_role)
{
    esp_err_t ret = ESP_OK;

    if ((text == NULL) || (out_role == NULL)) {
        ret = ESP_ERR_INVALID_ARG;
    } else if (strcmp(text, "sender") == 0) {
        *out_role = BOL_ROLE_SENDER;
    } else if (strcmp(text, "receiver") == 0) {
        *out_role = BOL_ROLE_RECEIVER;
    } else {
        ret = ESP_ERR_INVALID_ARG;
    }

    return ret;
}

const char *bol_node_role_name(bol_role_t role)
{
    const char *name = "";

    switch (role) {
    case BOL_ROLE_SENDER:
        name = "sender";
        break;
    case BOL_ROLE_RECEIVER:
        name = "receiver";
        break;
    case BOL_ROLE_NONE:
    default:
        name = "";
        break;
    }

    return name;
}

esp_err_t bol_node_parse_pass(const char *text, bol_pass_t *out_pass)
{
    esp_err_t ret = ESP_OK;

    if ((text == NULL) || (out_pass == NULL)) {
        ret = ESP_ERR_INVALID_ARG;
    } else if (strcmp(text, "broadcast") == 0) {
        *out_pass = BOL_PASS_BROADCAST;
    } else if (strcmp(text, "unicast") == 0) {
        *out_pass = BOL_PASS_UNICAST;
    } else {
        ret = ESP_ERR_INVALID_ARG;
    }

    return ret;
}

const char *bol_node_pass_name(bol_pass_t pass)
{
    const char *name = "broadcast";

    switch (pass) {
    case BOL_PASS_UNICAST:
        name = "unicast";
        break;
    case BOL_PASS_BROADCAST:
    default:
        name = "broadcast";
        break;
    }

    return name;
}

esp_err_t bol_node_parse_mac(const char *text, uint8_t *out_mac)
{
    esp_err_t ret = ESP_OK;
    uint8_t mac[BOL_MAC_BYTES];
    size_t index = 0U;

    // The reader writes the address only after every byte of the text passes.
    // The return value of memset is the destination, which the caller already holds.
    (void)memset(mac, 0, sizeof(mac));

    if ((text == NULL) || (out_mac == NULL)) {
        ret = ESP_ERR_INVALID_ARG;
    } else if (strlen(text) != (BOL_MAC_TEXT_BYTES - 1U)) {
        ret = ESP_ERR_INVALID_ARG;
    } else {
        while ((ret == ESP_OK) && (index < BOL_MAC_BYTES)) {
            const size_t offset = index * 3U;
            uint8_t high = 0U;
            uint8_t low = 0U;
            const bool pair_is_hex = bol_hex_value(text[offset], &high) &&
                                     bol_hex_value(text[offset + 1U], &low);

            if (!pair_is_hex) {
                ret = ESP_ERR_INVALID_ARG;
            } else if ((index < (BOL_MAC_BYTES - 1U)) && (text[offset + 2U] != ':')) {
                ret = ESP_ERR_INVALID_ARG;
            } else {
                mac[index] = (uint8_t)(((uint32_t)high << 4U) | (uint32_t)low);
                index++;
            }
        }
    }

    if (ret == ESP_OK) {
        // The return value of memcpy is the destination, which the caller already holds.
        (void)memcpy(out_mac, mac, sizeof(mac));
    }

    return ret;
}

esp_err_t bol_node_format_mac(const uint8_t *mac, char *out_text, size_t out_capacity_bytes)
{
    esp_err_t ret = ESP_OK;

    if ((mac == NULL) || (out_text == NULL)) {
        ret = ESP_ERR_INVALID_ARG;
    } else if (out_capacity_bytes < BOL_MAC_TEXT_BYTES) {
        ret = ESP_ERR_INVALID_SIZE;
    } else {
        size_t index = 0U;

        while (index < BOL_MAC_BYTES) {
            const size_t offset = index * 3U;
            const uint8_t value = mac[index];

            out_text[offset] = s_hex_digits[(size_t)(((uint32_t)value >> 4U) & 0x0FU)];
            out_text[offset + 1U] = s_hex_digits[(size_t)((uint32_t)value & 0x0FU)];
            if (index < (BOL_MAC_BYTES - 1U)) {
                out_text[offset + 2U] = ':';
            }
            index++;
        }

        out_text[BOL_MAC_TEXT_BYTES - 1U] = '\0';
    }

    return ret;
}

esp_err_t bol_node_set_role(bol_node_t *node, bol_role_t role, uint32_t run_id,
                            const uint8_t *peer_mac)
{
    esp_err_t ret = ESP_OK;

    if (node == NULL) {
        ret = ESP_ERR_INVALID_ARG;
    } else if ((role != BOL_ROLE_SENDER) && (role != BOL_ROLE_RECEIVER)) {
        ret = ESP_ERR_INVALID_ARG;
    } else if ((role == BOL_ROLE_SENDER) && (peer_mac == NULL)) {
        // The sender reaches the receiver by address, so a sender without one
        // cannot run the unicast pass of its cell.
        ret = ESP_ERR_INVALID_ARG;
    } else {
        bol_node_reset(node);
        node->role = role;
        node->run_id = run_id;

        if (peer_mac != NULL) {
            // The return value of memcpy is the destination, which the caller already holds.
            (void)memcpy(node->peer_mac, peer_mac, BOL_MAC_BYTES);
            node->has_peer = true;
        }
    }

    return ret;
}

esp_err_t bol_node_set_cell(bol_node_t *node, const bol_node_cell_t *cell,
                            uint32_t payload_limit_bytes)
{
    esp_err_t ret = ESP_OK;

    if ((node == NULL) || (cell == NULL)) {
        ret = ESP_ERR_INVALID_ARG;
    } else if (node->role == BOL_ROLE_NONE) {
        ret = ESP_ERR_INVALID_STATE;
    } else if (cell->cell_id > (uint16_t)BOL_FRAME_CELL_ID_MAX) {
        ret = ESP_ERR_INVALID_ARG;
    } else if (cell->payload_bytes < BOL_FRAME_HEADER_BYTES) {
        // A message holds the header of its first packet, so a payload below
        // that header carries no frame.
        ret = ESP_ERR_INVALID_ARG;
    } else if ((cell->frames == 0U) || (payload_limit_bytes == 0U)) {
        ret = ESP_ERR_INVALID_ARG;
    } else if (cell->channel > (uint32_t)UINT8_MAX) {
        ret = ESP_ERR_INVALID_ARG;
    } else if (cell->power_set_value > (uint32_t)INT8_MAX) {
        ret = ESP_ERR_INVALID_ARG;
    } else {
        const uint32_t packets = bol_stats_packets_per_message(cell->payload_bytes,
                                                               payload_limit_bytes);

        if (packets == 0U) {
            ret = ESP_ERR_INVALID_ARG;
        } else {
            node->cell = *cell;
            node->packets_per_message = packets;
            node->has_cell = true;
        }
    }

    return ret;
}

esp_err_t bol_node_positions(const bol_node_t *node, uint32_t *out_positions)
{
    esp_err_t ret = ESP_OK;

    if ((node == NULL) || (out_positions == NULL)) {
        ret = ESP_ERR_INVALID_ARG;
    } else if (!node->has_cell) {
        ret = ESP_ERR_INVALID_STATE;
    } else {
        // A pass sends whole messages only, so the product stays at or below the
        // frame budget and no multiplication wraps.
        const uint32_t messages = bol_stats_messages_that_fit(node->cell.frames,
                                                              node->packets_per_message);

        *out_positions = messages * node->packets_per_message;
    }

    return ret;
}

esp_err_t bol_node_check_cell(const bol_node_t *node, uint16_t cell_id, bol_pass_t pass)
{
    esp_err_t ret = ESP_OK;

    if (node == NULL) {
        ret = ESP_ERR_INVALID_ARG;
    } else if (!node->has_cell) {
        ret = ESP_ERR_INVALID_STATE;
    } else if ((node->cell.cell_id != cell_id) || (node->cell.pass != pass)) {
        ret = ESP_ERR_INVALID_STATE;
    } else {
        ret = ESP_OK;
    }

    return ret;
}
