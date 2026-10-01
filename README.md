# Bolis

Bolis is a bench tool for ESP-NOW. It consists of firmware for two ESP32 nodes and a host CLI. The firmware sweeps the ESP-NOW link between the two nodes. The host CLI writes one report that shows which variable moves frame loss near the configuration of the user.

Status: pre-release. No firmware or host code exists yet.

## Layout

| Path | Contents |
|---|---|
| `components/bolis/` | The ESP-IDF component `fortunelabs-io/bolis`, with the `bol_` prefix |
| `components/bolis/examples/bench/` | The example project for source builds and for the prebuilt images |
| `host/` | The Python package `bolis`: CLI, flasher, orchestrator, run record writer, and report builder |
| `schema/` | The JSON Schema of the run record format |
| `docs/` | The Doxygen configuration and the MISRA compliance files |
| `docs/adr/` | The decision records |
