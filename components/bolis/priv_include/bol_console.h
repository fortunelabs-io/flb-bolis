/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file bol_console.h
 * @brief Control plane on the console (thinkbook section 7, decision record
 *        2026-10-01-control-line-wire-format.md).
 */

#ifndef BOL_CONSOLE_H
#define BOL_CONSOLE_H

#include "esp_err.h"

/**
 * @brief Starts the control task that reads and writes control lines.
 *
 * Installs the UART driver on the console port, points the standard streams at
 * the driver so a read blocks, and starts the task. The task reads one line at
 * a time, answers the commands it implements, and counts every line it rejects.
 *
 * @pre The radio is up, because the task answers hello with the ESP-NOW version.
 * @note Call once, from a task. Do not call from a callback.
 *
 * @retval ESP_OK                 The control task runs.
 * @retval ESP_ERR_NO_MEM         The task did not start.
 * @retval ESP_ERR_INVALID_STATE  The standard streams did not reach the driver.
 * @retval Other                  The code that the failing ESP-IDF call returned.
 */
esp_err_t bol_console_start(void);

#endif // BOL_CONSOLE_H
