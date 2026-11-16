/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file bol_receiver.c
 * @brief The receive callback, its queue, and the task that drains it
 *        (decision record 2026-11-13-the-receiving-loop-of-a-pass.md).
 *
 * The callback runs in the WiFi task. It copies the header bytes, the
 * length, and the strength of a packet to a queue and returns, so it blocks
 * that task for no longer than one copy (thinkbook section 7).
 *
 * The task decodes the header, separates a frame of another run from a
 * frame of this pass, checks the fill, and updates the counters. It runs
 * below the WiFi task, so a burst fills the queue rather than delaying the
 * driver.
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#include "esp_err.h"
#include "esp_log.h"
#include "esp_now.h"

#include "bol_frame.h"
#include "bol_receiver.h"
#include "bol_rxstats.h"
#include "bol_stats.h"

/**
 * @brief The stack of the receive task, in bytes.
 *
 * The task keeps its counters in static storage, so the stack carries one
 * queue entry and the decode of one header. High-water mark from
 * uxTaskGetStackHighWaterMark: <pending, no run has measured it yet>.
 */
#define BOL_RECEIVER_STACK_BYTES 3072

/**
 * @brief The priority of the receive task.
 *
 * The task runs below the WiFi task, which thinkbook section 7 requires, so
 * a burst of frames fills the queue rather than delaying the driver.
 */
#define BOL_RECEIVER_TASK_PRIORITY 4

/** @brief The bytes of one queue entry that hold the frame header. */
#define BOL_RECEIVER_HEADER_BYTES BOL_FRAME_HEADER_BYTES

/** @brief One received packet, as the callback hands it to the task. */
typedef struct {
    uint8_t header[BOL_RECEIVER_HEADER_BYTES]; /*!< The header bytes. */
    uint16_t length_bytes;                     /*!< The bytes that arrived. */
    int8_t rssi_dbm;                           /*!< The strength, in dBm. */
} bol_receiver_entry_t;

/** @brief The queue between the callback and the task. */
static QueueHandle_t s_queue = NULL;

/** @brief The counters of the pass. Only the receive task writes them. */
static bol_receiver_counters_t s_counters;

/**
 * @brief The packets that the callback could not place on the queue.
 *
 * The callback runs in the WiFi task and the drain runs in the receive task,
 * so the two reach this counter inside a critical section. The coding
 * standard allows a queue or a critical section and nothing else.
 */
static uint32_t s_dropped_packets = 0U;

/** @brief The lock that guards the dropped counter. */
// cppcheck-suppress misra-c2012-7.2 ; D-002, the initializer is an adopted macro
static portMUX_TYPE s_dropped_lock = portMUX_INITIALIZER_UNLOCKED;

/** @brief The run that the receiver counts frames of. */
static uint32_t s_run_id = 0U;

/** @brief The cell that the receiver counts frames of. */
static uint16_t s_cell_id = 0U;

/** @brief The pass that the receiver counts frames of. */
static bol_pass_t s_pass = BOL_PASS_BROADCAST;

/** @brief The packets of one message of the armed cell. */
static uint32_t s_packets_per_message = 1U;

/** @brief Whether a pass is armed. */
static bool s_is_armed = false;

/**
 * @brief Copies one received packet to the queue, from the WiFi task.
 *
 * A packet shorter than a header carries no header to copy, so the callback
 * counts it as a foreign packet and returns. A queue that is full raises
 * the dropped counter, which states that the node did not keep up.
 */
static void bol_receiver_on_receive(const esp_now_recv_info_t *info,
                                    const uint8_t *data, int data_len)
{
    bol_receiver_entry_t entry;

    if ((info != NULL) && (data != NULL) && (data_len >= (int)BOL_FRAME_HEADER_BYTES) &&
            (s_queue != NULL)) {
        (void)memcpy(entry.header, data, BOL_RECEIVER_HEADER_BYTES);
        entry.length_bytes = (uint16_t)data_len;
        entry.rssi_dbm = (info->rx_ctrl != NULL) ? info->rx_ctrl->rssi : 0;

        // The callback runs in the WiFi task, so it never blocks that task on
        // a queue that a burst filled. It waits for no tick and counts instead.
        if (xQueueSend(s_queue, &entry, 0) != pdTRUE) {
            portENTER_CRITICAL(&s_dropped_lock);
            s_dropped_packets++;
            portEXIT_CRITICAL(&s_dropped_lock);
        }
    }
}

/**
 * @brief Counts one packet that the queue delivered.
 */
static void bol_receiver_handle(const bol_receiver_entry_t *entry)
{
    bol_frame_header_t header;
    const esp_err_t ret = bol_frame_decode(entry->header, BOL_FRAME_HEADER_BYTES, &header);

    if (ret != ESP_OK) {
        s_counters.foreign_packets++;
    } else if ((header.run_id != s_run_id) || (header.cell_id != s_cell_id) ||
               (header.pass != s_pass)) {
        s_counters.foreign_packets++;
    } else if (!bol_frame_fill_is_intact(&header, entry->header,
                                         BOL_FRAME_HEADER_BYTES)) {
        s_counters.corrupt_packets++;
    } else {
        const uint32_t position = bol_rxstats_position(header.message_id,
                                                       header.fragment_index,
                                                       s_packets_per_message);

        (void)bol_rxstats_accept(&s_counters, position, (int32_t)entry->rssi_dbm);
    }
}

/**
 * @brief Drains the queue for the life of the node.
 */
static void bol_receiver_task(void *argument)
{
    (void)argument;

    for (;;) {
        bol_receiver_entry_t entry;

        if (xQueueReceive(s_queue, &entry, portMAX_DELAY) == pdTRUE) {
            if (s_is_armed) {
                bol_receiver_handle(&entry);
            }
        }
    }
}

// cppcheck-suppress misra-c2012-8.7 ; the console calls this when the four
// commands land, so the module keeps external linkage
esp_err_t bol_receiver_start(void)
{
    esp_err_t ret = ESP_OK;

    if (s_queue != NULL) {
        ret = ESP_ERR_INVALID_STATE;
    } else {
        // The storage and the control block hold static storage duration, so they
        // outlive this function and stay available for the life of the node.
        static uint8_t queue_storage[BOL_RECEIVER_QUEUE_ENTRIES *
                                                                sizeof(bol_receiver_entry_t)];
        static StaticQueue_t queue_block;

        s_queue = xQueueCreateStatic(BOL_RECEIVER_QUEUE_ENTRIES,
                                     sizeof(bol_receiver_entry_t),
                                     queue_storage, &queue_block);
        if (s_queue == NULL) {
            ret = ESP_ERR_NO_MEM;
        }
    }

    if (ret == ESP_OK) {
        bol_rxstats_reset(&s_counters);
        portENTER_CRITICAL(&s_dropped_lock);
        s_dropped_packets = 0U;
        portEXIT_CRITICAL(&s_dropped_lock);
        ret = esp_now_register_recv_cb(bol_receiver_on_receive);
    }

    if (ret == ESP_OK) {
        // The stack and the control block hold static storage duration, so they
        // outlive this function and stay available for the life of the node.
        static StackType_t receiver_stack[BOL_RECEIVER_STACK_BYTES];
        static StaticTask_t receiver_task_block;
        const TaskHandle_t handle = xTaskCreateStatic(bol_receiver_task, "bol_receiver",
                                                      BOL_RECEIVER_STACK_BYTES, NULL,
                                                      BOL_RECEIVER_TASK_PRIORITY,
                                                      receiver_stack,
                                                      &receiver_task_block);

        if (handle == NULL) {
            ret = ESP_ERR_NO_MEM;
        }
    }

    if (ret == ESP_OK) {
        static const char *const receiver_tag = "bolis";

        ESP_LOGI(receiver_tag, "The receive task drains a queue of %u entries.",
                 (unsigned int)BOL_RECEIVER_QUEUE_ENTRIES);
    }

    return ret;
}

// cppcheck-suppress misra-c2012-8.7 ; the console calls this when the four
// commands land, so the module keeps external linkage
esp_err_t bol_receiver_arm(uint32_t run_id, uint16_t cell_id, bol_pass_t pass,
                           uint32_t packets_per_message)
{
    esp_err_t ret = ESP_OK;

    if (packets_per_message == 0U) {
        ret = ESP_ERR_INVALID_ARG;
    } else {
        s_is_armed = false;
        bol_rxstats_reset(&s_counters);
        portENTER_CRITICAL(&s_dropped_lock);
        s_dropped_packets = 0U;
        portEXIT_CRITICAL(&s_dropped_lock);
        s_run_id = run_id;
        s_cell_id = cell_id;
        s_pass = pass;
        s_packets_per_message = packets_per_message;
        s_is_armed = true;
    }

    return ret;
}

// cppcheck-suppress misra-c2012-8.7 ; the console calls this when the four
// commands land, so the module keeps external linkage
esp_err_t bol_receiver_finish(uint32_t positions)
{
    esp_err_t ret = ESP_OK;

    if (!s_is_armed) {
        ret = ESP_ERR_INVALID_STATE;
    } else {
        s_is_armed = false;
        bol_rxstats_finish(&s_counters, positions);
    }

    return ret;
}

// cppcheck-suppress misra-c2012-8.7 ; the console calls this when the four
// commands land, so the module keeps external linkage
esp_err_t bol_receiver_counters(bol_receiver_counters_t *out_counters)
{
    esp_err_t ret = ESP_OK;

    if (out_counters == NULL) {
        ret = ESP_ERR_INVALID_ARG;
    } else {
        uint32_t dropped;

        portENTER_CRITICAL(&s_dropped_lock);
        dropped = s_dropped_packets;
        portEXIT_CRITICAL(&s_dropped_lock);

        *out_counters = s_counters;
        out_counters->dropped_packets = dropped;
    }

    return ret;
}
