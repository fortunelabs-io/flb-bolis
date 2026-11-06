/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file host_runner.c
 * @brief Runs the reader test cases on the host (decision record
 *        2026-11-06-host-execution-of-the-reader-tests.md).
 *
 * The TEST_CASE macro of ESP-IDF registers each case from a constructor function
 * that calls unity_testcase_register. A host build therefore needs that function,
 * the output and clock hooks that unity_config.h declares, and an entry point that
 * runs every registered case. This file supplies all three, so the cases in
 * test_bol_json.c run with no ESP-IDF runtime, no container, and no node.
 *
 * ESP-IDF fixes the name of each hook, so the seven external names in this file
 * carry no bol_ prefix. Every other name here has internal linkage.
 *
 * tools/prep test compiles and runs this file. The command it uses is in that
 * script, and the stage reports the result.
 */

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#include "unity.h"

/** @brief The head of the list of cases that the constructors registered. */
static test_desc_t *s_head = NULL;

/**
 * @brief Appends one test case to the end of the registered list.
 *
 * A constructor function of the TEST_CASE macro calls this function before main
 * runs. The order of the constructors across translation units is not defined, so
 * the list order is the registration order and nothing more.
 *
 * ESP-IDF declares this name in unity_test_runner.h, so it carries no bol_ prefix.
 *
 * @param[in,out] desc The case to append. The function writes its next pointer.
 *                     A null pointer leaves the list unchanged.
 */
void unity_testcase_register(test_desc_t *desc)
{
    if (desc != NULL) {
        desc->next = NULL;

        if (s_head == NULL) {
            s_head = desc;
        } else {
            test_desc_t *tail = s_head;

            while (tail->next != NULL) {
                tail = tail->next;
            }
            tail->next = desc;
        }
    }
}

/**
 * @brief Writes one character of unity output to the standard output.
 *
 * ESP-IDF declares this name in unity_config.h, so it carries no bol_ prefix.
 *
 * @param[in] c The character to write, as an int, which is the type that the
 *              UNITY_OUTPUT_CHAR macro passes.
 */
void unity_putc(int c)
{
    (void)putchar(c);
}

/**
 * @brief Flushes the standard output.
 *
 * A stage reads the output of this program through a pipe, where the standard
 * output is a block buffer. Unity flushes at each case, which keeps the log of a
 * run that crashes partway through.
 *
 * ESP-IDF declares this name in unity_config.h, so it carries no bol_ prefix.
 */
void unity_flush(void)
{
    (void)fflush(stdout);
}

/**
 * @brief Returns an empty line, because the host run reads no input.
 *
 * The interactive menu of ESP-IDF calls this function to read a case to run. The
 * host run executes every case instead, so the function returns an empty string.
 *
 * ESP-IDF declares this name in unity_config.h, so it carries no bol_ prefix.
 *
 * @param[out] dst The buffer that receives the line.
 * @param[in]  len The capacity of dst in bytes. A value of zero writes nothing.
 */
void unity_gets(char *dst, size_t len)
{
    if ((dst != NULL) && (len > 0U)) {
        dst[0] = '\0';
    }
}

/**
 * @brief Starts the case clock, which this runner does not keep.
 *
 * The host run reports pass or fail and not duration, because the host timing of
 * the reader says nothing about its timing on a node. tools/prep measure reports
 * the duration of the whole stage instead.
 *
 * ESP-IDF declares this name in unity_config.h, so it carries no bol_ prefix.
 */
void unity_exec_time_start(void)
{
}

/**
 * @brief Stops the case clock, which this runner does not keep.
 *
 * ESP-IDF declares this name in unity_config.h, so it carries no bol_ prefix.
 */
void unity_exec_time_stop(void)
{
}

/**
 * @brief Returns the duration of a case in milliseconds, which is always zero.
 *
 * ESP-IDF declares this name in unity_config.h, so it carries no bol_ prefix.
 *
 * @return Zero milliseconds. This runner keeps no case clock.
 */
uint32_t unity_exec_time_get_ms(void)
{
    return 0U;
}

/**
 * @brief Prepares the state before one case. The reader holds no state.
 */
void setUp(void)
{
}

/**
 * @brief Releases the state after one case. The reader holds no state.
 */
void tearDown(void)
{
}

/**
 * @brief Runs every registered case and reports how many ran.
 *
 * The count on the last line lets a stage separate a clean run from a run that
 * stopped early. A run that reports fewer cases than the source declares has
 * stopped, even when it reports no failure.
 *
 * @return The count of failed cases, which UNITY_END returns. Zero means that
 *         every case passed.
 */
int main(void)
{
    const test_desc_t *test = NULL;
    int cases = 0;

    UNITY_BEGIN();

    for (test = s_head; test != NULL; test = test->next) {
        uint8_t index = 0U;

        // Unity names the file of UNITY_BEGIN until a caller states another one, so a
        // failing case would point at this runner instead of the file that holds it.
        UnitySetTestFile(test->file);

        for (index = 0U; index < test->test_fn_count; index++) {
            UnityDefaultTestRun(test->fn[index], test->name, test->line);
            cases++;
        }
    }

    printf("ran %d registered test cases\n", cases);
    return UNITY_END();
}
