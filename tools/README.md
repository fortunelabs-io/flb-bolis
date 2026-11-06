# Tools

## `prep`

`prep` runs the preparation and run stages of Bolis on a developer machine. It runs the
stage that you name and nothing else.

```
./tools/prep preflight     Report whether every later stage can run. Change nothing.
./tools/prep build         Build the bench example and the reader test app.
./tools/prep test          Compile the reader cases with the host compiler, then run them.
./tools/prep measure       Report the size of each image and the duration of each stage.
./tools/prep all           Run the four stages in the order above.
```

Run `./tools/prep --help` for the options.

### What each stage reports

Every stage prints the command it runs, writes a log under `prep-out/`, and ends with one
verdict line:

| Verdict | Meaning |
|---|---|
| `PASS` | The stage ran and met its condition. |
| `FAIL` | The stage ran and did not meet its condition. The exit code is 1. |
| `SKIP` | The stage could not run. The verdict line states the reason. |

A run ends with a summary table that names the verdict, the duration, and the detail of
every stage. A failing stage stops the run, and `--keep-going` collects every failure
instead.

### What the stages do not do

The stages run no layout, MISRA, CERT, or Doxygen check. Those checks belong to
`.github/workflows/checks.yml` for a pull request, and to the local compliance procedure
for a C change.

The `measure` stage reports the size of each image and the duration of each stage. It
measures no frame loss. The firmware carries no sweep yet, so a loss figure would carry no
measurement behind it. Every number that a stage prints carries its origin label (decision
record `docs/adr/2026-10-01-number-origin-labels.md`).

### Before the first run

Source the `export.sh` of your ESP-IDF checkout, which places `idf.py` and the target
compiler on `PATH` and sets `IDF_PATH` and `ESP_ROM_ELF_DIR`:

```
. "${HOME}/esp/esp-idf/export.sh"
```

The `preflight` stage reports each requirement, so run it first. It installs nothing.

### The test stage

The `test` stage compiles `components/bolis/test/host_runner.c`, the reader cases, the
reader, and the unity sources of ESP-IDF with the host compiler. Decision record
`docs/adr/2026-11-06-host-execution-of-the-reader-tests.md` states why the stage uses the
host compiler rather than the ESP-IDF linux target.

The stage needs the generated `sdkconfig.h` of the test app, which the `build` stage
produces. Run `build` before `test` on a clean checkout.
