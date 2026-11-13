/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * The TEST_CASE macro of unity builds the name of each generated function from
 * __LINE__, so a case at one line number collides with a case at the same line
 * number in another test file. The collision comes from the expansion of an
 * adopted macro, which deviation D-002 covers. It belongs to the pair of files
 * rather than to one of them, so each test file carries this suppression. A
 * suppression on one line would move the collision to the next matching case.
 */
/* cppcheck-suppress-file misra-c2012-5.9 */

/**
 * @file test_bol_json.c
 * @brief Tests of the control line reader (decision record
 *        2026-10-01-control-line-wire-format.md).
 *
 * The reader takes a control line from the host, so every test states what the
 * reader does with input that the contract does not allow.
 */

#include <stdint.h>
#include <string.h>

#include "unity.h"

#include "bol_json.h"

/** @brief The host line that the accepted record states for the hello command. */
#define BOL_TEST_HELLO_LINE "{\"proto\":1,\"cmd\":\"hello\",\"seq\":1}"

/**
 * @brief Reads an unsigned value from a line, and returns the code of the reader.
 */
static esp_err_t read_u32(const char *line, const char *key, uint32_t *out_value)
{
    return bol_json_get_u32(line, strlen(line), key, out_value);
}

/**
 * @brief Reads a string value from a line, and returns the code of the reader.
 */
static esp_err_t read_text(const char *line, const char *key, char *out_text,
                           size_t out_capacity_bytes)
{
    return bol_json_get_text(line, strlen(line), key, out_text, out_capacity_bytes);
}

TEST_CASE("the reader takes every key of a hello line", "[bol_json]")
{
    uint32_t value = 0U;
    char text[16];

    TEST_ASSERT_EQUAL_INT(ESP_OK, read_u32(BOL_TEST_HELLO_LINE, "proto", &value));
    TEST_ASSERT_EQUAL_UINT32(1U, value);

    TEST_ASSERT_EQUAL_INT(ESP_OK, read_u32(BOL_TEST_HELLO_LINE, "seq", &value));
    TEST_ASSERT_EQUAL_UINT32(1U, value);

    TEST_ASSERT_EQUAL_INT(ESP_OK, read_text(BOL_TEST_HELLO_LINE, "cmd", text, sizeof(text)));
    TEST_ASSERT_EQUAL_STRING("hello", text);
}

TEST_CASE("the reader takes a key in any position and with any spacing", "[bol_json]")
{
    uint32_t value = 0U;
    char text[16];

    TEST_ASSERT_EQUAL_INT(ESP_OK, read_u32("{\"cmd\":\"go\",\"proto\":1,\"seq\":77}", "seq", &value));
    TEST_ASSERT_EQUAL_UINT32(77U, value);

    TEST_ASSERT_EQUAL_INT(ESP_OK,
                          read_text("  { \"cmd\" : \"stats\" , \"seq\" : 4 }  ", "cmd", text,
                                    sizeof(text)));
    TEST_ASSERT_EQUAL_STRING("stats", text);

    // The console passes the line with the newline that the reader of the stream left.
    TEST_ASSERT_EQUAL_INT(ESP_OK, read_u32("{\"seq\":1}\n", "seq", &value));
    TEST_ASSERT_EQUAL_UINT32(1U, value);
}

TEST_CASE("the reader takes the whole range of a sequence number", "[bol_json]")
{
    uint32_t value = 1U;

    TEST_ASSERT_EQUAL_INT(ESP_OK, read_u32("{\"seq\":0}", "seq", &value));
    TEST_ASSERT_EQUAL_UINT32(0U, value);

    TEST_ASSERT_EQUAL_INT(ESP_OK, read_u32("{\"seq\":4294967295}", "seq", &value));
    TEST_ASSERT_EQUAL_UINT32(4294967295U, value);
}

TEST_CASE("the reader reports an absent key", "[bol_json]")
{
    uint32_t value = 0U;
    char text[16];

    TEST_ASSERT_EQUAL_INT(ESP_ERR_NOT_FOUND, read_u32("{\"cmd\":\"hello\"}", "seq", &value));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_NOT_FOUND, read_u32("{}", "seq", &value));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_NOT_FOUND, read_text("{\"seq\":1}", "cmd", text, sizeof(text)));
}

TEST_CASE("the reader matches a key only where a key belongs", "[bol_json]")
{
    uint32_t value = 0U;
    char text[16];

    // The name of the key also appears as a value, which must not match.
    TEST_ASSERT_EQUAL_INT(ESP_OK,
                          read_text("{\"a\":\"cmd\",\"cmd\":\"hello\"}", "cmd", text, sizeof(text)));
    TEST_ASSERT_EQUAL_STRING("hello", text);

    TEST_ASSERT_EQUAL_INT(ESP_OK, read_u32("{\"xseq\":5,\"seq\":9}", "seq", &value));
    TEST_ASSERT_EQUAL_UINT32(9U, value);

    TEST_ASSERT_EQUAL_INT(ESP_ERR_NOT_FOUND, read_u32("{\"seqx\":5}", "seq", &value));

    // The first pair that carries the key wins.
    TEST_ASSERT_EQUAL_INT(ESP_OK,
                          read_text("{\"cmd\":\"go\",\"cmd\":\"stats\"}", "cmd", text,
                                    sizeof(text)));
    TEST_ASSERT_EQUAL_STRING("go", text);
}

TEST_CASE("the reader refuses a value of the wrong kind", "[bol_json]")
{
    uint32_t value = 0U;
    char text[16];

    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, read_u32("{\"seq\":\"1\"}", "seq", &value));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, read_u32("{\"seq\":true}", "seq", &value));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, read_text("{\"cmd\":5}", "cmd", text, sizeof(text)));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          read_text("{\"cmd\":null}", "cmd", text, sizeof(text)));
}

TEST_CASE("the reader refuses a value the contract does not carry", "[bol_json]")
{
    uint32_t value = 0U;
    char text[16];

    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, read_u32("{\"seq\":{\"a\":1}}", "seq", &value));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, read_u32("{\"seq\":[1,2]}", "seq", &value));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, read_u32("{\"seq\":-1}", "seq", &value));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, read_u32("{\"seq\":1.5}", "seq", &value));

    // The reader decodes no escape sequence, so a backslash makes the object invalid.
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          read_text("{\"cmd\":\"he\\\\llo\"}", "cmd", text, sizeof(text)));
}

TEST_CASE("the reader refuses a number outside 32 bits", "[bol_json]")
{
    uint32_t value = 0U;

    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_SIZE, read_u32("{\"seq\":4294967296}", "seq", &value));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_SIZE,
                          read_u32("{\"seq\":99999999999999999999}", "seq", &value));
}

TEST_CASE("the reader refuses a malformed or truncated object", "[bol_json]")
{
    uint32_t value = 0U;

    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, read_u32("\"seq\":1", "seq", &value));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, read_u32("", "seq", &value));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, read_u32("{", "seq", &value));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, read_u32("}", "seq", &value));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, read_u32("{\"seq\" 1}", "seq", &value));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, read_u32("{\"seq", "seq", &value));

    // A line that lost its closing brace must fail rather than yield a value.
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, read_u32("{\"seq\":1", "seq", &value));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, read_u32("{\"cmd\":\"go\",}", "seq", &value));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, read_u32("{\"seq\":1,", "seq", &value));

    // Only space may follow the object, so a second object on the line fails.
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, read_u32("{\"seq\":1} junk", "seq", &value));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, read_u32("{\"seq\":1}{\"seq\":2}", "seq", &value));
}

TEST_CASE("the reader keeps a value inside the caller buffer", "[bol_json]")
{
    char text[16];

    // The value and its null terminator fill the buffer exactly.
    TEST_ASSERT_EQUAL_INT(ESP_OK, read_text("{\"cmd\":\"hello\"}", "cmd", text, 6U));
    TEST_ASSERT_EQUAL_STRING("hello", text);

    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_SIZE, read_text("{\"cmd\":\"hello\"}", "cmd", text, 5U));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, read_text("{\"cmd\":\"hello\"}", "cmd", text, 0U));

    TEST_ASSERT_EQUAL_INT(ESP_OK, read_text("{\"cmd\":\"\"}", "cmd", text, sizeof(text)));
    TEST_ASSERT_EQUAL_STRING("", text);
}

TEST_CASE("the reader refuses a null argument", "[bol_json]")
{
    uint32_t value = 0U;
    char text[16];

    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, bol_json_get_u32(NULL, 5U, "seq", &value));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          bol_json_get_u32(BOL_TEST_HELLO_LINE, strlen(BOL_TEST_HELLO_LINE), "seq",
                                           NULL));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG, bol_json_get_text(NULL, 5U, "cmd", text,
                                                                 sizeof(text)));
    TEST_ASSERT_EQUAL_INT(ESP_ERR_INVALID_ARG,
                          bol_json_get_text(BOL_TEST_HELLO_LINE, strlen(BOL_TEST_HELLO_LINE), "cmd",
                                            NULL, sizeof(text)));
}
