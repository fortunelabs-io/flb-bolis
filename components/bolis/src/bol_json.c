/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file bol_json.c
 * @brief Reader for the flat JSON object of a control line (decision record
 *        2026-10-01-control-line-wire-format.md).
 */

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "esp_err.h"

#include "bol_json.h"

/** @brief The kind of a JSON value that the reader accepts. */
typedef enum {
    BOL_JSON_KIND_TEXT = 0,    /*!< A quoted string */
    BOL_JSON_KIND_NUMBER = 1,  /*!< A number */
    BOL_JSON_KIND_LITERAL = 2  /*!< One of true, false, and null */
} bol_json_kind_t;

/** @brief The position, the length, and the kind of one value inside an object. */
typedef struct {
    size_t index;          /*!< Offset of the first byte of the value inside the object */
    size_t length_bytes;   /*!< Length of the value in bytes, without the quotes of a string */
    bol_json_kind_t kind;  /*!< Kind of the value */
} bol_json_span_t;

/** @brief Reports whether a byte separates tokens. */
static bool bol_is_space(char value)
{
    return (value == ' ') || (value == '\t') || (value == '\r') || (value == '\n');
}

/** @brief Reports whether a byte can start a number. */
static bool bol_is_number_start(char value)
{
    return ((value >= '0') && (value <= '9')) || (value == '-');
}

/** @brief Reports whether a byte can continue a number. */
static bool bol_is_number_body(char value)
{
    return ((value >= '0') && (value <= '9')) || (value == '-') || (value == '+') ||
           (value == '.') || (value == 'e') || (value == 'E');
}

/** @brief Reports whether a byte can belong to the literal true, false, or null. */
static bool bol_is_literal_body(char value)
{
    return (value >= 'a') && (value <= 'z');
}

/**
 * @brief Returns the offset of the first byte at or after an offset that is not a separator.
 */
static size_t bol_skip_space(const char *object, size_t length_bytes, size_t index)
{
    size_t next = index;

    while ((next < length_bytes) && bol_is_space(object[next])) {
        next++;
    }

    return next;
}

/**
 * @brief Scans a quoted string that starts at an offset.
 *
 * A backslash ends the scan without a closing quote, so the caller rejects the
 * object. The reader decodes no escape sequence.
 */
static esp_err_t bol_scan_text(const char *object, size_t length_bytes, size_t *index,
                               bol_json_span_t *out_span)
{
    esp_err_t ret = ESP_ERR_INVALID_ARG;
    const size_t open = *index;

    if ((open < length_bytes) && (object[open] == '"')) {
        const size_t start = open + 1U;
        size_t end = start;

        while ((end < length_bytes) && (object[end] != '"') && (object[end] != '\\')) {
            end++;
        }

        if ((end < length_bytes) && (object[end] == '"')) {
            out_span->index = start;
            out_span->length_bytes = end - start;
            out_span->kind = BOL_JSON_KIND_TEXT;
            *index = end + 1U;
            ret = ESP_OK;
        }
    }

    return ret;
}

/**
 * @brief Scans one value that starts at an offset.
 *
 * A nested object and an array are invalid, because a control line carries one
 * flat object.
 */
static esp_err_t bol_scan_value(const char *object, size_t length_bytes, size_t *index,
                                bol_json_span_t *out_span)
{
    esp_err_t ret = ESP_OK;
    size_t next = *index;

    if (next >= length_bytes) {
        ret = ESP_ERR_INVALID_ARG;
    } else if (object[next] == '"') {
        ret = bol_scan_text(object, length_bytes, index, out_span);
    } else if (bol_is_number_start(object[next])) {
        const size_t start = next;

        while ((next < length_bytes) && bol_is_number_body(object[next])) {
            next++;
        }
        out_span->index = start;
        out_span->length_bytes = next - start;
        out_span->kind = BOL_JSON_KIND_NUMBER;
        *index = next;
    } else if (bol_is_literal_body(object[next])) {
        const size_t start = next;

        while ((next < length_bytes) && bol_is_literal_body(object[next])) {
            next++;
        }
        out_span->index = start;
        out_span->length_bytes = next - start;
        out_span->kind = BOL_JSON_KIND_LITERAL;
        *index = next;
    } else {
        ret = ESP_ERR_INVALID_ARG;
    }

    return ret;
}

/**
 * @brief Reports whether two byte ranges of the same length hold the same bytes.
 *
 * Rules 21.14 and 21.16 rule out memcmp for this comparison, because the key is a
 * null-terminated string and both pointers address plain characters.
 */
static bool bol_bytes_equal(const char *left, const char *right, size_t count)
{
    bool equal = true;
    size_t index = 0U;

    while (equal && (index < count)) {
        if (left[index] != right[index]) {
            equal = false;
        } else {
            index++;
        }
    }

    return equal;
}

/**
 * @brief Scans one key and value pair that starts at an offset.
 */
static esp_err_t bol_scan_pair(const char *object, size_t length_bytes, size_t *index,
                               bol_json_span_t *out_key, bol_json_span_t *out_value)
{
    esp_err_t ret = bol_scan_text(object, length_bytes, index, out_key);

    if (ret == ESP_OK) {
        const size_t next = bol_skip_space(object, length_bytes, *index);

        if ((next < length_bytes) && (object[next] == ':')) {
            *index = bol_skip_space(object, length_bytes, next + 1U);
            ret = bol_scan_value(object, length_bytes, index, out_value);
        } else {
            ret = ESP_ERR_INVALID_ARG;
        }
    }

    return ret;
}

/**
 * @brief Finds the value of a key in a flat object.
 *
 * Walks every pair in order, so a key inside a string value never matches. The
 * walk continues past a match to the closing brace, so a truncated object and a
 * trailing comma each fail instead of yielding a value. The first match wins.
 */
static esp_err_t bol_find_key(const char *object, size_t length_bytes, const char *key,
                              bol_json_span_t *out_span)
{
    esp_err_t ret = ESP_OK;
    const size_t key_length_bytes = strlen(key);
    size_t next = bol_skip_space(object, length_bytes, 0U);
    bool scanning = false;
    bool closed = false;
    bool found = false;

    if ((next < length_bytes) && (object[next] == '{')) {
        next++;
        scanning = true;
    } else {
        ret = ESP_ERR_INVALID_ARG;
    }

    while (scanning) {
        bol_json_span_t key_span = {0U, 0U, BOL_JSON_KIND_TEXT};
        bol_json_span_t value_span = {0U, 0U, BOL_JSON_KIND_TEXT};

        next = bol_skip_space(object, length_bytes, next);

        if ((next < length_bytes) && (object[next] == '}')) {
            closed = true;
            scanning = false;
        } else if (bol_scan_pair(object, length_bytes, &next, &key_span, &value_span) != ESP_OK) {
            ret = ESP_ERR_INVALID_ARG;
            scanning = false;
        } else {
            if (!found && (key_span.length_bytes == key_length_bytes) &&
                    bol_bytes_equal(&object[key_span.index], key, key_length_bytes)) {
                *out_span = value_span;
                found = true;
            }

            next = bol_skip_space(object, length_bytes, next);

            if ((next < length_bytes) && (object[next] == ',')) {
                // A comma announces another pair, so anything but a key makes the object invalid.
                next = bol_skip_space(object, length_bytes, next + 1U);
                if ((next >= length_bytes) || (object[next] != '"')) {
                    ret = ESP_ERR_INVALID_ARG;
                    scanning = false;
                }
            } else if ((next < length_bytes) && (object[next] == '}')) {
                closed = true;
                scanning = false;
            } else {
                ret = ESP_ERR_INVALID_ARG;
                scanning = false;
            }
        }
    }

    if (ret == ESP_OK) {
        // The closing brace carries the index of the brace itself, so the tail starts after it.
        const size_t tail = bol_skip_space(object, length_bytes, next + 1U);

        if (!closed || (tail < length_bytes)) {
            ret = ESP_ERR_INVALID_ARG;
        } else if (!found) {
            ret = ESP_ERR_NOT_FOUND;
        } else {
            ret = ESP_OK;
        }
    }

    return ret;
}

/**
 * @brief Converts decimal text to an unsigned 32-bit value.
 *
 * Rejects a value above the range of the type before the multiply, so the
 * result never wraps.
 */
static esp_err_t bol_parse_u32(const char *text, size_t length_bytes, uint32_t *out_value)
{
    esp_err_t ret = ESP_OK;
    uint32_t value = 0U;
    size_t index = 0U;

    if (length_bytes == 0U) {
        ret = ESP_ERR_INVALID_ARG;
    }

    while ((ret == ESP_OK) && (index < length_bytes)) {
        const char digit_text = text[index];

        if ((digit_text < '0') || (digit_text > '9')) {
            ret = ESP_ERR_INVALID_ARG;
        } else {
            const int digit_signed = (int)digit_text - (int)'0';
            const uint32_t digit = (uint32_t)digit_signed;

            if (value > ((UINT32_MAX - digit) / 10U)) {
                ret = ESP_ERR_INVALID_SIZE;
            } else {
                value = (value * 10U) + digit;
                index++;
            }
        }
    }

    if (ret == ESP_OK) {
        *out_value = value;
    }

    return ret;
}

esp_err_t bol_json_get_u32(const char *object, size_t object_length_bytes, const char *key,
                           uint32_t *out_value)
{
    esp_err_t ret = ESP_ERR_INVALID_ARG;
    bol_json_span_t span = {0U, 0U, BOL_JSON_KIND_TEXT};

    if ((object != NULL) && (key != NULL) && (out_value != NULL)) {
        ret = bol_find_key(object, object_length_bytes, key, &span);
    }

    if (ret == ESP_OK) {
        if (span.kind != BOL_JSON_KIND_NUMBER) {
            ret = ESP_ERR_INVALID_ARG;
        } else {
            ret = bol_parse_u32(&object[span.index], span.length_bytes, out_value);
        }
    }

    return ret;
}

esp_err_t bol_json_get_text(const char *object, size_t object_length_bytes, const char *key,
                            char *out_text, size_t out_capacity_bytes)
{
    esp_err_t ret = ESP_ERR_INVALID_ARG;
    bol_json_span_t span = {0U, 0U, BOL_JSON_KIND_TEXT};

    if ((object != NULL) && (key != NULL) && (out_text != NULL) && (out_capacity_bytes > 0U)) {
        ret = bol_find_key(object, object_length_bytes, key, &span);
    }

    if (ret == ESP_OK) {
        if (span.kind != BOL_JSON_KIND_TEXT) {
            ret = ESP_ERR_INVALID_ARG;
        } else if (span.length_bytes >= out_capacity_bytes) {
            ret = ESP_ERR_INVALID_SIZE;
        } else {
            // The check above confirms that the value and its null terminator fit the caller
            // buffer. The return value of memcpy is the destination, which the caller holds.
            (void)memcpy(out_text, &object[span.index], span.length_bytes);
            out_text[span.length_bytes] = '\0';
        }
    }

    return ret;
}
