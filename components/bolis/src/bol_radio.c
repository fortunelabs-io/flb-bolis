/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file bol_radio.c
 * @brief Radio owner of the Bolis firmware (thinkbook section 7, decision record
 *        2026-10-01-radio-ownership-and-prebuilt-firmware.md).
 */

#include <stdbool.h>
#include <string.h>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_wifi.h"
#include "nvs_flash.h"

#include "bolis.h"

#include "bol_console.h"
#include "bol_radio.h"

/** @brief The address that a broadcast pass sends to. */
static const uint8_t s_broadcast_mac[ESP_NOW_ETH_ALEN] = {
    0xFFU, 0xFFU, 0xFFU, 0xFFU, 0xFFU, 0xFFU
};

/**
 * @brief Initializes the non-volatile storage that the WiFi driver reads.
 *
 * Erases the storage and initializes it again if the partition is full or
 * holds an older format.
 */
static esp_err_t bol_nvs_init(void)
{
    esp_err_t ret = nvs_flash_init();

    if ((ret == ESP_ERR_NVS_NO_FREE_PAGES) || (ret == ESP_ERR_NVS_NEW_VERSION_FOUND)) {
        ret = nvs_flash_erase();
        if (ret == ESP_OK) {
            ret = nvs_flash_init();
        }
    }

    return ret;
}

/**
 * @brief Creates the default event loop, and accepts a loop that already exists.
 *
 * A source build can create the default event loop before it calls bol_start.
 * An existing loop does not conflict with a run, because Bolis registers no
 * handler on it.
 */
static esp_err_t bol_event_loop_init(void)
{
    esp_err_t ret = esp_event_loop_create_default();

    if (ret == ESP_ERR_INVALID_STATE) {
        ret = ESP_OK;
    }

    return ret;
}

/**
 * @brief Brings the radio up, initializes ESP-NOW, and starts the control task.
 *
 * Each step runs only after the previous step returned ESP_OK, so the first
 * failing code reaches the caller. The control task starts last, because its
 * hello reply states the ESP-NOW version.
 */
static esp_err_t bol_radio_up(void)
{
    esp_err_t ret = ESP_OK;
    wifi_init_config_t wifi_config = WIFI_INIT_CONFIG_DEFAULT();

    ret = bol_nvs_init();

    if (ret == ESP_OK) {
        ret = esp_netif_init();
    }
    if (ret == ESP_OK) {
        ret = bol_event_loop_init();
    }
    if (ret == ESP_OK) {
        ret = esp_wifi_init(&wifi_config);
    }
    if (ret == ESP_OK) {
        // The radio settings of a run stay in RAM, so a run writes no WiFi state to flash
        // and the next run starts from the same state.
        ret = esp_wifi_set_storage(WIFI_STORAGE_RAM);
    }
    if (ret == ESP_OK) {
        ret = esp_wifi_set_mode(WIFI_MODE_STA);
    }
    if (ret == ESP_OK) {
        // 802.11d stays off, so a beacon of another network cannot change the country
        // during a run, and the run record states the country that applied.
        ret = esp_wifi_set_country_code(CONFIG_BOL_COUNTRY_CODE, false);
    }
    if (ret == ESP_OK) {
        ret = esp_wifi_start();
    }
    if (ret == ESP_OK) {
        // Power save stays off on both nodes, because a node in modem sleep does not
        // receive ESP-NOW data (thinkbook section 4).
        ret = esp_wifi_set_ps(WIFI_PS_NONE);
    }
    if (ret == ESP_OK) {
        ret = esp_now_init();
    }
    if (ret == ESP_OK) {
        ret = bol_console_start();
    }

    return ret;
}

/**
 * @brief Adds one peer, or moves a peer that exists to a new channel.
 *
 * @param[in] address  The six bytes of the peer address.
 * @param[in] channel  The channel that the peer uses.
 *
 * @retval ESP_OK  The peer holds the channel and the rate.
 * @retval Other   The code that the failing ESP-IDF call returned.
 */
static esp_err_t bol_radio_set_peer(const uint8_t *address, uint8_t channel)
{
    esp_now_peer_info_t peer;
    // Decision record 2026-10-01-phy-rate-fixed-at-1-mbps.md fixes the rate of
    // every peer that the component adds.
    esp_now_rate_config_t rate = {
        .phymode = WIFI_PHY_MODE_11B,
        .rate = WIFI_PHY_RATE_1M_L,
        .ersu = false,
        .dcm = false
    };
    esp_err_t ret = ESP_OK;

    // The return value of memset is the destination, which this function already holds.
    (void)memset(&peer, 0, sizeof(peer));
    (void)memcpy(peer.peer_addr, address, (size_t)ESP_NOW_ETH_ALEN);
    peer.channel = channel;
    peer.ifidx = WIFI_IF_STA;
    peer.encrypt = false;

    if (esp_now_is_peer_exist(address)) {
        ret = esp_now_mod_peer(&peer);
    } else {
        ret = esp_now_add_peer(&peer);
    }

    if (ret == ESP_OK) {
        ret = esp_now_set_peer_rate_config(address, &rate);
    }

    return ret;
}

const uint8_t *bol_radio_broadcast_address(void)
{
    return s_broadcast_mac;
}

esp_err_t bol_radio_station_mac(uint8_t *out_mac)
{
    esp_err_t ret = ESP_OK;

    if (out_mac == NULL) {
        ret = ESP_ERR_INVALID_ARG;
    } else {
        ret = esp_wifi_get_mac(WIFI_IF_STA, out_mac);
    }

    return ret;
}

esp_err_t bol_radio_apply_condition(uint8_t channel, int8_t power_set_value,
                                    int8_t *out_power_read_back)
{
    esp_err_t ret = ESP_OK;

    if (out_power_read_back == NULL) {
        ret = ESP_ERR_INVALID_ARG;
    } else {
        ret = esp_wifi_set_channel(channel, WIFI_SECOND_CHAN_NONE);
    }

    if (ret == ESP_OK) {
        ret = esp_wifi_set_max_tx_power(power_set_value);
    }
    if (ret == ESP_OK) {
        // The cell reply states the value that the radio reports rather than the
        // value that the host requested.
        ret = esp_wifi_get_max_tx_power(out_power_read_back);
    }

    return ret;
}

esp_err_t bol_radio_set_peers(const uint8_t *peer_mac, uint8_t channel)
{
    esp_err_t ret = ESP_OK;

    if (peer_mac == NULL) {
        ret = ESP_ERR_INVALID_ARG;
    } else {
        ret = bol_radio_set_peer(s_broadcast_mac, channel);
    }

    if (ret == ESP_OK) {
        ret = bol_radio_set_peer(peer_mac, channel);
    }

    return ret;
}

esp_err_t bol_start(void)
{
    static const char *const radio_tag = "bolis";
    esp_err_t ret = ESP_OK;
    // The call needs the address of an object. The mode itself does not change the result.
    wifi_mode_t mode = WIFI_MODE_NULL;

    ret = esp_wifi_get_mode(&mode);

    if (ret != ESP_ERR_WIFI_NOT_INIT) {
        ESP_LOGE(radio_tag, "WiFi is already initialized. Bolis leaves the radio unchanged.");
        ret = ESP_ERR_INVALID_STATE;
    } else {
        ret = bol_radio_up();
        if (ret == ESP_OK) {
            ESP_LOGI(radio_tag, "The radio is ready. The country code is %s.", CONFIG_BOL_COUNTRY_CODE);
        } else {
            ESP_LOGE(radio_tag, "The radio did not start: %s", esp_err_to_name(ret));
        }
    }

    return ret;
}
