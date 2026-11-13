/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file bol_frame.c
 * @brief The frame header and the fill of a Bolis frame (decision record
 *        2026-11-12-frame-header-encoding.md).
 *
 * The layout holds 14 bytes, and every multi-byte field is big-endian:
 *
 *   offset 0  magic, two bytes
 *   offset 2  run ID, four bytes
 *   offset 6  cell and pass, two bytes, the pass in the top bit
 *   offset 8  message ID, four bytes
 *   offset 12 fragment index, one byte
 *   offset 13 fragment count, one byte
 *
 * The fill follows the header to the end of the frame. Its byte at offset i
 * is (seed + i) mod 256, and the seed is (message ID + fragment index) mod
 * 256. The firmware holds no pseudorandom generator, so the pattern is one
 * addition per byte and no stored state.
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#include "bol_frame.h"

/** @brief The offset of the magic. */
#define BOL_FRAME_OFFSET_MAGIC 0U

/** @brief The offset of the run ID. */
#define BOL_FRAME_OFFSET_RUN_ID 2U

/** @brief The offset of the cell and the pass. */
#define BOL_FRAME_OFFSET_CELL 6U

/** @brief The offset of the message ID. */
#define BOL_FRAME_OFFSET_MESSAGE_ID 8U

/** @brief The offset of the fragment index. */
#define BOL_FRAME_OFFSET_FRAGMENT_INDEX 12U

/** @brief The offset of the fragment count. */
#define BOL_FRAME_OFFSET_FRAGMENT_COUNT 13U

/** @brief The bit of the cell field that names the pass. */
#define BOL_FRAME_PASS_BIT 0x8000U

/** @brief The bits of the cell field that name the cell. */
#define BOL_FRAME_CELL_MASK 0x7FFFU

/** @brief The byte that one shift or mask keeps. */
#define BOL_FRAME_BYTE_MASK 0xFFU

/** @brief The bits of one byte. */
#define BOL_FRAME_BYTE_BITS 8U

/** @brief The values that one byte holds, which the fill counts around. */
#define BOL_FRAME_BYTE_VALUES 256U

/**
 * @brief Writes one unsigned value of two bytes, most significant byte first.
 */
static void bol_frame_write_u16(uint8_t *bytes, uint16_t value)
{
    bytes[0] = (uint8_t)((value >> BOL_FRAME_BYTE_BITS) & BOL_FRAME_BYTE_MASK);
    bytes[1] = (uint8_t)(value & BOL_FRAME_BYTE_MASK);
}

/**
 * @brief Writes one unsigned value of four bytes, most significant byte first.
 */
static void bol_frame_write_u32(uint8_t *bytes, uint32_t value)
{
    bytes[0] = (uint8_t)((value >> 24U) & BOL_FRAME_BYTE_MASK);
    bytes[1] = (uint8_t)((value >> 16U) & BOL_FRAME_BYTE_MASK);
    bytes[2] = (uint8_t)((value >> BOL_FRAME_BYTE_BITS) & BOL_FRAME_BYTE_MASK);
    bytes[3] = (uint8_t)(value & BOL_FRAME_BYTE_MASK);
}

/**
 * @brief Reads one unsigned value of two bytes, most significant byte first.
 */
static uint16_t bol_frame_read_u16(const uint8_t *bytes)
{
    const uint16_t high = (uint16_t)((uint16_t)bytes[0] << BOL_FRAME_BYTE_BITS);

    return (uint16_t)(high | (uint16_t)bytes[1]);
}

/**
 * @brief Reads one unsigned value of four bytes, most significant byte first.
 */
static uint32_t bol_frame_read_u32(const uint8_t *bytes)
{
    uint32_t value = (uint32_t)bytes[0] << 24U;

    value |= (uint32_t)bytes[1] << 16U;
    value |= (uint32_t)bytes[2] << BOL_FRAME_BYTE_BITS;
    value |= (uint32_t)bytes[3];

    return value;
}

uint8_t bol_frame_fill_byte(const bol_frame_header_t *header, size_t offset)
{
    uint8_t value = 0U;

    if (header != NULL) {
        const uint32_t seed = (header->message_id + (uint32_t)header->fragment_index) %
                              BOL_FRAME_BYTE_VALUES;
        const uint32_t step = (uint32_t)(offset % BOL_FRAME_BYTE_VALUES);

        value = (uint8_t)((seed + step) % BOL_FRAME_BYTE_VALUES);
    }

    return value;
}

esp_err_t bol_frame_encode(const bol_frame_header_t *header, uint8_t *out_frame,
                           size_t frame_bytes)
{
    esp_err_t ret = ESP_OK;

    if ((header == NULL) || (out_frame == NULL)) {
        ret = ESP_ERR_INVALID_ARG;
    } else if (frame_bytes < BOL_FRAME_HEADER_BYTES) {
        ret = ESP_ERR_INVALID_SIZE;
    } else if (header->cell_id > (uint16_t)BOL_FRAME_CELL_ID_MAX) {
        ret = ESP_ERR_INVALID_ARG;
    } else {
        uint16_t cell_field = (uint16_t)(header->cell_id & (uint16_t)BOL_FRAME_CELL_MASK);
        size_t offset = 0U;

        if (header->pass == BOL_PASS_UNICAST) {
            cell_field = (uint16_t)(cell_field | (uint16_t)BOL_FRAME_PASS_BIT);
        }

        out_frame[BOL_FRAME_OFFSET_MAGIC] = (uint8_t)BOL_FRAME_MAGIC_FIRST;
        out_frame[BOL_FRAME_OFFSET_MAGIC + 1U] = (uint8_t)BOL_FRAME_MAGIC_SECOND;
        bol_frame_write_u32(&out_frame[BOL_FRAME_OFFSET_RUN_ID], header->run_id);
        bol_frame_write_u16(&out_frame[BOL_FRAME_OFFSET_CELL], cell_field);
        bol_frame_write_u32(&out_frame[BOL_FRAME_OFFSET_MESSAGE_ID], header->message_id);
        out_frame[BOL_FRAME_OFFSET_FRAGMENT_INDEX] = header->fragment_index;
        out_frame[BOL_FRAME_OFFSET_FRAGMENT_COUNT] = header->fragment_count;

        while ((offset + BOL_FRAME_HEADER_BYTES) < frame_bytes) {
            out_frame[BOL_FRAME_HEADER_BYTES + offset] = bol_frame_fill_byte(header, offset);
            offset++;
        }
    }

    return ret;
}

esp_err_t bol_frame_decode(const uint8_t *frame, size_t frame_bytes,
                           bol_frame_header_t *out_header)
{
    esp_err_t ret = ESP_OK;

    if ((frame == NULL) || (out_header == NULL)) {
        ret = ESP_ERR_INVALID_ARG;
    } else if (frame_bytes < BOL_FRAME_HEADER_BYTES) {
        ret = ESP_ERR_INVALID_SIZE;
    } else if ((frame[BOL_FRAME_OFFSET_MAGIC] != (uint8_t)BOL_FRAME_MAGIC_FIRST) ||
               (frame[BOL_FRAME_OFFSET_MAGIC + 1U] != (uint8_t)BOL_FRAME_MAGIC_SECOND)) {
        ret = ESP_ERR_NOT_FOUND;
    } else {
        const uint16_t cell_field = bol_frame_read_u16(&frame[BOL_FRAME_OFFSET_CELL]);

        out_header->run_id = bol_frame_read_u32(&frame[BOL_FRAME_OFFSET_RUN_ID]);
        out_header->cell_id = (uint16_t)(cell_field & (uint16_t)BOL_FRAME_CELL_MASK);
        if ((cell_field & (uint16_t)BOL_FRAME_PASS_BIT) != 0U) {
            out_header->pass = BOL_PASS_UNICAST;
        } else {
            out_header->pass = BOL_PASS_BROADCAST;
        }
        out_header->message_id = bol_frame_read_u32(&frame[BOL_FRAME_OFFSET_MESSAGE_ID]);
        out_header->fragment_index = frame[BOL_FRAME_OFFSET_FRAGMENT_INDEX];
        out_header->fragment_count = frame[BOL_FRAME_OFFSET_FRAGMENT_COUNT];
    }

    return ret;
}

bool bol_frame_fill_is_intact(const bol_frame_header_t *header, const uint8_t *frame,
                              size_t frame_bytes)
{
    bool is_intact = (header != NULL) && (frame != NULL) &&
                     (frame_bytes >= BOL_FRAME_HEADER_BYTES);
    size_t offset = 0U;

    while (is_intact && ((offset + BOL_FRAME_HEADER_BYTES) < frame_bytes)) {
        if (frame[BOL_FRAME_HEADER_BYTES + offset] != bol_frame_fill_byte(header, offset)) {
            is_intact = false;
        } else {
            offset++;
        }
    }

    return is_intact;
}
