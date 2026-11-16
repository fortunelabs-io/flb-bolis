/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file bol_radio.h
 * @brief The radio of a node: its address, the condition of a cell, and the
 *        peers of a sender (thinkbook section 7, decision record
 *        2026-10-01-radio-ownership-and-prebuilt-firmware.md).
 *
 * Every call that touches the WiFi driver or ESP-NOW lives here, so the
 * console holds the control line and the node module holds the state. The
 * console calls these functions while it answers the role command and the
 * cell command.
 */

#ifndef BOL_RADIO_H
#define BOL_RADIO_H

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/** @brief The bytes of a country code as text, with its null terminator. */
#define BOL_COUNTRY_TEXT_BYTES 4U

/**
 * @brief Returns the address that a broadcast pass sends to.
 *
 * @return The six bytes of the broadcast address.
 */
const uint8_t *bol_radio_broadcast_address(void);

/**
 * @brief Reads the country code that the radio holds.
 *
 * The hello reply states this code, and the run record takes it from there
 * (decision record 2026-11-16-the-country-code-in-the-hello-reply.md). The
 * reader takes the code from the driver rather than from the setting that
 * configured it, so the reply states what applied.
 *
 * The code reaches a reply inside a JSON string, so this function accepts a
 * code of letters and digits only and rejects anything else.
 *
 * @pre WiFi has started.
 *
 * @param[out] out_text            The buffer that receives the code and its
 *                                 null terminator.
 * @param[in]  out_capacity_bytes  The size of out_text,
 *                                 BOL_COUNTRY_TEXT_BYTES or more.
 *
 * @retval ESP_OK                 out_text holds the code.
 * @retval ESP_ERR_INVALID_ARG    The pointer is NULL.
 * @retval ESP_ERR_INVALID_SIZE   The buffer is shorter than
 *                                BOL_COUNTRY_TEXT_BYTES.
 * @retval ESP_ERR_INVALID_STATE  The driver reported a code that holds a byte
 *                                which is neither a letter nor a digit.
 * @retval Other                  The code that the failing ESP-IDF call returned.
 */
esp_err_t bol_radio_country_code(char *out_text, size_t out_capacity_bytes);

/**
 * @brief Reads the address of the station interface of this node.
 *
 * The role reply states this address, and the host sends it to the sender as
 * `peer_mac`. No side writes it to a log, a run record, or a report, which
 * specification section 7 requires.
 *
 * @param[out] out_mac  The six bytes of the address.
 *
 * @retval ESP_OK               out_mac holds the address.
 * @retval ESP_ERR_INVALID_ARG  The pointer is NULL.
 * @retval Other                The code that the failing ESP-IDF call returned.
 */
esp_err_t bol_radio_station_mac(uint8_t *out_mac);

/**
 * @brief Applies the channel and the transmit power of one cell.
 *
 * Reads the transmit power back from the radio after it sets it, because the
 * cell reply states the value that the radio reports rather than the value
 * that the host requested (decision record
 * 2026-11-11-control-line-command-fields.md).
 *
 * @param[in]  channel               The channel to set.
 * @param[in]  power_set_value       The transmit power, in units of 0.25 dBm.
 * @param[out] out_power_read_back   The transmit power that the radio reports,
 *                                   in units of 0.25 dBm.
 *
 * @retval ESP_OK               The radio holds the condition.
 * @retval ESP_ERR_INVALID_ARG  The pointer is NULL.
 * @retval Other                The code that the failing ESP-IDF call returned.
 *                              The driver checks the range of each value.
 */
esp_err_t bol_radio_apply_condition(uint8_t channel, int8_t power_set_value,
                                    int8_t *out_power_read_back);

/**
 * @brief Gives a sender the broadcast peer and the peer of the receiver.
 *
 * Sets both peers at 1 Mbps (decision record
 * 2026-10-01-phy-rate-fixed-at-1-mbps.md). A peer that already exists takes
 * the new channel, so a cell that moves the channel needs no delete.
 *
 * @param[in] peer_mac  The six bytes of the address of the receiver.
 * @param[in] channel   The channel that both peers use.
 *
 * @retval ESP_OK               Both peers hold the channel and the rate.
 * @retval ESP_ERR_INVALID_ARG  The pointer is NULL.
 * @retval Other                The code that the failing ESP-IDF call returned.
 */
esp_err_t bol_radio_set_peers(const uint8_t *peer_mac, uint8_t channel);

#ifdef __cplusplus
}
#endif

#endif /* BOL_RADIO_H */
