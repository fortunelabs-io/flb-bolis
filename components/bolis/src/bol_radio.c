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

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_now.h"
#include "esp_wifi.h"
#include "nvs_flash.h"

#include "bolis.h"

static const char *const s_tag = "bolis";

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
 * @brief Brings the radio up and initializes ESP-NOW.
 *
 * Each step runs only after the previous step returned ESP_OK, so the first
 * failing code reaches the caller.
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

    return ret;
}

esp_err_t bol_start(void)
{
    esp_err_t ret = ESP_OK;
    // The call needs the address of an object. The mode itself does not change the result.
    wifi_mode_t mode = WIFI_MODE_NULL;

    ret = esp_wifi_get_mode(&mode);

    if (ret != ESP_ERR_WIFI_NOT_INIT) {
        ESP_LOGE(s_tag, "WiFi is already initialized. Bolis leaves the radio unchanged.");
        ret = ESP_ERR_INVALID_STATE;
    } else {
        ret = bol_radio_up();
        if (ret == ESP_OK) {
            ESP_LOGI(s_tag, "The radio is ready. The country code is %s.", CONFIG_BOL_COUNTRY_CODE);
        } else {
            ESP_LOGE(s_tag, "The radio did not start: %s", esp_err_to_name(ret));
        }
    }

    return ret;
}
