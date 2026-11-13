/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file bol_frame.h
 * @brief The 14-byte header of a Bolis frame and the fill that follows it
 *        (decision record 2026-11-12-frame-header-encoding.md).
 *
 * Every multi-byte field is big-endian, with the most significant byte first,
 * so a hex dump of a frame reads in field order. The encoder and the decoder
 * touch one byte at a time, because MISRA C:2012 Rule 11.3 rules out a cast
 * from a receive buffer to a structure pointer.
 *
 * The fill holds every byte after the header, to the end of that frame. It
 * detects a change to any byte of one frame and a frame shorter than the
 * length that its header implies. It does not tell one frame from another,
 * and the header does that.
 */

#ifndef BOL_FRAME_H
#define BOL_FRAME_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/** @brief The bytes of the frame header (thinkbook section 7). */
#define BOL_FRAME_HEADER_BYTES 14U

/** @brief The first byte of the magic that marks a Bolis frame. */
#define BOL_FRAME_MAGIC_FIRST 0x42U

/** @brief The second byte of the magic that marks a Bolis frame. */
#define BOL_FRAME_MAGIC_SECOND 0x4FU

/** @brief The widest cell that the low fifteen bits of the header carry. */
#define BOL_FRAME_CELL_ID_MAX 32767U

/** @brief The widest fragment index or count that one byte carries. */
#define BOL_FRAME_FRAGMENT_MAX 255U

/**
 * @brief The pass that the top bit of the cell field names.
 *
 * Every run carries a broadcast pass, and a unicast pass follows it in a
 * unicast run, so 0 names the pass that every run holds.
 */
typedef enum {
    BOL_PASS_BROADCAST = 0, /*!< The pass that every run sends. */
    BOL_PASS_UNICAST = 1    /*!< The pass that a unicast run adds. */
} bol_pass_t;

/**
 * @brief The fields of one frame header.
 *
 * The magic is not a field here. The encoder writes it, and the decoder
 * checks it, so no caller states it.
 */
typedef struct {
    uint32_t run_id;         /*!< The run that this frame belongs to. */
    uint16_t cell_id;        /*!< The cell, 0 to BOL_FRAME_CELL_ID_MAX. */
    bol_pass_t pass;         /*!< The pass of this frame. */
    uint32_t message_id;     /*!< The message that this frame carries part of. */
    uint8_t fragment_index;  /*!< The fragment, counting from 0. */
    uint8_t fragment_count;  /*!< The fragments of the whole message. */
} bol_frame_header_t;

/**
 * @brief Returns the fill byte that one offset of a frame holds.
 *
 * The seed of a frame is the sum of its message ID and its fragment index,
 * taken low byte first, so the receiver reads both from the header that it
 * already checked.
 *
 * @param[in] header  The header of the frame.
 * @param[in] offset  The offset inside the fill, counting from 0.
 *
 * @return The byte that the fill holds at that offset.
 */
uint8_t bol_frame_fill_byte(const bol_frame_header_t *header, size_t offset);

/**
 * @brief Writes one frame: its header, then its fill.
 *
 * @param[in]  header       The fields of the header. The cell sits at or
 *                          below BOL_FRAME_CELL_ID_MAX.
 * @param[out] out_frame    The buffer that receives the frame.
 * @param[in]  frame_bytes  The bytes to write, BOL_FRAME_HEADER_BYTES or more.
 *
 * @retval ESP_OK                 The buffer holds the frame.
 * @retval ESP_ERR_INVALID_ARG    A pointer is NULL, or the cell sits above
 *                                its range.
 * @retval ESP_ERR_INVALID_SIZE   The buffer is shorter than the header.
 */
esp_err_t bol_frame_encode(const bol_frame_header_t *header, uint8_t *out_frame,
                           size_t frame_bytes);

/**
 * @brief Reads the header of one received frame.
 *
 * The reader treats every byte as untrusted (MISRA Dir 4.14). It checks the
 * length and the magic before it reads a field.
 *
 * @param[in]  frame        The bytes that arrived.
 * @param[in]  frame_bytes  The bytes that arrived, as the driver reported.
 * @param[out] out_header   The fields that the header states.
 *
 * @retval ESP_OK                 The header is a Bolis header, and out_header
 *                                holds its fields.
 * @retval ESP_ERR_INVALID_ARG    A pointer is NULL.
 * @retval ESP_ERR_INVALID_SIZE   The frame is shorter than the header.
 * @retval ESP_ERR_NOT_FOUND      The magic names another sender.
 */
esp_err_t bol_frame_decode(const uint8_t *frame, size_t frame_bytes,
                           bol_frame_header_t *out_header);

/**
 * @brief Reports whether the fill of one frame holds the bytes it should.
 *
 * @param[in] header       The header that `bol_frame_decode` read from this
 *                         frame.
 * @param[in] frame        The bytes that arrived.
 * @param[in] frame_bytes  The bytes that arrived.
 *
 * @return True when every fill byte holds its expected value. A frame of
 *         BOL_FRAME_HEADER_BYTES holds no fill, and returns true.
 */
bool bol_frame_fill_is_intact(const bol_frame_header_t *header, const uint8_t *frame,
                              size_t frame_bytes);

#ifdef __cplusplus
}
#endif

#endif /* BOL_FRAME_H */
