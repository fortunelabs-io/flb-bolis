/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file bol_json.h
 * @brief Reader for the flat JSON object of a control line (decision record
 *        2026-10-01-control-line-wire-format.md).
 */

#ifndef BOL_JSON_H
#define BOL_JSON_H

#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"

/**
 * @brief Reads an unsigned decimal value from a flat JSON object.
 *
 * The reader accepts one complete object of key and value pairs, followed by
 * nothing but space. A value is a string, a number, or one of the literals
 * true, false, and null. A nested object, an array, a backslash in a string, a
 * trailing comma, and a missing closing brace each make the object invalid,
 * because a control line needs none of them and a truncated line must fail.
 * The first pair that carries the key wins.
 *
 * @param[in]  object               The object text. It does not need a null terminator.
 * @param[in]  object_length_bytes  The length of the object text in bytes.
 * @param[in]  key                  The null-terminated key to read.
 * @param[out] out_value            The value, written only when the call returns ESP_OK.
 *
 * @retval ESP_OK                 The value is in out_value.
 * @retval ESP_ERR_NOT_FOUND      The object holds no such key. out_value is unchanged.
 * @retval ESP_ERR_INVALID_ARG    An argument is NULL, the object is invalid, or the value
 *                                is not an unsigned decimal number. out_value is unchanged.
 * @retval ESP_ERR_INVALID_SIZE   The value does not fit in 32 bits. out_value is unchanged.
 */
esp_err_t bol_json_get_u32(const char *object, size_t object_length_bytes, const char *key,
                           uint32_t *out_value);

/**
 * @brief Reads a string value from a flat JSON object.
 *
 * Copies the value and a null terminator into the caller buffer. The reader
 * decodes no escape sequence, and it rejects an object whose string value holds
 * a backslash.
 *
 * @param[in]  object               The object text. It does not need a null terminator.
 * @param[in]  object_length_bytes  The length of the object text in bytes.
 * @param[in]  key                  The null-terminated key to read.
 * @param[out] out_text             The buffer that receives the value and its null terminator.
 * @param[in]  out_capacity_bytes   The size of out_text in bytes, including the null terminator.
 *
 * @retval ESP_OK                 out_text holds the null-terminated value.
 * @retval ESP_ERR_NOT_FOUND      The object holds no such key. out_text is unchanged.
 * @retval ESP_ERR_INVALID_ARG    An argument is NULL, out_capacity_bytes is zero, the object
 *                                is invalid, or the value is not a string. out_text is unchanged.
 * @retval ESP_ERR_INVALID_SIZE   The value and its null terminator do not fit in
 *                                out_capacity_bytes. out_text is unchanged.
 */
esp_err_t bol_json_get_text(const char *object, size_t object_length_bytes, const char *key,
                            char *out_text, size_t out_capacity_bytes);

#endif // BOL_JSON_H
