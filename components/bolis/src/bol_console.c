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
#include "freertos/semphr.h"
#include "freertos/task.h"

#include "driver/uart.h"
#include "driver/uart_vfs.h"
#include "esp_app_desc.h"
#include "esp_chip_info.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_now.h"
#include "esp_timer.h"

#include "bol_console.h"
#include "bol_json.h"
#include "bol_node.h"
#include "bol_radio.h"
#include "bol_receiver.h"
#include "bol_sender.h"

/** @brief The prefix of every control line, in both directions. */
#define BOL_LINE_PREFIX "@bol "

/** @brief The largest control line in bytes, including the prefix and the newline. */
#define BOL_LINE_MAX_BYTES 512U

/**
 * @brief The version of the control line contract that this firmware speaks.
 *
 * Version 2 carries the field keys of the role, cell, go, and stats commands
 * (decision record 2026-11-11-control-line-command-fields.md), the run ID on
 * the role command, the dropped packet counter of a receiver, and the pass
 * and the frame budget on the cell command.
 */
#define BOL_PROTO_VERSION 2U

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

/** @brief The count of lines that the node rejected. The stats command reports it. */
static uint32_t s_rejected_line_count = 0U;

/** @brief The state that this node holds between two control commands. */
static bol_node_t s_node;

/** @brief The counters of the last pass that this node sent. */
static bol_sender_counters_t s_sender_counters;

// cppcheck-suppress misra-c2012-8.9 ; a frame of this size overruns the task stack
/** @brief The frame that the sending loop fills and sends. */
static uint8_t s_frame[ESP_NOW_MAX_DATA_LEN_V2];

/** @brief Signals the control task that the callback of a send ran. */
static SemaphoreHandle_t s_send_done = NULL;

// cppcheck-suppress misra-c2012-8.9 ; the semaphore outlives the function that creates it
/** @brief The storage of that semaphore, which holds no heap (MISRA Dir 4.12). */
static StaticSemaphore_t s_send_done_buffer;

/** @brief The time of the send whose callback the task waits for, in microseconds. */
static int64_t s_send_start_us = 0;

/** @brief Whether the callback of the last send reported success. */
static bool s_send_was_ok = false;

/** @brief The sequence number of the go command that the current pass answers. */
static uint32_t s_pass_seq = 0U;

/** @brief The cell that the replies of the current pass state. */
static uint16_t s_pass_cell_id = 0U;

/** @brief The address that the current pass sends every frame to. */
static const uint8_t *s_pass_address = NULL;

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
 *                         null terminator. It holds at least 2 x byte_count
 *                         + 1 bytes.
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
 * @brief Appends one key and its unsigned value to the reply being built.
 *
 * @param[in,out] offset  The bytes of the reply so far.
 * @param[in]     key     The key name, which is a literal of this module.
 * @param[in]     value   The value of that key.
 *
 * @retval ESP_OK                The reply holds the pair.
 * @retval ESP_ERR_INVALID_SIZE  The pair does not fit the line.
 */
static esp_err_t bol_append_u32_key(size_t *offset, const char *key, uint32_t value)
{
    // cppcheck-suppress misra-c2012-21.6 ; D-001
    const int written = snprintf(&s_reply[*offset], sizeof(s_reply) - *offset,
                                 ",\"%s\":%u", key, (unsigned int)value);
    esp_err_t ret = ESP_OK;

    if ((written < 0) || ((size_t)written >= (sizeof(s_reply) - *offset))) {
        ret = ESP_ERR_INVALID_SIZE;
    } else {
        *offset += (size_t)written;
    }

    return ret;
}

/**
 * @brief Appends one key and its signed value to the reply being built.
 *
 * @param[in,out] offset  The bytes of the reply so far.
 * @param[in]     key     The key name, which is a literal of this module.
 * @param[in]     value   The value of that key.
 *
 * @retval ESP_OK                The reply holds the pair.
 * @retval ESP_ERR_INVALID_SIZE  The pair does not fit the line.
 */
static esp_err_t bol_append_i32_key(size_t *offset, const char *key, int32_t value)
{
    // cppcheck-suppress misra-c2012-21.6 ; D-001
    const int written = snprintf(&s_reply[*offset], sizeof(s_reply) - *offset,
                                 ",\"%s\":%d", key, (int)value);
    esp_err_t ret = ESP_OK;

    if ((written < 0) || ((size_t)written >= (sizeof(s_reply) - *offset))) {
        ret = ESP_ERR_INVALID_SIZE;
    } else {
        *offset += (size_t)written;
    }

    return ret;
}

/**
 * @brief Appends a literal to the reply being built.
 *
 * @param[in,out] offset  The bytes of the reply so far.
 * @param[in]     text    The text to append, which is a literal of this module.
 *
 * @retval ESP_OK                The reply holds the text.
 * @retval ESP_ERR_INVALID_SIZE  The text does not fit the line.
 */
static esp_err_t bol_append_text(size_t *offset, const char *text)
{
    const size_t length_bytes = strlen(text);
    esp_err_t ret = ESP_OK;

    if ((*offset + length_bytes) >= sizeof(s_reply)) {
        ret = ESP_ERR_INVALID_SIZE;
    } else {
        // The length stays inside both objects, so rules 21.17 and 21.18 hold.
        (void)memcpy(&s_reply[*offset], text, length_bytes);
        *offset += length_bytes;
        s_reply[*offset] = '\0';
    }

    return ret;
}

/**
 * @brief Appends one key whose value is a histogram of BOL_HISTOGRAM_BINS counts.
 *
 * @param[in,out] offset  The bytes of the reply so far.
 * @param[in]     key     The key name, which is a literal of this module.
 * @param[in]     bins    The counts, from the lowest bin to the highest.
 *
 * @retval ESP_OK                The reply holds the histogram.
 * @retval ESP_ERR_INVALID_SIZE  The histogram does not fit the line.
 */
static esp_err_t bol_append_histogram(size_t *offset, const char *key, const uint32_t *bins)
{
    // cppcheck-suppress misra-c2012-21.6 ; D-001
    int written = snprintf(&s_reply[*offset], sizeof(s_reply) - *offset, ",\"%s\":[", key);
    esp_err_t ret = ESP_OK;
    size_t index = 0U;

    if ((written < 0) || ((size_t)written >= (sizeof(s_reply) - *offset))) {
        ret = ESP_ERR_INVALID_SIZE;
    } else {
        *offset += (size_t)written;
    }

    while ((ret == ESP_OK) && (index < BOL_HISTOGRAM_BINS)) {
        // cppcheck-suppress misra-c2012-21.6 ; D-001
        written = snprintf(&s_reply[*offset], sizeof(s_reply) - *offset, "%s%u",
                           (index == 0U) ? "" : ",", (unsigned int)bins[index]);

        if ((written < 0) || ((size_t)written >= (sizeof(s_reply) - *offset))) {
            ret = ESP_ERR_INVALID_SIZE;
        } else {
            *offset += (size_t)written;
            index++;
        }
    }

    if (ret == ESP_OK) {
        ret = bol_append_text(offset, "]");
    }

    return ret;
}

/**
 * @brief Appends the mean strength of a pass, with one decimal place.
 *
 * The mean comes from an integer sum and an integer count, so this function
 * builds the decimal with integer arithmetic and never formats a floating
 * point value. A mean between minus one and zero keeps its sign, which a
 * truncating division alone would drop.
 *
 * @param[in,out] offset     The bytes of the reply so far.
 * @param[in]     sum_dbm    The sum of the strengths, in dBm.
 * @param[in]     count      The packets that the sum holds, 1 or more.
 *
 * @retval ESP_OK                The reply holds the mean.
 * @retval ESP_ERR_INVALID_SIZE  The mean does not fit the line.
 */
static esp_err_t bol_append_mean_rssi(size_t *offset, int64_t sum_dbm, uint32_t count)
{
    const int64_t tenths = (sum_dbm * 10) / (int64_t)count;
    const int64_t whole = tenths / 10;
    int64_t fraction = tenths % 10;
    const bool is_negative = (tenths < 0);
    int written;
    esp_err_t ret = ESP_OK;

    if (fraction < 0) {
        fraction = -fraction;
    }

    if (is_negative && (whole == 0)) {
        // cppcheck-suppress misra-c2012-21.6 ; D-001
        written = snprintf(&s_reply[*offset], sizeof(s_reply) - *offset,
                           ",\"rssi_mean_dbm\":-0.%u", (unsigned int)fraction);
    } else {
        // cppcheck-suppress misra-c2012-21.6 ; D-001
        written = snprintf(&s_reply[*offset], sizeof(s_reply) - *offset,
                           ",\"rssi_mean_dbm\":%d.%u", (int)whole, (unsigned int)fraction);
    }

    if ((written < 0) || ((size_t)written >= (sizeof(s_reply) - *offset))) {
        ret = ESP_ERR_INVALID_SIZE;
    } else {
        *offset += (size_t)written;
    }

    return ret;
}

/**
 * @brief Writes a go reply, which a pass sends at an interval and at its end.
 *
 * @param[in] seq          The sequence number of the go command.
 * @param[in] cell_id      The cell of the pass.
 * @param[in] is_done      Whether the pass ended.
 * @param[in] frames_sent  The frames whose callback has returned.
 */
static esp_err_t bol_reply_go(uint32_t seq, uint16_t cell_id, bool is_done,
                              uint32_t frames_sent)
{
    // cppcheck-suppress misra-c2012-21.6 ; D-001
    const int written = snprintf(s_reply, sizeof(s_reply),
                                 BOL_LINE_PREFIX
                                 "{\"proto\":%u,\"reply\":\"go\",\"seq\":%u,\"ok\":true,"
                                 "\"cell_id\":%u,\"done\":%s,\"frames_sent\":%u}\n",
                                 (unsigned int)BOL_PROTO_VERSION, (unsigned int)seq,
                                 (unsigned int)cell_id, is_done ? "true" : "false",
                                 (unsigned int)frames_sent);
    esp_err_t ret = bol_reply_fits(written);

    if (ret == ESP_OK) {
        ret = bol_write_reply();
    }

    return ret;
}

/**
 * @brief Records the result of one send.
 *
 * ESP-NOW runs this callback in the WiFi task, so it takes no lock and it
 * blocks on nothing. It gives the semaphore that the control task waits on.
 */
static void bol_console_on_send(const esp_now_send_info_t *tx_info,
                                esp_now_send_status_t status)
{
    (void)tx_info;
    s_send_was_ok = (status == ESP_NOW_SEND_SUCCESS);

    if (s_send_done != NULL) {
        (void)xSemaphoreGive(s_send_done);
    }
}

/**
 * @brief Puts one frame of the current pass on the air.
 */
static esp_err_t bol_port_send(void *context, const uint8_t *frame, size_t frame_bytes)
{
    (void)context;
    s_send_start_us = esp_timer_get_time();

    return esp_now_send(s_pass_address, frame, frame_bytes);
}

/**
 * @brief Waits for the callback of the last send and states its time.
 */
static esp_err_t bol_port_await(void *context, bool *out_is_ok, uint32_t *out_microseconds)
{
    esp_err_t ret = ESP_OK;

    (void)context;

    // ESP-NOW runs the send callback for every send that it accepted, so this
    // wait carries no timeout of its own. A callback that never runs stalls the
    // pass, and the host reads that silence through its liveness timeout.
    if (xSemaphoreTake(s_send_done, portMAX_DELAY) != pdTRUE) {
        ret = ESP_FAIL;
    } else {
        const int64_t elapsed_us = esp_timer_get_time() - s_send_start_us;

        *out_is_ok = s_send_was_ok;

        if (elapsed_us < 0) {
            *out_microseconds = 0U;
        } else if (elapsed_us > (int64_t)UINT32_MAX) {
            *out_microseconds = UINT32_MAX;
        } else {
            *out_microseconds = (uint32_t)elapsed_us;
        }
    }

    return ret;
}

/**
 * @brief Waits the stated milliseconds, after a send found no buffer.
 */
static void bol_port_wait_ms(void *context, uint32_t milliseconds)
{
    (void)context;
    vTaskDelay(pdMS_TO_TICKS(milliseconds));
}

/**
 * @brief Returns the millisecond counter of this node.
 */
static uint32_t bol_port_now_ms(void *context)
{
    // The quotient sits in its own object, so no composite expression takes a
    // cast to another type (MISRA Rule 10.8). The counter wraps about every 49
    // days, and the caller takes an unsigned difference, which holds across a
    // wrap.
    const int64_t now_ms = esp_timer_get_time() / 1000;

    (void)context;

    return (uint32_t)now_ms;
}

/**
 * @brief Writes a progress reply for the pass that runs.
 */
static void bol_port_progress(void *context, uint32_t frames_sent)
{
    (void)context;

    // The host restarts its liveness timeout on every line of the pass
    // (decision record 2026-11-12-serial-transport-reply-timeouts.md).
    (void)bol_reply_go(s_pass_seq, s_pass_cell_id, false, frames_sent);
}

/**
 * @brief Answers the role command.
 *
 * A receiver starts its task, and a sender registers the send callback. The
 * reply states the address of this node, which the host sends to the sender
 * as peer_mac and writes nowhere else.
 */
static esp_err_t bol_handle_role(const char *object, size_t length_bytes, uint32_t seq)
{
    char role_text[BOL_ROLE_TEXT_BYTES];
    char peer_text[BOL_MAC_TEXT_BYTES];
    char mac_text[BOL_MAC_TEXT_BYTES];
    uint8_t mac[BOL_MAC_BYTES];
    uint8_t peer_mac[BOL_MAC_BYTES];
    bol_role_t role = BOL_ROLE_NONE;
    uint32_t run_id = 0U;
    bool has_peer = false;
    esp_err_t ret;

    // The readers write a buffer only on success, so the clears hold every one
    // of them defined on each path.
    (void)memset(role_text, 0, sizeof(role_text));
    (void)memset(peer_text, 0, sizeof(peer_text));
    (void)memset(mac_text, 0, sizeof(mac_text));
    (void)memset(mac, 0, sizeof(mac));
    (void)memset(peer_mac, 0, sizeof(peer_mac));

    ret = bol_json_get_text(object, length_bytes, "role", role_text, sizeof(role_text));

    if (ret == ESP_OK) {
        ret = bol_node_parse_role(role_text, &role);
    }
    if (ret == ESP_OK) {
        ret = bol_json_get_u32(object, length_bytes, "run_id", &run_id);
    }
    if (ret == ESP_OK) {
        const esp_err_t peer_ret = bol_json_get_text(object, length_bytes, "peer_mac",
                                                     peer_text, sizeof(peer_text));

        if (peer_ret == ESP_OK) {
            ret = bol_node_parse_mac(peer_text, peer_mac);
            has_peer = (ret == ESP_OK);
        } else if (peer_ret != ESP_ERR_NOT_FOUND) {
            ret = peer_ret;
        } else {
            // A receiver carries no peer address, which the node module checks.
            has_peer = false;
        }
    }
    if (ret == ESP_OK) {
        ret = bol_node_set_role(&s_node, role, run_id, has_peer ? peer_mac : NULL);
    }
    if ((ret == ESP_OK) && (role == BOL_ROLE_RECEIVER)) {
        ret = bol_receiver_start();

        if (ret == ESP_ERR_INVALID_STATE) {
            // A second role command of one run finds the task already running.
            ret = ESP_OK;
        }
    }
    if ((ret == ESP_OK) && (role == BOL_ROLE_SENDER)) {
        ret = esp_now_register_send_cb(bol_console_on_send);
    }
    if (ret == ESP_OK) {
        ret = bol_radio_station_mac(mac);
    }
    if (ret == ESP_OK) {
        ret = bol_node_format_mac(mac, mac_text, sizeof(mac_text));
    }
    if (ret == ESP_OK) {
        // cppcheck-suppress misra-c2012-21.6 ; D-001
        const int written = snprintf(s_reply, sizeof(s_reply),
                                     BOL_LINE_PREFIX
                                     "{\"proto\":%u,\"reply\":\"role\",\"seq\":%u,"
                                     "\"ok\":true,\"role\":\"%s\",\"mac\":\"%s\"}\n",
                                     (unsigned int)BOL_PROTO_VERSION, (unsigned int)seq,
                                     bol_node_role_name(role), mac_text);

        ret = bol_reply_fits(written);
    }
    if (ret == ESP_OK) {
        ret = bol_write_reply();
    }

    return ret;
}

/**
 * @brief Answers the cell command.
 *
 * Applies the condition, then arms a receiver for the pass that follows. The
 * reply states the transmit power that the radio reports.
 */
static esp_err_t bol_handle_cell(const char *object, size_t length_bytes, uint32_t seq)
{
    char pass_text[BOL_PASS_TEXT_BYTES];
    bol_node_cell_t condition = {
        .cell_id = 0U, .channel = 0U, .power_set_value = 0U,
        .payload_bytes = 0U, .pass = BOL_PASS_BROADCAST, .frames = 0U
    };
    uint32_t cell_id = 0U;
    int8_t read_back = 0;
    esp_err_t ret;

    (void)memset(pass_text, 0, sizeof(pass_text));

    ret = bol_json_get_u32(object, length_bytes, "cell_id", &cell_id);

    if ((ret == ESP_OK) && (cell_id > BOL_FRAME_CELL_ID_MAX)) {
        // The check runs before the narrowing, so a wider value cannot wrap
        // into the range (CERT INT31-C).
        ret = ESP_ERR_INVALID_ARG;
    }
    if (ret == ESP_OK) {
        condition.cell_id = (uint16_t)cell_id;
        ret = bol_json_get_u32(object, length_bytes, "channel", &condition.channel);
    }
    if (ret == ESP_OK) {
        ret = bol_json_get_u32(object, length_bytes, "power_set_value", &condition.power_set_value);
    }
    if (ret == ESP_OK) {
        ret = bol_json_get_u32(object, length_bytes, "payload_bytes", &condition.payload_bytes);
    }
    if (ret == ESP_OK) {
        ret = bol_json_get_u32(object, length_bytes, "frames", &condition.frames);
    }
    if (ret == ESP_OK) {
        ret = bol_json_get_text(object, length_bytes, "pass", pass_text, sizeof(pass_text));
    }
    if (ret == ESP_OK) {
        ret = bol_node_parse_pass(pass_text, &condition.pass);
    }
    if (ret == ESP_OK) {
        ret = bol_node_set_cell(&s_node, &condition, (uint32_t)ESP_NOW_MAX_DATA_LEN_V2);
    }
    if (ret == ESP_OK) {
        ret = bol_radio_apply_condition((uint8_t)condition.channel, (int8_t)condition.power_set_value,
                                        &read_back);
    }
    if ((ret == ESP_OK) && (s_node.role == BOL_ROLE_SENDER) && s_node.has_peer) {
        ret = bol_radio_set_peers(s_node.peer_mac, (uint8_t)condition.channel);
    }
    if ((ret == ESP_OK) && (s_node.role == BOL_ROLE_RECEIVER)) {
        // The receiver takes the run, the cell, and the pass before the first
        // frame arrives (decision record
        // 2026-11-16-the-arm-and-finish-of-a-receiver-pass.md).
        ret = bol_receiver_arm(s_node.run_id, condition.cell_id, condition.pass,
                               s_node.packets_per_message);
    }
    if (ret == ESP_OK) {
        // cppcheck-suppress misra-c2012-21.6 ; D-001
        const int written = snprintf(s_reply, sizeof(s_reply),
                                     BOL_LINE_PREFIX
                                     "{\"proto\":%u,\"reply\":\"cell\",\"seq\":%u,"
                                     "\"ok\":true,\"cell_id\":%u,\"channel\":%u,"
                                     "\"payload_bytes\":%u,"
                                     "\"power_set_value_read_back\":%d}\n",
                                     (unsigned int)BOL_PROTO_VERSION, (unsigned int)seq,
                                     (unsigned int)condition.cell_id, (unsigned int)condition.channel,
                                     (unsigned int)condition.payload_bytes, (int)read_back);

        ret = bol_reply_fits(written);
    }
    if (ret == ESP_OK) {
        ret = bol_write_reply();
    }

    return ret;
}

/**
 * @brief Answers the go command, which runs one pass.
 *
 * The pass runs on this task, so the module that writes a control line is the
 * module that writes every progress reply, and a progress line sits between
 * two frames rather than between a send and its callback.
 */
static esp_err_t bol_handle_go(const char *object, size_t length_bytes, uint32_t seq)
{
    char pass_text[BOL_PASS_TEXT_BYTES];
    bol_pass_t pass = BOL_PASS_BROADCAST;
    uint32_t cell_id = 0U;
    uint32_t frames = 0U;
    esp_err_t ret;

    (void)memset(pass_text, 0, sizeof(pass_text));

    ret = bol_json_get_u32(object, length_bytes, "cell_id", &cell_id);

    if (ret == ESP_OK) {
        ret = bol_json_get_u32(object, length_bytes, "frames", &frames);
    }
    if (ret == ESP_OK) {
        ret = bol_json_get_text(object, length_bytes, "pass", pass_text, sizeof(pass_text));
    }
    if (ret == ESP_OK) {
        ret = bol_node_parse_pass(pass_text, &pass);
    }
    if ((ret == ESP_OK) && (cell_id > BOL_FRAME_CELL_ID_MAX)) {
        ret = ESP_ERR_INVALID_ARG;
    }
    if ((ret == ESP_OK) && (s_node.role != BOL_ROLE_SENDER)) {
        // Thinkbook section 7 sends the go command to the sender alone.
        ret = ESP_ERR_INVALID_STATE;
    }
    if (ret == ESP_OK) {
        ret = bol_node_check_cell(&s_node, (uint16_t)cell_id, pass);
    }
    if ((ret == ESP_OK) && (frames != s_node.condition.frames)) {
        // The host states one frame budget on the cell and the go of one pass.
        // A node that took another budget armed a receiver for frames that this
        // pass never sends.
        ret = ESP_ERR_INVALID_ARG;
    }
    if ((ret == ESP_OK) && (pass == BOL_PASS_UNICAST) && !s_node.has_peer) {
        ret = ESP_ERR_INVALID_STATE;
    }
    if (ret == ESP_OK) {
        const bol_sender_port_t port = {
            .send = bol_port_send,
            .await_callback = bol_port_await,
            .wait_ms = bol_port_wait_ms,
            .now_ms = bol_port_now_ms,
            .progress = bol_port_progress,
            .no_mem_code = ESP_ERR_ESPNOW_NO_MEM,
            .context = NULL
        };
        const bol_sender_pass_t sender_pass = {
            .run_id = s_node.run_id,
            .cell_id = s_node.condition.cell_id,
            .pass = pass,
            .frames = s_node.condition.frames,
            .payload_bytes = s_node.condition.payload_bytes,
            .payload_limit_bytes = (uint32_t)ESP_NOW_MAX_DATA_LEN_V2,
            .frame = s_frame,
            .frame_capacity_bytes = sizeof(s_frame)
        };

        s_pass_seq = seq;
        s_pass_cell_id = s_node.condition.cell_id;
        s_pass_address = (pass == BOL_PASS_UNICAST) ? s_node.peer_mac
                         : bol_radio_broadcast_address();

        ret = bol_sender_run_pass(&port, &sender_pass, &s_sender_counters);
    }
    if (ret == ESP_OK) {
        ret = bol_reply_go(seq, s_node.condition.cell_id, true, s_sender_counters.packets_sent);
    }

    return ret;
}

/**
 * @brief Appends the counters that a receiver reports for one pass.
 */
static esp_err_t bol_append_receiver_counters(size_t *offset,
                                              const bol_receiver_counters_t *counters)
{
    esp_err_t ret = bol_append_u32_key(offset, "packets_received", counters->packets_received);

    if (ret == ESP_OK) {
        ret = bol_append_u32_key(offset, "duplicates", counters->duplicates);
    }
    if (ret == ESP_OK) {
        ret = bol_append_u32_key(offset, "foreign_packets", counters->foreign_packets);
    }
    if (ret == ESP_OK) {
        ret = bol_append_u32_key(offset, "messages_complete", counters->messages_complete);
    }
    if (ret == ESP_OK) {
        ret = bol_append_u32_key(offset, "messages_incomplete", counters->messages_incomplete);
    }
    if (ret == ESP_OK) {
        ret = bol_append_u32_key(offset, "corrupt_packets", counters->corrupt_packets);
    }
    if (ret == ESP_OK) {
        ret = bol_append_u32_key(offset, "dropped_packets", counters->dropped_packets);
    }
    if (ret == ESP_OK) {
        ret = bol_append_histogram(offset, "loss_run_length_histogram",
                                   counters->loss_run_length_histogram);
    }
    if ((ret == ESP_OK) && (counters->rssi_count > 0U)) {
        // A pass that received no packet states no strength, which decision
        // record 2026-11-13-the-receiving-loop-of-a-pass.md requires.
        ret = bol_append_i32_key(offset, "rssi_min_dbm", counters->rssi_min_dbm);

        if (ret == ESP_OK) {
            ret = bol_append_mean_rssi(offset, counters->rssi_sum_dbm, counters->rssi_count);
        }
        if (ret == ESP_OK) {
            ret = bol_append_i32_key(offset, "rssi_max_dbm", counters->rssi_max_dbm);
        }
    }

    return ret;
}

/**
 * @brief Appends the counters that a sender reports for one pass.
 */
static esp_err_t bol_append_sender_counters(size_t *offset,
                                            const bol_sender_counters_t *counters)
{
    esp_err_t ret = bol_append_u32_key(offset, "messages_sent", counters->messages_sent);
    uint32_t index = 0U;

    if (ret == ESP_OK) {
        ret = bol_append_u32_key(offset, "packets_sent", counters->packets_sent);
    }
    if (ret == ESP_OK) {
        ret = bol_append_u32_key(offset, "callback_ok", counters->callback_ok);
    }
    if (ret == ESP_OK) {
        ret = bol_append_u32_key(offset, "callback_failed", counters->callback_failed);
    }
    if (ret == ESP_OK) {
        ret = bol_append_u32_key(offset, "no_mem_events", counters->no_mem_events);
    }
    if (ret == ESP_OK) {
        ret = bol_append_histogram(offset, "send_to_callback_us_histogram",
                                   counters->send_to_callback_us_histogram);
    }
    if (ret == ESP_OK) {
        ret = bol_append_text(offset, ",\"send_errors\":[");
    }

    while ((ret == ESP_OK) && (index < counters->send_error_kinds)) {
        // cppcheck-suppress misra-c2012-21.6 ; D-001
        const int written = snprintf(&s_reply[*offset], sizeof(s_reply) - *offset,
                                     "%s{\"err\":\"%s\",\"count\":%u}",
                                     (index == 0U) ? "" : ",",
                                     esp_err_to_name(counters->send_errors[index].code),
                                     (unsigned int)counters->send_errors[index].count);

        if ((written < 0) || ((size_t)written >= (sizeof(s_reply) - *offset))) {
            ret = ESP_ERR_INVALID_SIZE;
        } else {
            *offset += (size_t)written;
            index++;
        }
    }

    if (ret == ESP_OK) {
        ret = bol_append_text(offset, "]");
    }

    return ret;
}

/**
 * @brief Answers the stats command.
 *
 * A receiver closes its pass before it reads its counters, so the loss run
 * that the end of the pass left open reaches the histogram.
 */
static esp_err_t bol_handle_stats(const char *object, size_t length_bytes, uint32_t seq)
{
    char pass_text[BOL_PASS_TEXT_BYTES];
    bol_receiver_counters_t receiver_counters;
    bol_pass_t pass = BOL_PASS_BROADCAST;
    uint32_t cell_id = 0U;
    size_t offset = 0U;
    esp_err_t ret;

    (void)memset(pass_text, 0, sizeof(pass_text));
    (void)memset(&receiver_counters, 0, sizeof(receiver_counters));

    ret = bol_json_get_u32(object, length_bytes, "cell_id", &cell_id);

    if (ret == ESP_OK) {
        ret = bol_json_get_text(object, length_bytes, "pass", pass_text, sizeof(pass_text));
    }
    if (ret == ESP_OK) {
        ret = bol_node_parse_pass(pass_text, &pass);
    }
    if ((ret == ESP_OK) && (cell_id > BOL_FRAME_CELL_ID_MAX)) {
        ret = ESP_ERR_INVALID_ARG;
    }
    if (ret == ESP_OK) {
        ret = bol_node_check_cell(&s_node, (uint16_t)cell_id, pass);
    }
    if ((ret == ESP_OK) && (s_node.role == BOL_ROLE_RECEIVER)) {
        uint32_t positions = 0U;

        ret = bol_node_positions(&s_node, &positions);

        if (ret == ESP_OK) {
            const esp_err_t finish_ret = bol_receiver_finish(positions);

            if ((finish_ret != ESP_OK) && (finish_ret != ESP_ERR_INVALID_STATE)) {
                // A second stats command of one pass finds the pass closed,
                // and that is not an error.
                ret = finish_ret;
            }
        }
        if (ret == ESP_OK) {
            ret = bol_receiver_counters(&receiver_counters);
        }
    }
    if (ret == ESP_OK) {
        // cppcheck-suppress misra-c2012-21.6 ; D-001
        const int written = snprintf(s_reply, sizeof(s_reply),
                                     BOL_LINE_PREFIX
                                     "{\"proto\":%u,\"reply\":\"stats\",\"seq\":%u,"
                                     "\"ok\":true,\"cell_id\":%u,\"pass\":\"%s\"",
                                     (unsigned int)BOL_PROTO_VERSION, (unsigned int)seq,
                                     (unsigned int)cell_id, bol_node_pass_name(pass));

        ret = bol_reply_fits(written);

        if (ret == ESP_OK) {
            offset = (size_t)written;
            ret = bol_append_u32_key(&offset, "rejected_lines", s_rejected_line_count);
        }
    }
    if (ret == ESP_OK) {
        if (s_node.role == BOL_ROLE_RECEIVER) {
            ret = bol_append_receiver_counters(&offset, &receiver_counters);
        } else {
            ret = bol_append_sender_counters(&offset, &s_sender_counters);
        }
    }
    if (ret == ESP_OK) {
        ret = bol_append_text(&offset, "}\n");
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
    } else if (strcmp(command, "role") == 0) {
        ret = bol_handle_role(object, length_bytes, seq);
    } else if (strcmp(command, "cell") == 0) {
        ret = bol_handle_cell(object, length_bytes, seq);
    } else if (strcmp(command, "go") == 0) {
        ret = bol_handle_go(object, length_bytes, seq);
    } else if (strcmp(command, "stats") == 0) {
        ret = bol_handle_stats(object, length_bytes, seq);
    } else {
        ret = bol_reply_error(command, seq, ESP_ERR_NOT_FOUND);
    }

    if ((ret != ESP_OK) && (ret != ESP_FAIL)) {
        // The handler read a field that it could not use, or the reply of that
        // handler did not fit one line. The node names the code, so the host
        // reads an answer rather than the silence of a reply that it never sent.
        ret = bol_reply_error(command, seq, ret);
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

    bol_node_reset(&s_node);
    bol_stats_reset(&s_sender_counters);

    if (ret == ESP_OK) {
        // The semaphore holds static storage, so the component allocates no heap
        // (MISRA Dir 4.12).
        s_send_done = xSemaphoreCreateBinaryStatic(&s_send_done_buffer);

        if (s_send_done == NULL) {
            ret = ESP_ERR_NO_MEM;
        }
    }

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
