# Tools

## `prep`

`prep` runs the stages of Bolis on a developer machine. It runs the stage that you name
and nothing else.

`mise.toml` at the root of the repository pins the tool versions and declares one task
per stage, so mise is the front door:

```
mise install               Install every tool that mise.toml pins. Run this once.
mise tasks                 List every task, one line each, in alphabetical order.
mise run list              Print every task, grouped, with the stages in order.
mise run preflight         Report whether every later stage can run. Change nothing.
mise run lint              Check the host package with ruff and mypy, then the scripts.
mise run build             Build the bench example and the reader test app.
mise run test              Run the C reader cases on the host, then the host package pytest cases.
mise run measure           Report the size of each image and the duration of each stage.
mise run all               Run the five stages in the order above.
```

Three tasks call a checker directly and run no stage. `all` calls none of them:

```
mise run lint-python       Check the host package with ruff and mypy. Change no file.
mise run lint-shell        Check every shell script with ShellCheck.
mise run fix-python        Apply the ruff fixes and the ruff layout. Write files.
```

Each stage task calls `tools/prep`, which also runs on its own with the same stage
names:

```
./tools/prep preflight
./tools/prep build test
./tools/prep all --keep-going
```

Run `./tools/prep --help` for the options.

### The task list

`mise run list`, which is `./tools/prep --list`, prints every task of the repository
in three groups: the stages in the order that `all` runs them, the checker tasks that
`all` never calls, and the checks that no task of this repository runs. It marks the
one task that writes files.

The view reports no result. It reads no log under `prep-out/` and no run record, so a
verdict of an earlier run cannot read as the state of the tree now. Run a stage to
learn a result.

The view ends with a comparison against `mise.toml`. It reads the task names that
mise reports and names any task that the view omits, and any task that the view names
and mise does not carry. A new task that no one adds to the tables of `tools/prep`
therefore appears as a difference instead of staying out of sight. An absent mise
leaves the view unchecked, and the view states that rather than claiming agreement.

`tools/prep` holds one table of the stages, as `name|description`. The usage text,
the view, and the stage list of the script all read it, and `mise.toml` carries the
same sentence as the description of each stage task.

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

The stages run no `astyle_py`, MISRA, CERT, or Doxygen check. Those checks belong to
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

### The lint stage

The `lint` stage runs two parts and combines them into one verdict. The host package
part runs three commands from the `host/` directory, because each one reads its
configuration from `host/pyproject.toml`:

```
ruff check .
ruff format --check .
.venv/bin/mypy --strict src/bolis
```

The shell part runs ShellCheck over every script that the stage names.

The stage reports `PASS` or `FAIL` and never `SKIP`. An absent `ruff`, `shellcheck`, or
`host/.venv/bin/mypy` fails the stage. `mise.toml` pins the first two, and the `dev`
extra of `host/pyproject.toml` carries mypy, so an absent checker means an unprepared
machine rather than clean code. A `SKIP` would end the run with exit code 0, which
reads as a check that found nothing rather than a check that never ran.

The stage runs before `build` in `all`, because it finishes in seconds while the build
takes minutes, so a lint failure stops the run before the ESP-IDF build starts.

The stage changes no file. The layout command runs with `--check`, which reports a
difference and writes nothing. Run `mise run fix-python` to apply the ruff fixes and
the ruff layout, then read the diff.

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
