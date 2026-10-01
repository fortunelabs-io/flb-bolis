# SEI CERT C catalog for Bolis

This catalog lists the 99 rules of the SEI CERT C Coding Standard, 2016 Edition, with the risk level of each rule and its applicability to Bolis firmware. Level L1 covers priorities P12 to P27, L2 covers P6 to P9, and L3 covers P1 to P4.

Derived from: SEI CERT C Coding Standard: Rules for Developing Safe, Reliable, and Secure Systems, 2016 Edition. Copyright 2016 Carnegie Mellon University. Carnegie Mellon and CERT are registered marks of Carnegie Mellon University. This derivative work is for internal use.

NO WARRANTY. THIS CARNEGIE MELLON UNIVERSITY AND SOFTWARE ENGINEERING INSTITUTE MATERIAL IS FURNISHED ON AN "AS-IS" BASIS. CARNEGIE MELLON UNIVERSITY MAKES NO WARRANTIES OF ANY KIND, EITHER EXPRESSED OR IMPLIED, AS TO ANY MATTER INCLUDING, BUT NOT LIMITED TO, WARRANTY OF FITNESS FOR PURPOSE OR MERCHANTABILITY, EXCLUSIVITY, OR RESULTS OBTAINED FROM USE OF THE MATERIAL. CARNEGIE MELLON UNIVERSITY DOES NOT MAKE ANY WARRANTY OF ANY KIND WITH RESPECT TO FREEDOM FROM PATENT, TRADEMARK, OR COPYRIGHT INFRINGEMENT.

## PRE: Preprocessor

| Rule | Level | Title | Bolis applicability |
|---|---|---|---|
| PRE30-C | L3 | Do not create a universal character name through concatenation | Apply |
| PRE31-C | L3 | Avoid side effects in arguments to unsafe macros | Apply |
| PRE32-C | L3 | Do not use preprocessor directives in invocations of function-like macros | Apply |

## DCL: Declarations and initialization

| Rule | Level | Title | Bolis applicability |
|---|---|---|---|
| DCL30-C | L2 | Declare objects with appropriate storage durations | Apply |
| DCL31-C | L3 | Declare identifiers before using them | Apply |
| DCL36-C | L2 | Do not declare an identifier with conflicting linkage classifications | Apply |
| DCL37-C | L3 | Do not declare or define a reserved identifier | Apply |
| DCL38-C | L3 | Use the correct syntax when declaring a flexible array member | Not used. MISRA 18.7 bans flexible array members |
| DCL39-C | L3 | Avoid information leakage when passing a structure across a trust boundary | Apply |
| DCL40-C | L3 | Do not create incompatible declarations of the same function or object | Apply |
| DCL41-C | L3 | Do not declare variables inside a switch statement before the first case label | Apply |

## EXP: Expressions

| Rule | Level | Title | Bolis applicability |
|---|---|---|---|
| EXP30-C | L2 | Do not depend on the order of evaluation for side effects | Apply |
| EXP32-C | L2 | Do not access a volatile object through a nonvolatile reference | Apply |
| EXP33-C | L1 | Do not read uninitialized memory | Apply |
| EXP34-C | L1 | Do not dereference null pointers | Apply. Check every pointer argument and callback pointer |
| EXP35-C | L3 | Do not modify objects with temporary lifetime | Apply |
| EXP36-C | L3 | Do not cast pointers into more strictly aligned pointer types | Apply |
| EXP37-C | L3 | Call functions with the correct number and type of arguments | Apply |
| EXP39-C | L3 | Do not access a variable through a pointer of an incompatible type | Apply |
| EXP40-C | L3 | Do not modify constant objects | Apply |
| EXP42-C | L2 | Do not compare padding data | Apply |
| EXP43-C | L3 | Avoid undefined behavior when using restrict-qualified pointers | Not used. MISRA 8.14 bans restrict |
| EXP44-C | L3 | Do not rely on side effects in operands to sizeof, _Alignof, or _Generic | Apply |
| EXP45-C | L2 | Do not perform assignments in selection statements | Apply |
| EXP46-C | L2 | Do not use a bitwise operator with a Boolean-like operand | Apply |

## INT: Integers

| Rule | Level | Title | Bolis applicability |
|---|---|---|---|
| INT30-C | L2 | Ensure that unsigned integer operations do not wrap | Apply. Check every counter for wrap, such as message IDs |
| INT31-C | L2 | Ensure that integer conversions do not result in lost or misinterpreted data | Apply |
| INT32-C | L2 | Ensure that operations on signed integers do not result in overflow | Apply |
| INT33-C | L2 | Ensure that division and remainder operations do not result in divide-by-zero errors | Apply |
| INT34-C | L3 | Do not shift an expression by a negative number of bits or by greater than or equal to the number of bits that exist in the operand | Apply |
| INT35-C | L3 | Use correct integer precisions | Apply |
| INT36-C | L3 | Converting a pointer to integer or integer to pointer | Apply |

## FLP: Floating point

| Rule | Level | Title | Bolis applicability |
|---|---|---|---|
| FLP30-C | L2 | Do not use floating-point variables as loop counters | Apply where floating point appears |
| FLP32-C | L2 | Prevent or detect domain and range errors in math functions | Apply where floating point appears |
| FLP34-C | L3 | Ensure that floating-point conversions are within range of the new type | Apply where floating point appears |
| FLP36-C | L3 | Preserve precision when converting integral values to floating-point type | Apply where floating point appears |
| FLP37-C | L3 | Do not use object representations to compare floating-point values | Apply where floating point appears |

## ARR: Arrays

| Rule | Level | Title | Bolis applicability |
|---|---|---|---|
| ARR30-C | L2 | Do not form or use out-of-bounds pointers or array subscripts | Apply |
| ARR32-C | L2 | Ensure size arguments for variable length arrays are in a valid range | Not used. MISRA 18.8 bans variable-length arrays |
| ARR36-C | L2 | Do not subtract or compare two pointers that do not refer to the same array | Apply |
| ARR37-C | L2 | Do not add or subtract an integer to a pointer to a non-array object | Apply |
| ARR38-C | L1 | Guarantee that library functions do not form invalid pointers | Apply |
| ARR39-C | L2 | Do not add or subtract a scaled integer to a pointer | Apply |

## STR: Characters and strings

| Rule | Level | Title | Bolis applicability |
|---|---|---|---|
| STR30-C | L2 | Do not attempt to modify string literals | Apply |
| STR31-C | L1 | Guarantee that storage for strings has sufficient space for character data and the null terminator | Apply |
| STR32-C | L1 | Do not pass a non-null-terminated character sequence to a library function that expects a string | Apply |
| STR34-C | L2 | Cast characters to unsigned char before converting to larger integer sizes | Apply |
| STR37-C | L3 | Arguments to character-handling functions must be representable as an unsigned char | Apply |
| STR38-C | L1 | Do not confuse narrow and wide character strings and functions | Apply. Bolis code uses no wide strings |

## MEM: Memory management

| Rule | Level | Title | Bolis applicability |
|---|---|---|---|
| MEM30-C | L1 | Do not access freed memory | Apply. Bolis code allocates no heap memory (MISRA Dir 4.12) |
| MEM31-C | L2 | Free dynamically allocated memory when no longer needed | Apply. Bolis code allocates no heap memory (MISRA Dir 4.12) |
| MEM33-C | L3 | Allocate and copy structures containing a flexible array member dynamically | Not used. MISRA 18.7 bans flexible array members |
| MEM34-C | L1 | Only free memory allocated dynamically | Apply. Bolis code allocates no heap memory (MISRA Dir 4.12) |
| MEM35-C | L2 | Allocate sufficient memory for an object | Apply. Bolis code allocates no heap memory (MISRA Dir 4.12) |
| MEM36-C | L3 | Do not modify the alignment of objects by calling realloc() | Apply. Bolis code allocates no heap memory (MISRA Dir 4.12) |

## FIO: Input and output

| Rule | Level | Title | Bolis applicability |
|---|---|---|---|
| FIO30-C | L1 | Exclude user input from format strings | Apply to every format string, including ESP_LOG calls |
| FIO32-C | L3 | Do not perform operations on devices that are only appropriate for files | Apply in the console module (MISRA deviation D-001) |
| FIO34-C | L1 | Distinguish between characters read from a file and EOF or WEOF | Apply in the console module (MISRA deviation D-001) |
| FIO37-C | L1 | Do not assume that fgets() or fgetws() returns a nonempty string when successful | Apply in the console module (MISRA deviation D-001) |
| FIO38-C | L3 | Do not copy a FILE object | Apply in the console module (MISRA deviation D-001) |
| FIO39-C | L2 | Do not alternately input and output from a stream without an intervening flush or positioning call | Apply in the console module (MISRA deviation D-001) |
| FIO40-C | L3 | Reset strings on fgets() or fgetws() failure | Apply in the console module (MISRA deviation D-001) |
| FIO41-C | L3 | Do not call getc(), putc(), getwc(), or putwc() with a stream argument that has side effects | Apply in the console module (MISRA deviation D-001) |
| FIO42-C | L3 | Close files when they are no longer needed | Apply in the console module (MISRA deviation D-001) |
| FIO44-C | L3 | Only use values for fsetpos() that are returned from fgetpos() | Apply in the console module (MISRA deviation D-001) |
| FIO45-C | L2 | Avoid TOCTOU race conditions while accessing files | Apply in the console module (MISRA deviation D-001) |
| FIO46-C | L3 | Do not access a closed file | Apply in the console module (MISRA deviation D-001) |
| FIO47-C | L2 | Use valid format strings | Apply to every format string, including ESP_LOG calls |

## ENV: Environment

| Rule | Level | Title | Bolis applicability |
|---|---|---|---|
| ENV30-C | L3 | Do not modify the object referenced by the return value of certain functions | Apply. Bolis code calls no environment function |
| ENV31-C | L3 | Do not rely on an environment pointer following an operation that may invalidate it | Apply. Bolis code calls no environment function |
| ENV32-C | L1 | All exit handlers must return normally | Apply. Bolis code calls no environment function |
| ENV33-C | L1 | Do not call `system()` | Apply. Never call `system()` (MISRA 21.21) |
| ENV34-C | L3 | Do not store pointers returned by certain functions | Apply. Bolis code calls no environment function |

## SIG: Signals

| Rule | Level | Title | Bolis applicability |
|---|---|---|---|
| SIG30-C | L1 | Call only asynchronous-safe functions within signal handlers | Not applicable. Bolis code does not use `<signal.h>` |
| SIG31-C | L2 | Do not access shared objects in signal handlers | Not applicable. Bolis code does not use `<signal.h>` (MISRA 21.5) |
| SIG34-C | L3 | Do not call `signal()` from within interruptible signal handlers | Not applicable. Bolis code does not use `<signal.h>` (MISRA 21.5) |
| SIG35-C | L3 | Do not return from a computational exception signal handler | Not applicable. Bolis code does not use `<signal.h>` (MISRA 21.5) |

## ERR: Error handling

| Rule | Level | Title | Bolis applicability |
|---|---|---|---|
| ERR30-C | L2 | Set errno to zero before calling a library function known to set errno, and check errno only after the function returns a value indicating failure | Apply where a function sets errno (MISRA 22.8 to 22.10) |
| ERR32-C | L3 | Do not rely on indeterminate values of errno | Apply where a function sets errno |
| ERR33-C | L1 | Detect and handle standard library errors | Apply. Extend to every esp_err_t return value |

## CON: Concurrency

| Rule | Level | Title | Bolis applicability |
|---|---|---|---|
| CON30-C | L3 | Clean up thread-specific storage | Apply by analogy to FreeRTOS tasks, queues, and critical sections. Bolis code does not use C11 threads (MISRA 1.4) |
| CON31-C | L3 | Do not destroy a mutex while it is locked | Apply by analogy to FreeRTOS tasks, queues, and critical sections. Bolis code does not use C11 threads (MISRA 1.4) |
| CON32-C | L2 | Prevent data races when accessing bit-fields from multiple threads | Apply. No bit-fields shared between tasks |
| CON33-C | L3 | Avoid race conditions when using library functions | Apply by analogy to FreeRTOS tasks, queues, and critical sections. Bolis code does not use C11 threads (MISRA 1.4) |
| CON34-C | L3 | Declare objects shared between threads with appropriate storage durations | Apply by analogy to FreeRTOS tasks, queues, and critical sections. Bolis code does not use C11 threads (MISRA 1.4) |
| CON35-C | L3 | Avoid deadlock by locking in a predefined order | Apply by analogy to FreeRTOS tasks, queues, and critical sections. Bolis code does not use C11 threads (MISRA 1.4) |
| CON36-C | L3 | Wrap functions that can spuriously wake up in a loop | Apply by analogy to FreeRTOS tasks, queues, and critical sections. Bolis code does not use C11 threads (MISRA 1.4) |
| CON37-C | L2 | Do not call `signal()` in a multithreaded program | Not applicable. Bolis code does not use `signal()` |
| CON38-C | L3 | Preserve thread safety and liveness when using condition variables | Apply by analogy to FreeRTOS tasks, queues, and critical sections. Bolis code does not use C11 threads (MISRA 1.4) |
| CON39-C | L2 | Do not join or detach a thread that was previously joined or detached | Apply by analogy to FreeRTOS tasks, queues, and critical sections. Bolis code does not use C11 threads (MISRA 1.4) |
| CON40-C | L2 | Do not refer to an atomic variable twice in an expression | Apply by analogy to FreeRTOS tasks, queues, and critical sections. Bolis code does not use C11 threads (MISRA 1.4) |
| CON41-C | L3 | Wrap functions that can fail spuriously in a loop | Apply by analogy to FreeRTOS tasks, queues, and critical sections. Bolis code does not use C11 threads (MISRA 1.4) |

## MSC: Miscellaneous

| Rule | Level | Title | Bolis applicability |
|---|---|---|---|
| MSC30-C | L2 | Do not use the rand() function for generating pseudorandom numbers | Apply. Firmware uses no pseudorandom generator |
| MSC32-C | L1 | Properly seed pseudorandom number generators | Apply. Firmware uses no pseudorandom generator |
| MSC33-C | L1 | Do not pass invalid data to the asctime() function | Apply. Bolis code does not use `<time.h>` (MISRA 21.10) |
| MSC37-C | L2 | Ensure that control never reaches the end of a non-void function | Apply |
| MSC38-C | L3 | Do not treat a predefined identifier as an object if it might only be implemented as a macro | Apply |
| MSC39-C | L3 | Do not call va_arg() on a va_list that has an indeterminate value | Apply |
| MSC40-C | L3 | Do not violate constraints | Apply |
