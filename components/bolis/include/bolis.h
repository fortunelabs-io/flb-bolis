/**
 * @file bolis.h
 * @brief Public API of the Bolis firmware component (thinkbook section 7).
 */

#ifndef BOL_BOLIS_H
#define BOL_BOLIS_H

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Takes the radio and prepares the node for a run.
 *
 * Initializes WiFi in station mode, keeps the WiFi settings in RAM, sets the
 * country code, disables power save, starts WiFi, and initializes ESP-NOW.
 * The node then waits for the host, which assigns the sender role or the
 * receiver role over the control plane.
 *
 * Bolis owns the radio during a run. If WiFi is already initialized, the
 * application of the user owns the radio, and this function changes nothing.
 *
 * @pre WiFi is not initialized.
 * @note Call once, from a task. Do not call from a callback.
 *
 * @retval ESP_OK                 The radio is ready for a run.
 * @retval ESP_ERR_INVALID_STATE  WiFi was already initialized. The radio is unchanged.
 * @retval Other                  The code that the failing ESP-IDF call returned. The radio
 *                                holds the state that the failing step left.
 */
esp_err_t bol_start(void);

#ifdef __cplusplus
}
#endif

#endif // BOL_BOLIS_H
