/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file bol_node.h
 * @brief The state that a node holds between control commands (decision
 *        record 2026-11-16-the-arm-and-finish-of-a-receiver-pass.md).
 *
 * A node takes its role and its run from the role command, and it takes the
 * condition, the pass, and the frame budget of one pass from the cell
 * command. This module holds those values, checks each one, and derives the
 * positions that the pass puts on the air.
 *
 * This module touches no radio and no task. It holds the state machine of a
 * node, so the reader tests drive it on the host.
 */

#ifndef BOL_NODE_H
#define BOL_NODE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#include "bol_frame.h"

#ifdef __cplusplus
extern "C" {
#endif

/** @brief The bytes of a MAC address. */
#define BOL_MAC_BYTES 6U

/** @brief The bytes of a MAC address as text, with its null terminator. */
#define BOL_MAC_TEXT_BYTES 18U

/** @brief The bytes of a role name as text, with its null terminator. */
#define BOL_ROLE_TEXT_BYTES 9U

/** @brief The bytes of a pass name as text, with its null terminator. */
#define BOL_PASS_TEXT_BYTES 10U

/** @brief The role that a node took, or none before its first role command. */
typedef enum {
    BOL_ROLE_NONE = 0,     /*!< The node holds no role. */
    BOL_ROLE_SENDER = 1,   /*!< The node sends the frames of a pass. */
    BOL_ROLE_RECEIVER = 2  /*!< The node counts the frames of a pass. */
} bol_role_t;

/**
 * @brief The condition and the pass that one cell command states.
 *
 * The channel and the transmit power hold the width that the control line
 * carries. The driver checks the value of each one and reports its own code,
 * so this module checks only that a value fits the type the driver takes.
 */
typedef struct {
    uint16_t cell_id;          /*!< The cell, 0 to BOL_FRAME_CELL_ID_MAX. */
    uint32_t channel;          /*!< The channel, which fits eight bits. */
    uint32_t power_set_value;  /*!< The transmit power, in units of 0.25 dBm. */
    uint32_t payload_bytes;    /*!< The payload of one message, in bytes. */
    bol_pass_t pass;           /*!< The pass that follows this command. */
    uint32_t frames;           /*!< The frame budget of that pass, in packets. */
} bol_node_cell_t;

/** @brief Everything a node remembers between two control commands. */
typedef struct {
    bol_role_t role;                 /*!< The role of this node. */
    uint32_t run_id;                 /*!< The run that the role command carried. */
    uint8_t peer_mac[BOL_MAC_BYTES]; /*!< The address of the other node. */
    bool has_peer;                   /*!< Whether peer_mac holds an address. */
    bool has_cell;                   /*!< Whether condition holds a condition. */
    bol_node_cell_t condition;            /*!< The condition of the current pass. */
    uint32_t packets_per_message;    /*!< The packets of one message of that condition. */
} bol_node_t;

/**
 * @brief Clears every field of a node.
 *
 * @param[out] node  The node to clear.
 */
void bol_node_reset(bol_node_t *node);

/**
 * @brief Reads a role name.
 *
 * @param[in]  text      The null-terminated name, sender or receiver.
 * @param[out] out_role  The role that the name states.
 *
 * @retval ESP_OK               out_role holds the role.
 * @retval ESP_ERR_INVALID_ARG  A pointer is NULL, or the name is neither role.
 */
esp_err_t bol_node_parse_role(const char *text, bol_role_t *out_role);

/**
 * @brief Returns the name of a role.
 *
 * @param[in] role  The role to name.
 *
 * @return The name, or an empty string for BOL_ROLE_NONE.
 */
const char *bol_node_role_name(bol_role_t role);

/**
 * @brief Reads a pass name.
 *
 * @param[in]  text      The null-terminated name, broadcast or unicast.
 * @param[out] out_pass  The pass that the name states.
 *
 * @retval ESP_OK               out_pass holds the pass.
 * @retval ESP_ERR_INVALID_ARG  A pointer is NULL, or the name is neither pass.
 */
esp_err_t bol_node_parse_pass(const char *text, bol_pass_t *out_pass);

/**
 * @brief Returns the name of a pass.
 *
 * @param[in] pass  The pass to name.
 *
 * @return The name, broadcast or unicast.
 */
const char *bol_node_pass_name(bol_pass_t pass);

/**
 * @brief Reads a MAC address from its text.
 *
 * The text holds six pairs of hexadecimal digits, separated by colons, in
 * either letter case. The reader treats the text as untrusted (MISRA Dir
 * 4.14), so it checks every byte before it writes an address.
 *
 * @param[in]  text     The null-terminated text, such as aa:bb:cc:dd:ee:ff.
 * @param[out] out_mac  The six bytes of the address.
 *
 * @retval ESP_OK               out_mac holds the address.
 * @retval ESP_ERR_INVALID_ARG  A pointer is NULL, or the text is not an address.
 */
esp_err_t bol_node_parse_mac(const char *text, uint8_t *out_mac);

/**
 * @brief Writes a MAC address as lowercase text.
 *
 * @param[in]  mac                 The six bytes of the address.
 * @param[out] out_text            The buffer that receives the text and its
 *                                 null terminator.
 * @param[in]  out_capacity_bytes  The size of out_text, BOL_MAC_TEXT_BYTES or more.
 *
 * @retval ESP_OK                out_text holds the address.
 * @retval ESP_ERR_INVALID_ARG   A pointer is NULL.
 * @retval ESP_ERR_INVALID_SIZE  The buffer is shorter than BOL_MAC_TEXT_BYTES.
 */
esp_err_t bol_node_format_mac(const uint8_t *mac, char *out_text, size_t out_capacity_bytes);

/**
 * @brief Gives a node its role and its run, and clears the condition it held.
 *
 * A role command starts a run, so the node holds no cell until the first cell
 * command of that run.
 *
 * @param[in,out] node      The node that takes the role.
 * @param[in]     role      The role, sender or receiver.
 * @param[in]     run_id    The run that the role command carried.
 * @param[in]     peer_mac  The address of the other node, or NULL for a
 *                          receiver, which takes no peer.
 *
 * @retval ESP_OK               The node holds the role and the run.
 * @retval ESP_ERR_INVALID_ARG  The node is NULL, the role is BOL_ROLE_NONE, or
 *                              a sender took no peer address.
 */
esp_err_t bol_node_set_role(bol_node_t *node, bol_role_t role, uint32_t run_id,
                            const uint8_t *peer_mac);

/**
 * @brief Takes the condition and the pass of one cell command.
 *
 * Derives the packets of one message from the payload size and the payload
 * limit, which the arm of a receiver and the budget of a sender both need.
 *
 * @param[in,out] node                 The node that takes the condition.
 * @param[in]     condition                 The condition that the command stated.
 * @param[in]     payload_limit_bytes  The packet payload limit L, 1 or more.
 *
 * @retval ESP_OK                 The node holds the condition.
 * @retval ESP_ERR_INVALID_ARG    A pointer is NULL, the cell sits above
 *                                BOL_FRAME_CELL_ID_MAX, the payload is below
 *                                BOL_FRAME_HEADER_BYTES, the frame budget is
 *                                0, the payload limit is 0, or the channel or
 *                                the transmit power does not fit the type that
 *                                the driver takes.
 * @retval ESP_ERR_INVALID_STATE  The node holds no role, so no cell command
 *                                can reach it yet.
 */
esp_err_t bol_node_set_cell(bol_node_t *node, const bol_node_cell_t *condition,
                            uint32_t payload_limit_bytes);

/**
 * @brief Returns the positions that the current pass puts on the air.
 *
 * A pass sends whole messages only, which decision record
 * 2026-11-13-the-sending-loop-of-a-pass.md fixes, so the positions are the
 * whole messages that fit the frame budget, multiplied by the packets of one
 * message. The finish of a receiver takes that count.
 *
 * @param[in]  node           The node that holds the condition.
 * @param[out] out_positions  The positions of the pass, in packets.
 *
 * @retval ESP_OK                 out_positions holds the count.
 * @retval ESP_ERR_INVALID_ARG    A pointer is NULL.
 * @retval ESP_ERR_INVALID_STATE  The node holds no cell.
 */
esp_err_t bol_node_positions(const bol_node_t *node, uint32_t *out_positions);

/**
 * @brief Checks that a command names the cell and the pass that the node holds.
 *
 * The go command and the stats command both name a cell and a pass. A command
 * that names another one reaches a node whose condition the host did not
 * apply, so the node answers with an error rather than with the counters of a
 * different pass.
 *
 * @param[in] node     The node that holds the condition.
 * @param[in] cell_id  The cell that the command named.
 * @param[in] pass     The pass that the command named.
 *
 * @retval ESP_OK                 The node holds that cell and that pass.
 * @retval ESP_ERR_INVALID_ARG    The node is NULL.
 * @retval ESP_ERR_INVALID_STATE  The node holds no cell, or it holds another
 *                                cell or another pass.
 */
esp_err_t bol_node_check_cell(const bol_node_t *node, uint16_t cell_id, bol_pass_t pass);

#ifdef __cplusplus
}
#endif

#endif /* BOL_NODE_H */
