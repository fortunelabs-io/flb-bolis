idf_component_register(
    SRCS "src/bol_radio.c" "src/bol_console.c" "src/bol_json.c" "src/bol_frame.c" "src/bol_stats.c" "src/bol_rxstats.c" "src/bol_receiver.c"
    INCLUDE_DIRS "include"
    PRIV_INCLUDE_DIRS "priv_include"
    PRIV_REQUIRES esp_wifi esp_netif esp_event nvs_flash esp_driver_uart esp_app_format vfs
)

# Decision record 2026-10-01-misra-c-2012-coding-baseline.md fixes the language at C17,
# because MISRA C:2012 with Amendment 2 covers C18 at most.
target_compile_options(${COMPONENT_LIB} PRIVATE -std=gnu17)

# The hello reply states the component version (decision record
# 2026-10-01-control-line-wire-format.md). The manifest is the one source of that version,
# so the build reads it from there instead of holding a second copy in C.
set(bol_manifest "${CMAKE_CURRENT_LIST_DIR}/idf_component.yml")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${bol_manifest}")
file(READ "${bol_manifest}" bol_manifest_text)
string(REGEX MATCH "version:[ \t]*\"([^\"]+)\"" bol_version_match "${bol_manifest_text}")
if(NOT bol_version_match)
    message(FATAL_ERROR "${bol_manifest} states no version, so the hello reply has no bolis_version.")
endif()
target_compile_definitions(${COMPONENT_LIB} PRIVATE "BOL_VERSION=\"${CMAKE_MATCH_1}\"")
