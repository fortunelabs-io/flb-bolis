idf_component_register(SRCS "main.c")

# Decision record 2026-10-01-misra-c-2012-coding-baseline.md fixes the language at C17.
target_compile_options(${COMPONENT_LIB} PRIVATE -std=gnu17)
