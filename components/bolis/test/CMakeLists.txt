# Test component for the Bolis control line reader.
#
# The component compiles src/bol_json.c into the test binary instead of linking the
# whole bolis component. The reader needs only esp_err.h, so the tests build and run
# on the linux target, where the radio components of the firmware do not exist.
#
# WHOLE_ARCHIVE keeps the test case registrations, which no symbol references.
idf_component_register(
    SRCS "test_bol_json.c" "../src/bol_json.c"
    PRIV_INCLUDE_DIRS "../priv_include"
    PRIV_REQUIRES unity
    WHOLE_ARCHIVE
)

# Decision record 2026-10-01-misra-c-2012-coding-baseline.md fixes the language at C17.
target_compile_options(${COMPONENT_LIB} PRIVATE -std=gnu17)
