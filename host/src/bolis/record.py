"""The run record writer.

Builds the numbers of one run record, checks the record against the JSON
Schema of the format, and writes one file per run
(record docs/adr/2026-11-12-run-record-format.md).

Every number that states a quantity of the run is an object with a value and
an origin label (record docs/adr/2026-10-01-number-origin-labels.md). The
keys of the format itself carry no label.

A cell states the loss quantities of its pass, with the Wilson score interval
at 95% beside each ratio
(record docs/adr/2026-11-13-loss-quantities-in-a-cell.md).

This module reaches no network. It reads the directory that it writes into,
to keep a run ID unique among the records that the host can see
(record docs/adr/2026-11-12-frame-header-encoding.md).
"""

import json
import math
import random
import re
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from bolis import BolisError

# The version of the run record format that this writer produces.
RECORD_VERSION: Final = 1

# The four origin labels of decision 2026-10-01-number-origin-labels.md.
MEASURED: Final = "measured"
CONFIGURED: Final = "configured"
DERIVED: Final = "derived"
DECLARED: Final = "declared"

# The standard normal value of a two-sided 95% interval, which thinkbook
# section 3.7 states as the level of the Wilson score interval.
WILSON_Z: Final = 1.96

# The widest run ID that the four bytes of the frame header carry.
RUN_ID_MAX: Final = 0xFFFFFFFF

# The bits that one draw of a run ID takes.
RUN_ID_BITS: Final = 32

# A draw that collides with a stored record repeats. A corpus meets a repeat
# of a 32-bit value long before it holds every value, so a run of draws this
# long states a directory that the host cannot read rather than bad luck.
RUN_ID_DRAWS: Final = 1000

# The name of one run record, which states its run ID in decimal digits
# (thinkbook section 9).
RECORD_NAME_PATTERN: Final = re.compile(r"^bolis-([0-9]+)\.json$")

# The schema sits at the repository root, which an installed package does not
# carry. The loader reads a copy inside the package first, so a later change
# that ships one needs no change here.
_SCHEMA_NAME: Final = "run-record.schema.json"
_PACKAGE_SCHEMA: Final = Path(__file__).parent / "schema" / _SCHEMA_NAME
_REPOSITORY_SCHEMA: Final = Path(__file__).parents[3] / "schema" / _SCHEMA_NAME


class BolisRecordError(BolisError):
    """Raised when a run record cannot be built, checked, or written."""


def measured(value: float) -> dict[str, Any]:
    """Labels a value that a node counted or read during the run.

    Args:
        value: The number that the node reported.

    Returns:
        The value beside its origin label.
    """
    return {"value": value, "label": MEASURED}


def configured(value: float) -> dict[str, Any]:
    """Labels a value that Bolis set.

    Args:
        value: The number that Bolis set.

    Returns:
        The value beside its origin label.
    """
    return {"value": value, "label": CONFIGURED}


def derived(value: float) -> dict[str, Any]:
    """Labels a value computed only from measured values.

    Args:
        value: The computed number.

    Returns:
        The value beside its origin label.
    """
    return {"value": value, "label": DERIVED}


def declared(value: str) -> dict[str, Any]:
    """Labels text that the user typed and that Bolis did not check.

    Args:
        value: The text that the user typed.

    Returns:
        The text beside its origin label.
    """
    return {"value": value, "label": DECLARED}


def measured_list(values: list[int]) -> dict[str, Any]:
    """Labels a list whose entries share one origin, such as a histogram.

    Args:
        values: The entries, in the order that the format states.

    Returns:
        The list beside its origin label.
    """
    return {"value": values, "label": MEASURED}


def configured_list(values: list[int]) -> dict[str, Any]:
    """Labels a list of values that Bolis set, such as the payload list.

    Args:
        values: The entries, in the order that the format states.

    Returns:
        The list beside its origin label.
    """
    return {"value": values, "label": CONFIGURED}


def wilson_interval(lost: int, total: int) -> tuple[float, float]:
    """Returns the Wilson score interval of a loss share, at 95%.

    Thinkbook section 3.7 states the level and the estimator. The interval
    assumes that losses are independent, and a bursty link breaks that
    assumption, which the run-length histogram of the same cell flags.

    Args:
        lost: The count that failed, 0 to total.
        total: The count that the share divides, 1 or more.

    Returns:
        The lower bound and the upper bound, in that order.

    Raises:
        BolisRecordError: The total is not positive, or the lost count sits
            outside it.
    """
    if total <= 0:
        raise BolisRecordError(
            f"the interval divides by {total}, and a share needs a positive total."
        )
    if not 0 <= lost <= total:
        raise BolisRecordError(
            f"the lost count is {lost}, which sits outside 0 to {total}."
        )

    share = lost / total
    spread = 1.0 + (WILSON_Z**2) / total
    center = (share + (WILSON_Z**2) / (2 * total)) / spread
    half = (WILSON_Z / spread) * math.sqrt(
        share * (1.0 - share) / total + (WILSON_Z**2) / (4 * total**2)
    )
    return center - half, center + half


def loss_quantity(lost: int, total: int) -> dict[str, Any]:
    """Builds one loss quantity, with its ratio and its interval.

    Every value divides counters that the same cell entry states, so each one
    carries the derived label.

    Args:
        lost: The count that failed, 0 to total.
        total: The count that the share divides, 1 or more.

    Returns:
        The ratio and the two bounds of its Wilson interval.

    Raises:
        BolisRecordError: The total is not positive, or the lost count sits
            outside it.
    """
    low, high = wilson_interval(lost, total)
    return {
        "ratio": derived(lost / total),
        "wilson_interval_low": derived(low),
        "wilson_interval_high": derived(high),
    }


@lru_cache(maxsize=1)
def load_schema() -> Mapping[str, Any]:
    """Reads the JSON Schema of the run record format.

    Returns:
        The parsed schema.

    Raises:
        BolisRecordError: Neither location holds the schema.
    """
    for path in (_PACKAGE_SCHEMA, _REPOSITORY_SCHEMA):
        if path.is_file():
            parsed: Mapping[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return parsed
    raise BolisRecordError(
        f"the schema of the run record format is absent. The host read "
        f"{_PACKAGE_SCHEMA} and {_REPOSITORY_SCHEMA}."
    )


def validate_record(document: Mapping[str, Any]) -> None:
    """Checks one record against the schema of the format.

    The Python coding standard calls a record that fails the schema an error,
    so the host checks a record before it writes the file.

    Args:
        document: The record to check.

    Raises:
        BolisRecordError: The record does not meet the schema.
    """
    # jsonschema loads here rather than at the top of the module, so a caller
    # that only labels a number pays nothing for the validator.
    import jsonschema  # type: ignore[import-untyped]  # noqa: PLC0415

    schema = load_schema()
    validator = jsonschema.validators.validator_for(schema)(schema)
    errors = sorted(validator.iter_errors(document), key=lambda error: error.path)
    if errors:
        first = errors[0]
        place = "/".join(str(part) for part in first.absolute_path) or "the record"
        raise BolisRecordError(
            f"the record does not meet the schema at {place}: {first.message}"
        )


def existing_run_ids(directory: Path) -> set[int]:
    """Returns the run ID of every record that the directory holds.

    The reader takes each ID from the name of a file rather than from its
    contents, so one unreadable record does not stop a run.

    Args:
        directory: The directory that the host writes into.

    Returns:
        The run IDs that the directory already names.

    Raises:
        BolisRecordError: The host cannot read the directory.
    """
    try:
        names = [path.name for path in directory.iterdir()]
    except OSError as error:
        raise BolisRecordError(
            f"the host cannot read the directory {directory}. A run that the "
            f"host cannot record is a run that wasted a bench. The system "
            f"reported: {error}"
        ) from error

    found: set[int] = set()
    for name in names:
        match = RECORD_NAME_PATTERN.match(name)
        if match is not None:
            found.add(int(match.group(1)))
    return found


def draw_run_id(directory: Path, rng: random.Random | None = None) -> int:
    """Draws a run ID that no record of the directory already names.

    The draw is random rather than taken from the hardware, because a record
    carries no device identifier that the user did not add (specification
    section 7). The value needs uniqueness across runs and holds no secret.

    Args:
        directory: The directory that the host writes into.
        rng: The generator to draw from. None draws from the module generator.

    Returns:
        The run ID, 0 to RUN_ID_MAX.

    Raises:
        BolisRecordError: The host cannot read the directory, or every draw
            collided.
    """
    taken = existing_run_ids(directory)
    draw = random.getrandbits if rng is None else rng.getrandbits
    for _attempt in range(RUN_ID_DRAWS):
        run_id = draw(RUN_ID_BITS)
        if run_id not in taken:
            return run_id
    raise BolisRecordError(
        f"{RUN_ID_DRAWS} draws of a run ID each matched a record in "
        f"{directory}, which holds {len(taken)} records."
    )


def record_path(directory: Path, run_id: int) -> Path:
    """Returns the file that one run writes.

    Args:
        directory: The directory that the host writes into.
        run_id: The run ID, 0 to RUN_ID_MAX.

    Returns:
        The path of the record.

    Raises:
        BolisRecordError: The run ID sits outside the range that the frame
            header carries.
    """
    if not 0 <= run_id <= RUN_ID_MAX:
        raise BolisRecordError(
            f"the run ID is {run_id}, which sits outside 0 to {RUN_ID_MAX}."
        )
    return directory / f"bolis-{run_id}.json"


def prepare_directory(directory: Path) -> None:
    """Checks that the host can read the output directory and write into it.

    The host stops before the first cell when it cannot record a run, rather
    than running a bench whose result it cannot keep.

    Args:
        directory: The directory that the host writes into.

    Raises:
        BolisRecordError: The path is absent, is not a directory, or does not
            accept a write.
    """
    if not directory.is_dir():
        raise BolisRecordError(
            f"the output directory {directory} is absent or is not a directory."
        )
    existing_run_ids(directory)

    probe = directory / ".bolis-write-check"
    try:
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError as error:
        raise BolisRecordError(
            f"the host cannot write into the directory {directory}. The "
            f"system reported: {error}"
        ) from error


def write_record(document: Mapping[str, Any], directory: Path) -> Path:
    """Checks one record and writes it as the file of its run.

    The writer states the format version, so a caller supplies the six
    sections of thinkbook section 9 and never the version.

    Args:
        document: The six sections of the record.
        directory: The directory that the host writes into.

    Returns:
        The path of the record that the host wrote.

    Raises:
        BolisRecordError: The record states no run ID, does not meet the
            schema, or did not reach the file.
    """
    complete: dict[str, Any] = {"record_version": RECORD_VERSION}
    complete.update(document)
    complete["record_version"] = RECORD_VERSION

    run = complete.get("run")
    if not isinstance(run, Mapping) or "run_id" not in run:
        raise BolisRecordError("the record states no run ID, so it names no file.")
    run_id = run["run_id"]
    if not isinstance(run_id, int) or isinstance(run_id, bool):
        raise BolisRecordError(
            f"the run ID is {run_id!r}, which is not a whole number."
        )

    validate_record(complete)

    path = record_path(directory, run_id)
    text = json.dumps(complete, indent=2, ensure_ascii=True) + "\n"
    # The record is the product of a run that took minutes at a bench. The
    # write lands on a temporary file in the same directory and then replaces
    # the target, so a failure leaves no half-written record.
    temporary = path.with_name(f"{path.name}.part")
    try:
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise BolisRecordError(
            f"the host did not write the record {path}. The system reported: {error}"
        ) from error
    return path
