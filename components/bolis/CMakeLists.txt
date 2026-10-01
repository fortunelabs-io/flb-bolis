idf_component_register(
    SRCS "src/bol_radio.c"
    INCLUDE_DIRS "include"
    PRIV_INCLUDE_DIRS "priv_include"
    PRIV_REQUIRES esp_wifi esp_netif esp_event nvs_flash
)

# Decision record 2026-10-01-misra-c-2012-coding-baseline.md fixes the language at C17,
# because MISRA C:2012 with Amendment 2 covers C18 at most.
target_compile_options(${COMPONENT_LIB} PRIVATE -std=gnu17)
