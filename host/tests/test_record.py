"""Tests for the run record writer.

Every case runs offline and writes into a temporary directory. The loss
figures below are checked against the values that thinkbook section 3.7
states, rather than against the output of this module.
"""

import json
import math
import os
import random
from pathlib import Path
from typing import Any

import pytest
from examples import record

from bolis.record import (
    RECORD_VERSION,
    RUN_ID_MAX,
    BolisRecordError,
    configured,
    declared,
    derived,
    draw_run_id,
    existing_run_ids,
    load_schema,
    loss_quantity,
    measured,
    prepare_directory,
    record_path,
    validate_record,
    wilson_interval,
    write_record,
)

# Thinkbook section 3.7 states that a cell needs about 1825 frames for a
# half-width of 1 percentage point at 5% loss, and about 1522 frames for half
# a point at 1% loss. The table is the anchor of the interval below.
THINKBOOK_FRAMES_AT_5_PERCENT = 1825
THINKBOOK_HALF_WIDTH = 0.01

# The frames of one pass (thinkbook section 8).
FRAMES_PER_PASS = 2000

# Loose bounds that hold for a pass of 2000 frames.
HIGH_BOUND_OF_NO_LOSS = 0.01
LOW_BOUND_OF_TOTAL_LOSS = 0.99

# The run ID that the scripted draw reaches once the taken one repeats.
FREE_RUN_ID = 9


def test_the_writer_states_the_version_of_the_format() -> None:
    """The first version of the run record format is 1."""
    assert RECORD_VERSION == 1


def test_a_label_names_the_origin_of_its_number() -> None:
    """Each helper attaches one of the four labels."""
    assert measured(7) == {"value": 7, "label": "measured"}
    assert configured(44) == {"value": 44, "label": "configured"}
    assert derived(0.5) == {"value": 0.5, "label": "derived"}
    assert declared("2 m") == {"value": "2 m", "label": "declared"}


def test_the_interval_matches_the_half_width_that_the_thinkbook_states() -> None:
    """At 5% loss over 1825 frames, the half-width is about 1 percentage point.

    Thinkbook section 3.7 states that frame count for that half-width, so the
    interval of this module has to reproduce it.
    """
    lost = round(0.05 * THINKBOOK_FRAMES_AT_5_PERCENT)
    low, high = wilson_interval(lost, THINKBOOK_FRAMES_AT_5_PERCENT)

    half_width = (high - low) / 2
    assert math.isclose(half_width, THINKBOOK_HALF_WIDTH, abs_tol=0.0005)


def test_the_interval_holds_the_share_it_covers() -> None:
    """The bounds sit either side of the ratio."""
    low, high = wilson_interval(13, FRAMES_PER_PASS)

    assert low < 13 / FRAMES_PER_PASS < high


def test_the_interval_of_no_loss_starts_at_zero() -> None:
    """A pass that lost nothing has a lower bound of zero."""
    low, high = wilson_interval(0, FRAMES_PER_PASS)

    assert low == pytest.approx(0.0, abs=1e-12)
    assert 0.0 < high < HIGH_BOUND_OF_NO_LOSS


def test_the_interval_of_total_loss_ends_at_one() -> None:
    """A pass that lost every frame has an upper bound of one."""
    low, high = wilson_interval(FRAMES_PER_PASS, FRAMES_PER_PASS)

    assert high == pytest.approx(1.0, abs=1e-12)
    assert LOW_BOUND_OF_TOTAL_LOSS < low < 1.0


def test_a_narrower_interval_follows_a_longer_pass() -> None:
    """More frames at one share of loss give a tighter interval."""
    short_low, short_high = wilson_interval(50, 1000)
    long_low, long_high = wilson_interval(500, 10000)

    assert (long_high - long_low) < (short_high - short_low)


@pytest.mark.parametrize(("lost", "total"), [(1, 0), (1, -5), (-1, 10), (11, 10)])
def test_an_interval_of_an_impossible_count_raises(lost: int, total: int) -> None:
    """A share needs a positive total and a lost count inside it."""
    with pytest.raises(BolisRecordError):
        wilson_interval(lost, total)


def test_a_loss_quantity_carries_the_derived_label() -> None:
    """A value computed from measured counters is derived."""
    quantity = loss_quantity(13, FRAMES_PER_PASS)

    assert quantity["ratio"] == {"value": 13 / FRAMES_PER_PASS, "label": "derived"}
    assert quantity["wilson_interval_low"]["label"] == "derived"
    assert quantity["wilson_interval_high"]["label"] == "derived"


def test_the_schema_loads() -> None:
    """The writer reaches the schema of the format."""
    assert load_schema()["title"] == "Bolis run record"


def test_a_complete_record_passes_the_check() -> None:
    """The example of the schema cases meets the format."""
    validate_record(record())


def test_a_record_that_fails_the_schema_names_where() -> None:
    """A record that fails the schema is an error, and the message locates it."""
    document = record()
    document["cells"][0]["sender"]["packets_sent"] = FRAMES_PER_PASS

    with pytest.raises(BolisRecordError, match="packets_sent"):
        validate_record(document)


def test_the_file_states_the_run_id_in_decimal_digits(tmp_path: Path) -> None:
    """One value takes one form in the record and in the file name."""
    assert record_path(tmp_path, 2749382104).name == "bolis-2749382104.json"


@pytest.mark.parametrize("run_id", [-1, RUN_ID_MAX + 1])
def test_a_run_id_outside_four_bytes_names_no_file(tmp_path: Path, run_id: int) -> None:
    """The frame header carries the run ID in four bytes."""
    with pytest.raises(BolisRecordError):
        record_path(tmp_path, run_id)


def test_the_reader_finds_the_run_id_of_each_record(tmp_path: Path) -> None:
    """The reader takes each ID from a file name."""
    (tmp_path / "bolis-7.json").write_text("{}", encoding="utf-8")
    (tmp_path / "bolis-2749382104.json").write_text("{}", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("", encoding="utf-8")
    (tmp_path / "bolis-abc.json").write_text("{}", encoding="utf-8")

    assert existing_run_ids(tmp_path) == {7, 2749382104}


def test_the_reader_ignores_a_record_that_does_not_parse(tmp_path: Path) -> None:
    """One unreadable record does not stop a run."""
    (tmp_path / "bolis-7.json").write_text("this is not JSON", encoding="utf-8")

    assert existing_run_ids(tmp_path) == {7}


def test_a_drawn_run_id_avoids_the_records_that_are_there(tmp_path: Path) -> None:
    """A draw that matches a stored record repeats."""
    (tmp_path / "bolis-5.json").write_text("{}", encoding="utf-8")

    class TakenThenFree(random.Random):
        """Draws the taken value first, then a free one."""

        def __init__(self) -> None:
            super().__init__()
            self.values = [5, 5, 9]

        def getrandbits(self, k: int) -> int:
            """Returns the next scripted value."""
            return self.values.pop(0)

    assert draw_run_id(tmp_path, TakenThenFree()) == FREE_RUN_ID


def test_a_draw_that_never_frees_raises(tmp_path: Path) -> None:
    """A directory that matches every draw stops the run rather than looping."""
    (tmp_path / "bolis-5.json").write_text("{}", encoding="utf-8")

    class AlwaysTaken(random.Random):
        """Draws one value that a record already names."""

        def getrandbits(self, k: int) -> int:
            """Returns the taken value."""
            return 5

    with pytest.raises(BolisRecordError, match="draws of a run ID"):
        draw_run_id(tmp_path, AlwaysTaken())


def test_a_directory_that_is_absent_stops_the_run(tmp_path: Path) -> None:
    """A run that the host cannot record stops before the first cell."""
    with pytest.raises(BolisRecordError, match="absent"):
        prepare_directory(tmp_path / "no-such-directory")


@pytest.mark.skipif(
    not hasattr(os, "geteuid") or os.geteuid() == 0,
    reason="a mode of 0o500 stops no write for the root user or on a system without it",
)
def test_a_directory_that_refuses_a_write_stops_the_run(tmp_path: Path) -> None:
    """A directory that the host cannot write into stops the run."""
    directory = tmp_path / "read-only"
    directory.mkdir()
    directory.chmod(0o500)
    try:
        with pytest.raises(BolisRecordError, match="cannot write"):
            prepare_directory(directory)
    finally:
        directory.chmod(0o700)


def test_a_directory_that_accepts_a_write_leaves_no_file(tmp_path: Path) -> None:
    """The check of a directory leaves nothing behind."""
    prepare_directory(tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_the_writer_writes_a_record_that_meets_the_schema(tmp_path: Path) -> None:
    """One run writes one file, and that file parses."""
    document = record()
    del document["record_version"]

    path = write_record(document, tmp_path)

    assert path.name == f"bolis-{document['run']['run_id']}.json"
    written: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    assert written["record_version"] == RECORD_VERSION
    validate_record(written)


def test_the_writer_states_the_version_that_it_produces(tmp_path: Path) -> None:
    """A caller supplies the six sections, and the writer states the version."""
    document = record()
    document["record_version"] = 99

    path = write_record(document, tmp_path)

    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["record_version"] == RECORD_VERSION


def test_the_writer_refuses_a_record_that_fails_the_schema(tmp_path: Path) -> None:
    """A record that fails the schema reaches no file."""
    document = record()
    document["cells"][0]["post_retry_loss"] = loss_quantity(3, FRAMES_PER_PASS)

    with pytest.raises(BolisRecordError):
        write_record(document, tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_the_writer_refuses_a_record_without_a_run_id(tmp_path: Path) -> None:
    """A record that names no run names no file."""
    document = record()
    del document["run"]["run_id"]

    with pytest.raises(BolisRecordError, match="no run ID"):
        write_record(document, tmp_path)


def test_the_writer_leaves_no_part_file(tmp_path: Path) -> None:
    """A finished write leaves the record and nothing beside it."""
    write_record(record(), tmp_path)

    names = sorted(path.name for path in tmp_path.iterdir())
    assert names == ["bolis-2749382104.json"]


def test_a_written_record_states_no_mac_address(tmp_path: Path) -> None:
    """The record stores no MAC address (specification section 7)."""
    path = write_record(record(), tmp_path)

    text = path.read_text(encoding="utf-8")
    assert "mac" not in text.lower()
