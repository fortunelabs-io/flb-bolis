# Radio ownership and prebuilt firmware as the default path

Date: 2026-10-01
Status: Accepted

## Context

The Bolis v0 specification (v0.3) described Bolis as a component that a developer adds to an ESP-IDF project and starts with one function call. A clean measurement needs control of the channel, power save, rate, transmit power, and country code. If the application of the user also uses WiFi, a second call to `esp_wifi_init` conflicts, a connection to an access point fixes the channel, and application traffic shares airtime with the test frames. ESP-IDF reports an uninitialized WiFi driver through `esp_wifi_get_mode`, which returns `ESP_ERR_WIFI_NOT_INIT`. The founder asked for the option with the lowest adoption friction if that tradeoff won. A comparison of the paths to a first report found that a path through prebuilt firmware needs no ESP-IDF installation, no build, and no code change. Espressif offers ESP Launchpad so that users can try prebuilt firmware without ESP-IDF, and WLED, Tasmota, ESPHome, and ESPEasy install from the browser through ESP Web Tools. The esptool package offers a Python API that detects the chip and writes images to flash. Earlier decisions already fix the rate, power save, country code, and transmit power that Bolis uses, so most of what the sdkconfig of a user sets does not reach the measurement. If nothing was decided, the contract of the start function and the first steps of a user would stay undefined.

## Alternatives considered

- The component takes the radio, refuses to start when WiFi is already initialized, and runs in a test build of the user.
- The component adapts to the WiFi state of the application of the user.
- Bolis runs as standalone firmware, which the host CLI flashes from prebuilt images.
- The component takes the radio, and an example project builds it with the sdkconfig of the user.

## Decision

Bolis firmware owns the radio during a run. The default path is a standalone firmware image per chip. CI builds each image from the tagged Bolis source on ESP-IDF v5.5.x. The host CLI flashes the image through the esptool Python API. The images ship inside the host package, so flashing needs no network access. Both nodes run the same image. The host assigns the sender role and the receiver role at run time. The component stays available for source builds. In a source build, the component returns `ESP_ERR_INVALID_STATE` if WiFi is already initialized. The example project `examples/bench` is the source-build path. The run record states which path produced the firmware. The run record states whether the Bluetooth controller was enabled, as a `[configured]` value.

## Consequences

- The first report needs three steps: install the host package, flash two boards, and run one command.
- The default path needs no ESP-IDF installation, no build, and no code change.
- Users outside ESP-IDF, such as Arduino and PlatformIO users, can run Bolis on the default path.
- Integration into Arduino projects stays outside v0.
- Records from the default path share one firmware image per chip, which strengthens the corpus metric.
- A run on the default path does not measure the ESP-IDF version or the sdkconfig of the user.
- A user who needs those builds from source.
- The host package grows by one image per supported chip.
- CI publishes the hash of each image with each release.
- Each supported chip needs its own image, and the ESP32 comes first.
- The role argument of the start function in thinkbook section 7 moves to the control protocol.
- Specification sections 3, 5, and 8.2 change in v0.4.
- In v0.4, the product is firmware plus a host CLI, and the user flow starts with the installation of the host package.
- In v0.4, the ESP Component Registry serves source builds.
- A browser flasher such as ESP Launchpad stays a candidate for a later version.
