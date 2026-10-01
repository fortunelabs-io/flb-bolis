/**
 * @file main.c
 * @brief Entry point of the bench example. It calls only bol_start (decision record
 *        2026-10-01-radio-ownership-and-prebuilt-firmware.md).
 */

#include "esp_err.h"
#include "esp_log.h"

#include "bolis.h"

static const char *const s_tag = "bench";

// ESP-IDF calls app_main from the startup task and declares it in no public header.
void app_main(void);

void app_main(void)
{
    const esp_err_t ret = bol_start();

    if (ret != ESP_OK) {
        ESP_LOGE(s_tag, "The node is not ready for a run: %s", esp_err_to_name(ret));
    }
}
