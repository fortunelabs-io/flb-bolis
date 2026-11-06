cmake_minimum_required(VERSION 3.16)

# The test component carries the test cases and the reader under test.
set(EXTRA_COMPONENT_DIRS "../../test")

# The reader needs no storage, no network, and no cryptography. Naming the root
# components keeps those out of the build, so the test app stays small and needs
# no host library beyond a C toolchain.
set(COMPONENTS main test)

# The reader needs no radio, so this app builds and runs on the linux target:
#   idf.py -C components/bolis/test_apps/json --preview set-target linux
#   idf.py -C components/bolis/test_apps/json build
#   ./components/bolis/test_apps/json/build/bolis_json_test.elf
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(bolis_json_test)
