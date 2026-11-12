# Bolis host package

The Python package `bolis` on PyPI. Thinkbook section 6 gives it the CLI, the flasher, the orchestrator, the run record writer, and the report builder. It holds the CLI, the flasher, the control line codec, and the sweep plan today. It supports Python 3.10 and later.

The package sends nothing off the machine of the user (specification section 7).

## Development setup

Run every command in this section from the `host/` directory.

A system Python may resolve to the Python environment of an ESP-IDF checkout, which carries neither `pytest` nor `mypy`. Create a virtual environment for the host package instead, and install the package into it in editable mode with the `dev` extra:

```
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

`.gitignore` excludes `.venv/`. Activate the environment, then run the checks that the root `CLAUDE.md` names:

```
. .venv/bin/activate
ruff check .
ruff format --check .
mypy --strict src/bolis
pytest
```

`tools/prep test` runs `pytest` from this environment as part of the local test stage. Create the environment before that stage, or it reports `SKIP` with the command above.
