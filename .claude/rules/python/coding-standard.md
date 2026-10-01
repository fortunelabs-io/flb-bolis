---
paths:
  - "**/*.py"
  - "**/pyproject.toml"
---

# Python coding standard

Python has no MISRA or CERT standard. The host package follows these sources instead:

| Concern | Source |
|---|---|
| Style | PEP 8, enforced by the Ruff formatter and linter |
| Docstrings | PEP 257, in the Google docstring style |
| Types | PEP 484 annotations, checked by `mypy --strict` |
| Secure coding | The OpenSSF Secure Coding Guide for Python (pyscg), which maps each rule to a CWE entry |
| Packaging | PEP 621 metadata in `pyproject.toml` |

## Version

- Support Python 3.10 and later. esptool 5 requires Python 3.10 or later.
- Use the syntax of Python 3.10. Write `X | None`, not `Optional[X]`.

## Tool configuration

The tracked `pyproject.toml` holds this configuration. Change it only through a PR.

```toml
[tool.ruff]
target-version = "py310"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "D", "UP", "B", "S", "ANN", "BLE", "PTH", "ERA", "PL", "RUF", "SIM", "RET", "C4", "PT"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.mypy]
python_version = "3.10"
strict = true
```

- Keep the default line length of the Ruff formatter.
- A `# noqa` comment names the rule code, such as `# noqa: S311`. A comment on the line above states the reason.

## Style

- Name modules, functions, and variables in `snake_case`, classes in `PascalCase`, and constants in `UPPER_SNAKE_CASE`.
- Put the unit at the end of the name of a quantity: `_us`, `_ms`, `_s`, `_bytes`, `_dbm`, or `_qdbm`. Example: `airtime_ms`.
- Use `pathlib.Path` for file paths.
- Do not leave code commented out.

## Docstrings

- Give every public module, class, function, and method a docstring in the Google style.
- Start the summary line with a verb in the third person, such as "Computes the Wilson score interval."
- In `Args:`, state the unit and the valid range of each argument.
- In `Raises:`, name each exception that the function raises on purpose.
- Write every docstring in the writing standard (`writing.md`).
- Doxygen does not process Python in Bolis. Doxygen shows a plain docstring as preformatted text. Its command form, a docstring that starts with `"""!`, puts Doxygen markup into the output of `help()`.

## Types

- Annotate every function parameter and return value.
- Use `Any` only at the boundary with an untyped library, and narrow it at once.
- Represent each record section with a `dataclass` or a `TypedDict`.

## Errors

- Raise a specific exception. Derive every Bolis exception from one base class, `BolisError`.
- Never write a bare `except:`. Catch `Exception` only at the CLI entry point, to print a message and exit with a non-zero status.
- Never use `assert` for a runtime check. Python removes `assert` under `-O`.
- Never swallow an exception silently.

## External input

- Treat every line from a node as untrusted.
- Read lines with a length limit and a timeout.
- Parse only lines that start with `@bol `. Parse the rest of the line as one JSON object.
- Validate each object against the control protocol before use: the command name, the field types, and the field ranges.
- Validate every value that the user types, such as the channel, the power set value, and the payload size, before the run starts.
- Never use `eval`, `exec`, `pickle`, or `yaml.load` without a safe loader on external data.

## Offline and private

- The host package sends nothing off the machine of the user (specification section 7). Do not import `socket`, `urllib`, `http`, or `requests` in the package.
- Hold MAC addresses only in memory. Never write a MAC address to a run record, a report, or a log.
- The firmware images ship inside the package. Check the SHA-256 of an image before the CLI flashes it.
- Flash through the esptool Python API (decision 7). Never start esptool as a subprocess. Never use `shell=True`.

## Numbers and records

- Shuffle the cells with `random.Random(seed)` and record the seed (decision 4). The seed makes a run reproducible. It is not a secret, so the Bandit rule S311 does not apply. Mark the line with `# noqa: S311`, and state that reason in the comment above it.
- Never compare floating-point values with `==`. Use `math.isclose` with a stated tolerance.
- Give every number in the run record one of the four labels of decision 5.
- Write the run record against the JSON Schema of the run record format. A record that fails the schema is an error.

## Tests

- Test with `pytest`.
- Test each formula of thinkbook section 3 against the values that the thinkbook states, such as an airtime of 2.54 ms at 250 bytes and 12.58 ms at 1470 bytes, and 1825 frames for a 5% loss at a half-width of 1 percentage point.
- Test the parser of control lines with malformed, oversized, and truncated lines.
