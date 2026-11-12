# Bolis

Bolis is a bench tool for ESP-NOW. It consists of firmware for two ESP32 nodes and a host CLI. The firmware sweeps the ESP-NOW link between the two nodes. The host CLI writes one report that shows which variable moves frame loss near the configuration of the user.

Status: pre-release. The firmware component owns the radio and builds. It answers the `hello` command of the control line, and it names the `role`, `cell`, `go`, and `stats` commands as unsupported. The host package holds the control line codec, the firmware flasher, and the sweep plan. `bolis run --print-plan` prints a plan. `bolis run` reports the missing control line transport. `bolis flash` reads the image manifest and stops, because a checkout carries no prebuilt image. The serial transport, the orchestrator, the run record writer, and the report do not exist.

## Layout

Each row names the purpose of a directory. The status line above states which parts exist today.

| Path | Contents |
|---|---|
| `components/bolis/` | The ESP-IDF component `fortunelabs-io/bolis`, with the `bol_` prefix |
| `components/bolis/examples/bench/` | The example project for source builds and for the prebuilt images |
| `host/` | The Python package `bolis`, with `pyproject.toml`, `src/bolis/`, and `tests/` |
| `schema/` | The JSON Schema of the run record format |
| `docs/` | The Doxygen configuration and the MISRA compliance files |
| `docs/adr/` | The decision records |
| `docs/record-lifecycle.md` | The status lifecycle of a decision record and of a deviation record |
