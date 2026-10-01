# Bench example

The example project for source builds and for the prebuilt images (`docs/adr/2026-10-01-radio-ownership-and-prebuilt-firmware.md`).

`main/main.c` calls only `bol_start`. The host assigns the sender role and the receiver role at run time, so both nodes run this one image.

`sdkconfig.defaults` disables the Bluetooth controller, because an active controller takes time slices from WiFi (thinkbook section 4).

`main/idf_component.yml` finds the component in this repository with `override_path`, so a local build needs no registry.

## Build

Build from the repository root:

```bash
idf.py -C components/bolis/examples/bench set-target esp32
idf.py -C components/bolis/examples/bench build
```

The ESP32 is the first supported chip. The build needs ESP-IDF v5.5 or later.

## Flash and monitor

```bash
idf.py -C components/bolis/examples/bench -p <port> flash monitor
```

The node logs that the radio is ready, then waits. The control protocol and the sweep arrive in a later change.
