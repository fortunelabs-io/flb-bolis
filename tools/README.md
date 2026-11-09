# Tools

## `prep`

`prep` runs the stages of Bolis on a developer machine. It runs the stage that you name
and nothing else.

`mise.toml` at the root of the repository pins the tool versions and declares one task
per stage, so mise is the front door:

```
mise install               Install every tool that mise.toml pins. Run this once.
mise tasks                 List the stages.
mise run preflight         Report whether every later stage can run. Change nothing.
mise run build             Build the bench example and the reader test app.
mise run test              Run the C reader cases on the host, then the host package pytest cases.
mise run measure           Report the size of each image and the duration of each stage.
mise run all               Run the four stages in the order above.
mise run lint-shell        Check every shell script with ShellCheck.
```

Each task calls `tools/prep`, which also runs on its own with the same stage names:

```
./tools/prep preflight
./tools/prep build test
./tools/prep all --keep-going
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

Install the pinned tools, then source the `export.sh` of your ESP-IDF checkout, which
places `idf.py` and the target compiler on `PATH` and sets `IDF_PATH` and
`ESP_ROM_ELF_DIR`:

```
mise install
. "${HOME}/esp/esp-idf/export.sh"
```

ESP-IDF stays outside mise, because it is a git checkout with its own install and export
scripts. `mise.toml` states why it pins no Python version.

The `preflight` stage reports each requirement, including whether every tool that
`mise.toml` pins is installed. Run it first. It installs nothing.

### The test stage

The `test` stage runs two independent parts and combines them into one verdict. Either
part failing fails the stage. Both parts skipping skips the stage.

The C part compiles `components/bolis/test/host_runner.c`, the reader cases, the reader,
and the unity sources of ESP-IDF with the host compiler. Decision record
`docs/adr/2026-11-06-host-execution-of-the-reader-tests.md` states why this part uses the
host compiler rather than the ESP-IDF linux target. It needs the generated `sdkconfig.h`
of the test app, which the `build` stage produces. Run `build` before `test` on a clean
checkout.

The host package part runs `pytest` from `host/.venv`, the virtual environment that
`host/README.md` describes. A system `python3` may resolve to the Python environment of
an ESP-IDF checkout, which carries neither `pytest` nor `mypy`, so this part never calls a
bare `python3`. Create the environment once, before the first run:

```
python3 -m venv host/.venv
host/.venv/bin/pip install -e 'host[dev]'
```

Without that environment, this part reports `SKIP` with the command above.
