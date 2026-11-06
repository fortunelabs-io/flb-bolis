idf_component_register(
    SRCS "test_app_main.c"
    PRIV_REQUIRES unity
)

# Decision record 2026-10-01-misra-c-2012-coding-baseline.md fixes the language at C17.
target_compile_options(${COMPONENT_LIB} PRIVATE -std=gnu17)
