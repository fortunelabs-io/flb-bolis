/*
 * SPDX-FileCopyrightText: 2026 Fortunelabs
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @file test_app_main.c
 * @brief Runner of the control line reader tests (decision record
 *        2026-10-01-control-line-wire-format.md).
 */

#include "unity.h"

// ESP-IDF calls app_main from the startup task and declares it in no public header.
void app_main(void);

// cppcheck-suppress misra-c2012-8.7 ; ESP-IDF calls app_main from outside this unit
void app_main(void)
{
    unity_run_all_tests();
}
