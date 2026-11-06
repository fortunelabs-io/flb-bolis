/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file bol_console.c
 * @brief Control plane on the console (thinkbook section 7, decision record
 *        2026-10-01-control-line-wire-format.md).
 *
 * This module is the only module that includes the standard input and output
 * header, and the only module that writes a line with the control prefix.
 * Deviation record D-001 covers that include.
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
// cppcheck-suppress misra-c2012-21.6 ; D-001
#include <stdio.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "driver/uart.h"
#include "driver/uart_vfs.h"
#include "esp_app_desc.h"
#include "esp_chip_info.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_now.h"

#include "bol_console.h"
#include "bol_json.h"

/** @brief The prefix of every control line, in both directions. */
#define BOL_LINE_PREFIX "@bol "

/** @brief The largest control line in bytes, including the prefix and the newline. */
#define BOL_LINE_MAX_BYTES 512U

/** @brief The version of the control line contract that this firmware speaks. */
#define BOL_PROTO_VERSION 1U

/** @brief The buffer size for a command name, including the null terminator. */
#define BOL_COMMAND_MAX_BYTES 16U

/** @brief The buffer size for the ELF SHA-256 as text: 64 characters and the null terminator. */
#define BOL_SHA256_TEXT_BYTES 65U

/** @brief The number of bytes of the ELF SHA-256 in the application description. */
#define BOL_SHA256_BYTES 32U

/** @brief The console port that carries the log and the control lines. */
#define BOL_CONSOLE_UART_NUM CONFIG_ESP_CONSOLE_UART_NUM

/**
 * @brief The receive buffer of the UART driver in bytes.
 *
 * The hardware FIFO of the ESP32 holds 128 bytes, and a control line reaches
 * 512 bytes, so the driver buffer holds a full line and leaves room for the
 * next one.
 */
#define BOL_CONSOLE_RX_BUFFER_BYTES 1024

/**
 * @brief The stack of the control task in bytes.
 *
 * ESP-IDF measures a task stack in bytes. The task keeps its line buffer and
 * its reply buffer in static storage, so the stack carries the formatting of
 * one reply. High-water mark from uxTaskGetStackHighWaterMark: <pending, no run
 * has measured it yet>.
 */
#define BOL_CONSOLE_STACK_BYTES 4096

/**
 * @brief The priority of the control task.
 *
 * The task stays below the WiFi task and below the sender, because a control
 * line must never delay a frame of a pass.
 */
#define BOL_CONSOLE_TASK_PRIORITY 2

#ifdef CONFIG_BOL_PREBUILT
/** @brief The firmware path that the hello reply states. */
#define BOL_FIRMWARE_PATH "prebuilt"
#else
/** @brief The firmware path that the hello reply states. */
#define BOL_FIRMWARE_PATH "source"
#endif

#ifdef CONFIG_BT_ENABLED
/** @brief The state of the Bluetooth controller that the hello reply states. */
#define BOL_BLUETOOTH_STATE "enabled"
#else
/** @brief The state of the Bluetooth controller that the hello reply states. */
#define BOL_BLUETOOTH_STATE "disabled"
#endif

static const char *const s_console_tag = "bolis";

/** @brief The line that the task reads. Only the control task touches it. */
static char s_line[BOL_LINE_MAX_BYTES + 1U];

/** @brief The reply that the task writes. Only the control task touches it. */
static char s_reply[BOL_LINE_MAX_BYTES + 1U];

// cppcheck-suppress misra-c2012-8.9 ; the stats command reads this counter in a later change
/** @brief The count of lines that the node rejected. The stats command reports it. */
static uint32_t s_rejected_line_count = 0U;

/**
 * @brief Counts one rejected line, and stops at the top of the range.
 */
static void bol_count_rejected_line(void)
{
    if (s_rejected_line_count < UINT32_MAX) {
        s_rejected_line_count++;
    }
}

/**
 * @brief Returns the name of a chip model, or "unknown" for a model that Bolis does not support.
 *
 * Thinkbook section 11 names the ESP32 first, then the ESP32-S3, the ESP32-C3,
 * and the ESP32-C6.
 */
static const char *bol_chip_name(esp_chip_model_t model)
{
    const char *name = "unknown";

    switch (model) {
    case CHIP_ESP32:
        name = "esp32";
        break;
    case CHIP_ESP32S3:
        name = "esp32s3";
        break;
    case CHIP_ESP32C3:
        name = "esp32c3";
        break;
    case CHIP_ESP32C6:
        name = "esp32c6";
        break;
    default:
        name = "unknown";
        break;
    }

    return name;
}

/**
 * @brief Reports whether a command name can appear in a reply without breaking the line.
 *
 * A name holds one to fifteen bytes, and every byte is a lowercase letter or an
 * underscore. The check runs before the node copies a name that came from the
 * host into a reply.
 */
static bool bol_command_name_is_safe(const char *name)
{
    const size_t length_bytes = strlen(name);
    bool is_safe = (length_bytes > 0U) && (length_bytes < BOL_COMMAND_MAX_BYTES);
    size_t index = 0U;

    while (is_safe && (index < length_bytes)) {
        const char value = name[index];

        if (((value < 'a') || (value > 'z')) && (value != '_')) {
            is_safe = false;
        } else {
            index++;
        }
    }

    return is_safe;
}

/**
 * @brief Encodes bytes as lowercase hexadecimal text with a null terminator.
 *
 * @param[in]  bytes       The bytes to encode.
 * @param[in]  byte_count  The number of bytes to encode.
 * @param[out] out_text    The buffer that receives two characters per byte and the
 *                         null terminator. It holds at least two times byte_count
 *                         plus one bytes.
 */
static void bol_hex_encode(const uint8_t *bytes, size_t byte_count, char *out_text)
{
    static const char hex_digits[] = "0123456789abcdef";
    size_t index = 0U;

    while (index < byte_count) {
        const uint8_t value = bytes[index];
        const uint8_t high = (uint8_t)((value >> 4U) & 0x0FU);
        const uint8_t low = (uint8_t)(value & 0x0FU);

        out_text[index * 2U] = hex_digits[high];
        out_text[(index * 2U) + 1U] = hex_digits[low];
        index++;
    }

    out_text[byte_count * 2U] = '\0';
}

/**
 * @brief Writes the reply buffer to the console as one line.
 *
 * The caller formats the buffer and checks that it fits the line limit.
 */
static esp_err_t bol_write_reply(void)
{
    esp_err_t ret = ESP_OK;

    // cppcheck-suppress misra-c2012-21.6 ; D-001
    if (fputs(s_reply, stdout) == EOF) {
        ret = ESP_FAIL;
    }

    // cppcheck-suppress misra-c2012-21.6 ; D-001
    if (fflush(stdout) == EOF) {
        ret = ESP_FAIL;
    }

    return ret;
}

/**
 * @brief Checks that a formatted reply fits the line limit that the record sets.
 */
static esp_err_t bol_reply_fits(int written)
{
    esp_err_t ret = ESP_OK;

    if ((written < 0) || ((size_t)written >= sizeof(s_reply))) {
        ret = ESP_ERR_INVALID_SIZE;
    }

    return ret;
}

/**
 * @brief Writes a reply that reports a failure.
 *
 * @param[in] command  The command name. The caller checks it with bol_command_name_is_safe.
 * @param[in] seq      The sequence number of the command that this reply answers.
 * @param[in] reason   The code whose name the reply states in the err key.
 */
static esp_err_t bol_reply_error(const char *command, uint32_t seq, esp_err_t reason)
{
    // cppcheck-suppress misra-c2012-21.6 ; D-001
    const int written = snprintf(s_reply, sizeof(s_reply),
                                 BOL_LINE_PREFIX
                                 "{\"proto\":%u,\"reply\":\"%s\",\"seq\":%u,\"ok\":false,"
                                 "\"err\":\"%s\"}\n",
                                 (unsigned int)BOL_PROTO_VERSION, command, (unsigned int)seq,
                                 esp_err_to_name(reason));
    esp_err_t ret = bol_reply_fits(written);

    if (ret == ESP_OK) {
        ret = bol_write_reply();
    }

    return ret;
}

/**
 * @brief Writes the hello reply.
 *
 * States the ELF SHA-256 as 64 lowercase hexadecimal characters, encoded from
 * the 32 bytes of the application description. The ESP-IDF text helper
 * truncates to the length that CONFIG_APP_RETRIEVE_LEN_ELF_SHA sets, so this
 * function encodes the bytes itself.
 */
static esp_err_t bol_reply_hello(uint32_t seq)
{
    esp_chip_info_t chip = {.model = CHIP_ESP32, .features = 0U, .revision = 0U, .cores = 0U};
    const esp_app_desc_t *description = esp_app_get_description();
    uint32_t espnow_version = 0U;
    esp_err_t ret = esp_now_get_version(&espnow_version);

    esp_chip_info(&chip);

    if ((ret == ESP_OK) && (description == NULL)) {
        ret = ESP_ERR_INVALID_STATE;
    }

    if (ret == ESP_OK) {
        char sha256_text[BOL_SHA256_TEXT_BYTES];

        // The encoder writes every byte and the null terminator. The clear holds the
        // buffer defined even if a later change shortens the encoded length.
        // The return value of memset is the destination, which the caller already holds.
        (void)memset(sha256_text, 0, sizeof(sha256_text));
        bol_hex_encode(description->app_elf_sha256, BOL_SHA256_BYTES, sha256_text);

        // The idf_ver field holds a fixed-size array, so the precision bounds the read.
        // cppcheck-suppress misra-c2012-21.6 ; D-001
        const int written = snprintf(s_reply, sizeof(s_reply),
                                     BOL_LINE_PREFIX
                                     "{\"proto\":%u,\"reply\":\"hello\",\"seq\":%u,\"ok\":true,"
                                     "\"chip\":\"%s\",\"chip_revision\":%u,"
                                     "\"idf_version\":\"%.32s\",\"espnow_version\":%u,"
                                     "\"payload_limit_bytes\":%u,\"bolis_version\":\"%s\","
                                     "\"firmware_path\":\"" BOL_FIRMWARE_PATH "\","
                                     "\"elf_sha256\":\"%s\","
                                     "\"bluetooth_controller\":\"" BOL_BLUETOOTH_STATE "\"}\n",
                                     (unsigned int)BOL_PROTO_VERSION, (unsigned int)seq,
                                     bol_chip_name(chip.model), (unsigned int)chip.revision,
                                     description->idf_ver, (unsigned int)espnow_version,
                                     (unsigned int)ESP_NOW_MAX_DATA_LEN_V2, BOL_VERSION,
                                     sha256_text);

        ret = bol_reply_fits(written);
    }

    if (ret == ESP_OK) {
        ret = bol_write_reply();
    }

    return ret;
}

/**
 * @brief Answers one control line.
 *
 * Reads the three keys that every host line carries, then dispatches on the
 * command. A line whose keys do not parse draws no reply, because the node
 * cannot name the command it failed to read. The node counts that line, and the
 * host detects the silence through its reply timeout.
 */
static void bol_handle_line(const char *object, size_t length_bytes)
{
    char command[BOL_COMMAND_MAX_BYTES];
    uint32_t proto = 0U;
    uint32_t seq = 0U;
    esp_err_t ret = ESP_OK;

    // The reader writes the name only when it returns ESP_OK. The clear holds the buffer
    // defined on every path. The return value of memset is the destination, which the
    // caller already holds.
    (void)memset(command, 0, sizeof(command));
    ret = bol_json_get_text(object, length_bytes, "cmd", command, sizeof(command));

    if (ret == ESP_OK) {
        ret = bol_json_get_u32(object, length_bytes, "seq", &seq);
    }
    if (ret == ESP_OK) {
        ret = bol_json_get_u32(object, length_bytes, "proto", &proto);
    }

    if (ret != ESP_OK) {
        bol_count_rejected_line();
        ESP_LOGW(s_console_tag, "The node rejected a control line: %s", esp_err_to_name(ret));
    } else if (!bol_command_name_is_safe(command)) {
        bol_count_rejected_line();
        ESP_LOGW(s_console_tag, "The node rejected a control line whose command name is unusable.");
    } else if (proto != BOL_PROTO_VERSION) {
        ret = bol_reply_error(command, seq, ESP_ERR_INVALID_VERSION);
    } else if (strcmp(command, "hello") == 0) {
        ret = bol_reply_hello(seq);
    } else if ((strcmp(command, "role") == 0) || (strcmp(command, "cell") == 0) ||
               (strcmp(command, "go") == 0) || (strcmp(command, "stats") == 0)) {
        // The sender, the receiver, and the cell configuration reach the component in a
        // later change. The command is in the contract, so the node names it as unsupported.
        ret = bol_reply_error(command, seq, ESP_ERR_NOT_SUPPORTED);
    } else {
        ret = bol_reply_error(command, seq, ESP_ERR_NOT_FOUND);
    }

    if (ret != ESP_OK) {
        ESP_LOGE(s_console_tag, "The node did not write a reply: %s", esp_err_to_name(ret));
    }
}

/**
 * @brief Reads bytes until a newline or the end of the stream, and discards them.
 *
 * Runs after the node rejects a line that exceeds the limit, so the next read
 * starts at a line boundary.
 */
static void bol_drain_line(void)
{
    bool draining = true;

    while (draining) {
        // cppcheck-suppress misra-c2012-21.6 ; D-001
        const int character = fgetc(stdin);

        if ((character == EOF) || (character == (int)'\n')) {
            draining = false;
        }
    }
}

/**
 * @brief Reads one line from the console into the line buffer.
 *
 * @param[out] out_length_bytes  The length of the line without its null terminator.
 *
 * @retval ESP_OK                The line buffer holds a null-terminated line.
 * @retval ESP_FAIL              The stream reached its end or failed.
 * @retval ESP_ERR_INVALID_SIZE  The line exceeds the limit. The reader discarded the rest.
 */
static esp_err_t bol_read_line(size_t *out_length_bytes)
{
    esp_err_t ret = ESP_OK;
    // cppcheck-suppress misra-c2012-21.6 ; D-001
    const char *line = fgets(s_line, (int)sizeof(s_line), stdin);
    size_t length_bytes = 0U;

    if (line == NULL) {
        ret = ESP_FAIL;
    } else {
        length_bytes = strlen(s_line);
    }

    if (ret == ESP_OK) {
        const bool holds_newline = (length_bytes > 0U) && (s_line[length_bytes - 1U] == '\n');

        if (!holds_newline && (length_bytes == (sizeof(s_line) - 1U))) {
            bol_drain_line();
            ret = ESP_ERR_INVALID_SIZE;
        }
    }

    if (ret == ESP_OK) {
        *out_length_bytes = length_bytes;
    }

    return ret;
}

/**
 * @brief Reads control lines for the life of the node.
 *
 * Ignores every line that does not start with the prefix, so the application
 * log and the control plane share one serial line.
 */
static void bol_console_task(void *argument)
{
    (void)argument;

    for (;;) {
        size_t length_bytes = 0U;
        const esp_err_t ret = bol_read_line(&length_bytes);

        if (ret == ESP_ERR_INVALID_SIZE) {
            bol_count_rejected_line();
            ESP_LOGW(s_console_tag, "The node rejected a control line longer than %u bytes.",
                     (unsigned int)BOL_LINE_MAX_BYTES);
        } else if (ret != ESP_OK) {
            // The console stream gives no more data. Wait, so the task leaves the processor
            // to the run instead of spinning on the failing read.
            vTaskDelay(pdMS_TO_TICKS(100));
        } else if (length_bytes > strlen(BOL_LINE_PREFIX)) {
            const size_t prefix_length_bytes = strlen(BOL_LINE_PREFIX);

            // Rule 21.14 rules out memcmp here, because both operands are null-terminated
            // strings. The length stays inside both objects, so rules 21.17 and 21.18 hold.
            if (strncmp(s_line, BOL_LINE_PREFIX, prefix_length_bytes) == 0) {
                bol_handle_line(&s_line[prefix_length_bytes], length_bytes - prefix_length_bytes);
            }
        } else {
            // A line shorter than the prefix carries no command.
        }
    }
}

esp_err_t bol_console_start(void)
{
    esp_err_t ret = uart_driver_install(BOL_CONSOLE_UART_NUM, BOL_CONSOLE_RX_BUFFER_BYTES, 0, 0,
                                        NULL, 0);
    TaskHandle_t handle = NULL;

    if (ret == ESP_OK) {
        // The driver gives the console an interrupt-driven receive buffer, so a read blocks
        // and no byte drops inside a line that exceeds the hardware FIFO.
        uart_vfs_dev_use_driver(BOL_CONSOLE_UART_NUM);

        // The host ends a line with a newline, and a reply ends the same way, so neither
        // direction translates a line ending.
        if (uart_vfs_dev_port_set_rx_line_endings(BOL_CONSOLE_UART_NUM,
                                                  ESP_LINE_ENDINGS_LF) != 0) {
            ret = ESP_ERR_INVALID_STATE;
        }
    }

    if (ret == ESP_OK) {
        if (uart_vfs_dev_port_set_tx_line_endings(BOL_CONSOLE_UART_NUM,
                                                  ESP_LINE_ENDINGS_LF) != 0) {
            ret = ESP_ERR_INVALID_STATE;
        }
    }

    if (ret == ESP_OK) {
        // The stack and the control block hold static storage duration, so they outlive
        // this function and stay available to the task for the life of the node.
        static StackType_t console_stack[BOL_CONSOLE_STACK_BYTES];
        static StaticTask_t console_task_block;

        handle = xTaskCreateStatic(bol_console_task, "bol_console", BOL_CONSOLE_STACK_BYTES, NULL,
                                   BOL_CONSOLE_TASK_PRIORITY, console_stack, &console_task_block);
        if (handle == NULL) {
            ret = ESP_ERR_NO_MEM;
        }
    }

    if (ret == ESP_OK) {
        ESP_LOGI(s_console_tag, "The control task reads the console. The contract version is %u.",
                 (unsigned int)BOL_PROTO_VERSION);
    }

    return ret;
}
