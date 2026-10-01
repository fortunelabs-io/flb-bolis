# MISRA C:2012 catalog for Bolis

This catalog covers MISRA C:2012 with Amendment 1 and Amendment 2: 17 directives and 158 rules. Category: M is Mandatory, R is Required, and A is Advisory. The summary column is a Fortune Labs paraphrase for orientation. It is not the guideline text. The licensed MISRA C:2012 text governs. Check each category against the licensed text before the first compliance summary.

Status values: "Apply" means the guideline applies to native code with no exception. A deviation ID names the deviation record in `docs/compliance/misra-deviations.md`. "Apply, note" means advisory exceptions carry an inline note.

## Directives

| ID | Cat. | Summary | Bolis status |
|---|---|---|---|
| Dir 1.1 | R | Document every implementation-defined behavior the program relies on. | Apply. `docs/compliance/implementation-defined.md` |
| Dir 2.1 | R | Compile every source file without errors. | Apply. CI builds on each supported ESP-IDF minor |
| Dir 3.1 | R | Trace all code to documented requirements. | Apply. File headers name the specification or thinkbook section, or the ADR |
| Dir 4.1 | R | Minimize run-time failures. | Apply. Static analysis plus explicit checks |
| Dir 4.2 | A | Document every use of assembly language. | Apply. Bolis code has no assembly |
| Dir 4.3 | R | Encapsulate and isolate assembly language. | Apply. Bolis code has no assembly |
| Dir 4.4 | A | Do not leave sections of code commented out. | Apply |
| Dir 4.5 | A | Keep identifiers in one name space typographically unambiguous. | Apply |
| Dir 4.6 | A | Use sized typedefs in place of the basic numeric types. | Apply, note. `int` only where an ESP-IDF signature requires it |
| Dir 4.7 | R | Test the error information that a function returns. | Apply. Every `esp_err_t` |
| Dir 4.8 | A | Hide the definition of a structure that a unit uses only through pointers. | Apply. Opaque types in public headers |
| Dir 4.9 | A | Prefer a function to a function-like macro where either works. | Apply. Use `static inline` |
| Dir 4.10 | R | Prevent the repeated inclusion of a header. | Apply. `#ifndef` guards |
| Dir 4.11 | R | Check each argument to a library function against the range that the function accepts. | Apply |
| Dir 4.12 | R | Do not use dynamic memory allocation. | Apply. Static FreeRTOS objects |
| Dir 4.13 | A | Call the functions that manage a resource in the right sequence. | Apply |
| Dir 4.14 | R | Check the validity of values received from external sources. | Apply. Radio packets and control lines |

## Rules 1 to 9

| ID | Cat. | Summary | Bolis status |
|---|---|---|---|
| 1.1 | R | Stay within standard C syntax, constraints, and the translation limits of the implementation. | Apply |
| 1.2 | A | Do not use language extensions. | Apply, note. Extensions appear only through ESP-IDF headers and macros |
| 1.3 | R | Do not rely on undefined or critical unspecified behavior. | Apply |
| 1.4 | R | Do not use the emergent C11 features that Amendment 2 lists, such as generic selection, atomics, and threads. | Apply |
| 2.1 | R | Do not leave unreachable code. | Apply |
| 2.2 | R | Do not leave dead code. | Apply |
| 2.3 | A | Do not leave unused type declarations. | Apply |
| 2.4 | A | Do not leave unused tag declarations. | Apply |
| 2.5 | A | Do not leave unused macro definitions. | Apply |
| 2.6 | A | Do not leave unused labels. | Apply |
| 2.7 | A | Do not leave unused function parameters. | Apply, note. Cast an unused callback parameter to `void` |
| 3.1 | R | Do not write the comment openers `/*` or `//` inside a comment. | Apply. No URLs in comments |
| 3.2 | R | Do not end a `//` comment with a line splice. | Apply |
| 4.1 | R | Terminate octal and hexadecimal escape sequences. | Apply |
| 4.2 | A | Do not use trigraphs. | Apply |
| 5.1 | R | Keep external identifiers distinct. | Apply |
| 5.2 | R | Keep identifiers in one scope and name space distinct. | Apply |
| 5.3 | R | Do not hide an identifier of an outer scope. | Apply |
| 5.4 | R | Keep macro identifiers distinct. | Apply |
| 5.5 | R | Keep identifiers distinct from macro names. | Apply |
| 5.6 | R | Use each typedef name for one type only. | Apply |
| 5.7 | R | Use each tag name for one type only. | Apply |
| 5.8 | R | Use each identifier with external linkage once. | Apply |
| 5.9 | A | Use each identifier with internal linkage once. | Apply |
| 6.1 | R | Declare bit-fields only with appropriate types. | Apply. No bit-fields in frame headers |
| 6.2 | R | Do not make a single-bit named bit-field signed. | Apply |
| 7.1 | R | Do not use octal constants. | Apply |
| 7.2 | R | Add a `U` suffix to unsigned integer constants. | Apply |
| 7.3 | R | Do not use a lowercase `l` in a literal suffix. | Apply |
| 7.4 | R | Assign a string literal only to a pointer to const char. | Apply |
| 8.1 | R | State every type explicitly. | Apply |
| 8.2 | R | Write function types in prototype form with named parameters. | Apply |
| 8.3 | R | Use the same names and qualifiers in every declaration of an object or function. | Apply |
| 8.4 | R | Make a compatible declaration visible where an external object or function is defined. | Apply |
| 8.5 | R | Declare an external object or function once, in one file. | Apply |
| 8.6 | R | Define an identifier with external linkage exactly once. | Apply |
| 8.7 | A | Do not give external linkage to an object or function that one unit uses. | Apply |
| 8.8 | R | Write `static` in every declaration with internal linkage. | Apply |
| 8.9 | A | Define an object at block scope if one function uses it. | Apply |
| 8.10 | R | Declare an inline function `static`. | Apply |
| 8.11 | A | State the size of an external array explicitly. | Apply |
| 8.12 | R | Keep implicitly valued enumeration constants unique. | Apply |
| 8.13 | A | Point to a const-qualified type whenever possible. | Apply |
| 8.14 | R | Do not use the `restrict` qualifier. | Apply |
| 9.1 | M | Do not read an automatic object before it holds a value. | Apply |
| 9.2 | R | Enclose aggregate and union initializers in braces. | Apply |
| 9.3 | R | Do not initialize an array partly. | Apply |
| 9.4 | R | Initialize each element of an object at most once. | Apply |
| 9.5 | R | State the array size when designated initializers initialize an array. | Apply |

## Rules 10 to 14

| ID | Cat. | Summary | Bolis status |
|---|---|---|---|
| 10.1 | R | Give each operand an appropriate essential type. | Apply |
| 10.2 | R | Use character values in addition and subtraction only in the permitted forms. | Apply |
| 10.3 | R | Do not assign a value to a narrower essential type or to a different essential type category. | Apply |
| 10.4 | R | Give both operands of an arithmetic conversion the same essential type category. | Apply |
| 10.5 | A | Do not cast a value to an inappropriate essential type. | Apply |
| 10.6 | R | Do not assign a composite expression to a wider essential type. | Apply |
| 10.7 | R | If one operand is a composite expression, do not give the other operand a wider essential type. | Apply |
| 10.8 | R | Do not cast a composite expression to a different category or a wider essential type. | Apply |
| 11.1 | R | Do not convert between a function pointer and any other type. | Apply |
| 11.2 | R | Do not convert between a pointer to an incomplete type and any other type. | Apply |
| 11.3 | R | Do not cast between pointers to different object types. | Apply. Decode with `memcpy` or byte access |
| 11.4 | A | Do not convert between an object pointer and an integer type. | Apply |
| 11.5 | A | Do not convert a pointer to void into a pointer to an object. | Apply, note. FreeRTOS and ESP-IDF callback arguments |
| 11.6 | R | Do not cast between a pointer to void and an arithmetic type. | Apply |
| 11.7 | R | Do not cast between an object pointer and a non-integer arithmetic type. | Apply |
| 11.8 | R | Do not cast away const or volatile. | Apply |
| 11.9 | R | Use `NULL` as the only integer null pointer constant. | Apply |
| 12.1 | A | Make operator precedence explicit. | Apply |
| 12.2 | R | Keep the right operand of a shift within the width of the left operand. | Apply |
| 12.3 | A | Do not use the comma operator. | Apply |
| 12.4 | A | Do not let constant expressions wrap around in unsigned arithmetic. | Apply |
| 12.5 | M | Do not apply `sizeof` to a function parameter declared as an array. | Apply |
| 13.1 | R | Keep initializer lists free of persistent side effects. | Apply |
| 13.2 | R | Give an expression the same value and side effects under every permitted order of evaluation. | Apply |
| 13.3 | A | Let an increment or decrement be the only side effect in a full expression. | Apply |
| 13.4 | A | Do not use the result of an assignment. | Apply |
| 13.5 | R | Keep the right operand of `&&` and `\|\|` free of persistent side effects. | Apply |
| 13.6 | M | Keep the operand of `sizeof` free of side effects. | Apply |
| 14.1 | R | Do not use a floating-point loop counter. | Apply |
| 14.2 | R | Write every `for` loop in the well-formed shape. | Apply |
| 14.3 | R | Do not use an invariant controlling expression. | Apply. The infinite loop of a task, `for (;;)`, is the exception |
| 14.4 | R | Give `if` and loop conditions an essentially Boolean type. | Apply |

## Rules 15 to 19

| ID | Cat. | Summary | Bolis status |
|---|---|---|---|
| 15.1 | A | Do not use `goto`. | Apply |
| 15.2 | R | Jump forward only, with `goto`, in the same function. | Apply. Bolis code has no `goto` |
| 15.3 | R | Place a `goto` label in the same block or an enclosing block. | Apply. Bolis code has no `goto` |
| 15.4 | A | End a loop with at most one `break` or `goto`. | Apply |
| 15.5 | A | Give each function one exit point at its end. | Apply |
| 15.6 | R | Use a compound statement for every loop body and selection body. | Apply |
| 15.7 | R | End every `if ... else if` chain with `else`. | Apply |
| 16.1 | R | Write every `switch` in the well-formed shape. | Apply |
| 16.2 | R | Use a switch label only in the body of its `switch`. | Apply |
| 16.3 | R | End every non-empty switch clause with an unconditional `break`. | Apply |
| 16.4 | R | Give every `switch` a `default` label. | Apply |
| 16.5 | R | Place `default` first or last. | Apply |
| 16.6 | R | Give every `switch` at least two clauses. | Apply |
| 16.7 | R | Do not switch on an essentially Boolean expression. | Apply |
| 17.1 | R | Do not use the features of `<stdarg.h>`. | Apply. Calls to adopted logging macros fall under D-002 |
| 17.2 | R | Do not use recursion. | Apply |
| 17.3 | M | Do not declare a function implicitly. | Apply |
| 17.4 | M | Return an expression on every exit path of a non-void function. | Apply |
| 17.5 | A | Pass an array argument with the element count that the parameter declares. | Apply |
| 17.6 | M | Do not write `static` inside the brackets of an array parameter. | Apply |
| 17.7 | R | Use the value that a non-void function returns. | Apply. Cast to `void` only with a stated reason |
| 17.8 | A | Do not modify a function parameter. | Apply |
| 18.1 | R | Keep pointer arithmetic inside the same array. | Apply |
| 18.2 | R | Subtract pointers only within the same array. | Apply |
| 18.3 | R | Compare pointers with relational operators only within the same object. | Apply |
| 18.4 | A | Do not apply `+`, `-`, `+=`, or `-=` to a pointer. | Apply. Use array indexing |
| 18.5 | A | Use at most two levels of pointer nesting. | Apply |
| 18.6 | R | Do not let the address of an automatic object outlive the object. | Apply |
| 18.7 | R | Do not declare flexible array members. | Apply |
| 18.8 | R | Do not use variable-length array types. | Apply |
| 19.1 | M | Do not assign or copy an object to an overlapping object. | Apply |
| 19.2 | A | Do not use unions. | Apply |

## Rules 20 to 22

| ID | Cat. | Summary | Bolis status |
|---|---|---|---|
| 20.1 | A | Place `#include` only after other directives or comments. | Apply |
| 20.2 | R | Keep quote marks, backslashes, and comment openers out of header file names. | Apply |
| 20.3 | R | Follow `#include` with `<file>` or `"file"`. | Apply |
| 20.4 | R | Do not define a macro with the name of a keyword. | Apply |
| 20.5 | A | Do not use `#undef`. | Apply |
| 20.6 | R | Do not pass tokens that look like directives as macro arguments. | Apply |
| 20.7 | R | Parenthesize each macro parameter in an expansion that forms an expression. | Apply |
| 20.8 | R | Make every `#if` and `#elif` condition evaluate to 0 or 1. | Apply |
| 20.9 | R | Define every identifier in an `#if` or `#elif` condition before the evaluation. | Apply |
| 20.10 | A | Do not use the `#` and `##` operators. | Apply |
| 20.11 | R | Do not follow a `#` operand directly with `##`. | Apply |
| 20.12 | R | If a parameter is an operand of `#` or `##` and is replaced further, use it only as such an operand. | Apply |
| 20.13 | R | Make every line that starts with `#` a valid directive. | Apply |
| 20.14 | R | Keep `#else`, `#elif`, and `#endif` in the file of their `#if`. | Apply |
| 21.1 | R | Do not `#define` or `#undef` a reserved identifier or a standard macro name. | Apply |
| 21.2 | R | Do not declare a reserved identifier or a standard macro name. | Apply |
| 21.3 | R | Do not use the allocation functions of `<stdlib.h>`. | Apply |
| 21.4 | R | Do not use `<setjmp.h>`. | Apply |
| 21.5 | R | Do not use `<signal.h>`. | Apply |
| 21.6 | R | Do not use the standard input and output functions. | D-001 in the console module. Apply elsewhere |
| 21.7 | R | Do not use `atof`, `atoi`, `atol`, or `atoll`. | Apply |
| 21.8 | R | Do not use the termination functions of `<stdlib.h>`. | Apply. Do not use `ESP_ERROR_CHECK` |
| 21.9 | R | Do not use `bsearch` or `qsort`. | Apply |
| 21.10 | R | Do not use the time and date functions of `<time.h>`. | Apply. Use `esp_timer_get_time` |
| 21.11 | R | Do not use `<tgmath.h>`. | Apply |
| 21.12 | A | Do not use the exception features of `<fenv.h>`. | Apply |
| 21.13 | M | Pass a `<ctype.h>` function only a value that fits in unsigned char, or EOF. | Apply |
| 21.14 | R | Do not compare null-terminated strings with `memcmp`. | Apply |
| 21.15 | R | Pass `memcpy`, `memmove`, and `memcmp` pointers to compatible types. | Apply |
| 21.16 | R | Pass `memcmp` only pointers to pointer, Boolean, enumeration, or essentially signed or unsigned types. | Apply |
| 21.17 | M | Keep the string functions of `<string.h>` within the bounds of their objects. | Apply |
| 21.18 | M | Pass a valid `size_t` argument to a `<string.h>` function. | Apply |
| 21.19 | M | Treat a pointer from `localeconv`, `getenv`, `setlocale`, or `strerror` as a pointer to const. | Apply |
| 21.20 | M | Do not use a pointer that such a library function returned after a later call to the same function. | Apply |
| 21.21 | R | Do not use `system`. | Apply |
| 22.1 | R | Release every resource obtained dynamically. | Apply |
| 22.2 | M | Free only memory that a standard library allocation function returned. | Apply |
| 22.3 | R | Do not open one file for reading and writing at the same time on different streams. | Apply in the console module |
| 22.4 | M | Do not write to a stream opened as read-only. | Apply in the console module |
| 22.5 | M | Do not dereference a pointer to `FILE`. | Apply in the console module |
| 22.6 | M | Do not use a `FILE` pointer after its stream closes. | Apply in the console module |
| 22.7 | R | Compare `EOF` only with the unmodified return value of a function that can return it. | Apply in the console module |
| 22.8 | R | Set `errno` to zero before a call to a function that sets it. | Apply |
| 22.9 | R | Test `errno` after a call to a function that sets it. | Apply |
| 22.10 | R | Test `errno` only when the last function called sets it. | Apply |
