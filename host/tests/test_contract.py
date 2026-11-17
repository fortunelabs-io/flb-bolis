"""Tests that hold the two sides of the control line contract together.

The firmware and the host each hold constants of the same contract. Nothing
compiles them together, so a change to one side can leave the other behind.
These cases read the constants out of the C sources and compare them with the
host, and they measure the widest reply that the contract allows against the
line limit.

The reply formatting itself lives in `bol_console.c`, which the reader tests
cannot build, because deviation record D-001 keeps the standard streams inside
the console module and that module needs FreeRTOS, the UART driver, and
ESP-NOW. These cases therefore guard the contract rather than the formatter: a
key added to a counter set trips them, which is what decision record
2026-11-11-control-line-command-fields.md asks a reader to watch.
"""

import json
import re
from pathlib import Path

import pytest

from bolis.protocol import LINE_MAX_BYTES, PROTO_VERSION
from bolis.sweep import FRAMES_PER_CELL

REPOSITORY = Path(__file__).resolve().parents[2]
CONSOLE_SOURCE = REPOSITORY / "components" / "bolis" / "src" / "bol_console.c"
STATS_HEADER = REPOSITORY / "components" / "bolis" / "priv_include" / "bol_stats.h"
SCHEMA = REPOSITORY / "schema" / "run-record.schema.json"

# The prefix and the newline that every line carries beside its JSON object.
LINE_OVERHEAD_BYTES = len("@bol ") + len("\n")

# The widest sequence number that the envelope carries.
WIDEST_SEQ = 4294967295

# The widest cell that the frame header carries.
WIDEST_CELL_ID = 32767


def firmware_constant(path: Path, name: str) -> int:
    """Reads one unsigned integer macro out of a C source file.

    Args:
        path: The C source or header that defines the macro.
        name: The macro name.

    Returns:
        The value of the macro.

    Raises:
        AssertionError: The file defines no such macro.
    """
    match = re.search(
        rf"^#define\s+{re.escape(name)}\s+(\d+)U?\s*$",
        path.read_text(encoding="utf-8"),
        re.M,
    )
    assert match is not None, f"{path.name} defines no {name}"
    return int(match.group(1))


def counter_keys(name: str) -> list[str]:
    """Returns the keys of one counter set of the run record format.

    Args:
        name: The definition name, such as receiver_counters.

    Returns:
        The keys in the order the schema states them.
    """
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return list(schema["$defs"][name]["properties"].keys())


def widest_reply(counters: list[str], bins: int, error_kinds: int) -> int:
    """Returns the bytes of the widest stats reply that a counter set allows.

    Every counter of a pass counts packets of that pass, so the frame budget
    bounds its width. `rejected_lines` counts control lines instead, so it
    takes the width of its type. A histogram holds one count per bin, and
    `send_errors` holds one object per distinct error code.

    Args:
        counters: The keys of the counter set.
        bins: The bins of a histogram.
        error_kinds: The distinct error codes that the reply states.

    Returns:
        The bytes of the line, including the prefix and the newline.
    """
    counter = "9" * len(str(FRAMES_PER_CELL))
    fields = [
        f'"proto":{PROTO_VERSION}',
        '"reply":"stats"',
        f'"seq":{WIDEST_SEQ}',
        '"ok":true',
        f'"cell_id":{WIDEST_CELL_ID}',
        '"pass":"broadcast"',
    ]
    for key in counters:
        if key.endswith("_histogram"):
            bars = ",".join([counter] * bins)
            fields.append(f'"{key}":[{bars}]')
        elif key == "send_errors":
            entry = f'{{"err":"ESP_ERR_ESPNOW_NO_MEM","count":{counter}}}'
            fields.append(f'"{key}":[{",".join([entry] * error_kinds)}]')
        elif key == "rejected_lines":
            # A rejected line is not a packet of the pass, so the frame budget
            # does not bound this counter.
            fields.append(f'"{key}":{WIDEST_SEQ}')
        elif key.startswith("rssi_"):
            fields.append(f'"{key}":-128.0')
        else:
            fields.append(f'"{key}":{counter}')
    body = "{" + ",".join(fields) + "}"
    return len(body) + LINE_OVERHEAD_BYTES


def test_the_firmware_and_the_host_state_one_contract_version() -> None:
    """Both constants change in one release, so a drift breaks every run.

    A host of one version refuses a node of another at hello, before the first
    cell, so a drift between these two constants costs a bench session rather
    than a line of output.
    """
    assert firmware_constant(CONSOLE_SOURCE, "BOL_PROTO_VERSION") == PROTO_VERSION


def test_the_firmware_and_the_host_state_one_line_limit() -> None:
    """A node that writes a longer line than the host reads drops a reply."""
    assert firmware_constant(CONSOLE_SOURCE, "BOL_LINE_MAX_BYTES") == LINE_MAX_BYTES


def test_the_widest_receiver_stats_reply_fits_one_line() -> None:
    """A key added to the receiver counters must keep the reply inside a line.

    The record warns a reader to watch the width of a stats reply as a counter
    is added. This case is that watch.
    """
    bins = firmware_constant(STATS_HEADER, "BOL_HISTOGRAM_BINS")
    width = widest_reply(counter_keys("receiver_counters"), bins, error_kinds=0)

    assert width <= LINE_MAX_BYTES, (
        f"the widest receiver stats reply measures {width} bytes against the "
        f"{LINE_MAX_BYTES}-byte line. A counter no longer fits."
    )


def test_the_widest_sender_stats_reply_fits_one_line_with_one_error_code() -> None:
    """A pass that meets one error code must still report its counters."""
    bins = firmware_constant(STATS_HEADER, "BOL_HISTOGRAM_BINS")
    width = widest_reply(counter_keys("sender_counters"), bins, error_kinds=1)

    assert width <= LINE_MAX_BYTES, (
        f"the widest sender stats reply with one error code measures {width} "
        f"bytes against the {LINE_MAX_BYTES}-byte line."
    )


def test_the_line_carries_fewer_error_codes_than_the_counters_hold() -> None:
    """The counters hold more error slots than one line can state.

    `BOL_SEND_ERROR_SLOTS` bounds the distinct codes that a pass records. The
    line limit bounds the codes that a reply states, and it is the smaller of
    the two. A pass that meets more codes than the line carries draws a reply
    whose `ok` is false and whose `err` is `ESP_ERR_INVALID_SIZE`, so the host
    reads an answer rather than silence.

    This case records where that boundary sits. It fails if the boundary moves,
    which is a change a reader of the contract needs to see.
    """
    bins = firmware_constant(STATS_HEADER, "BOL_HISTOGRAM_BINS")
    slots = firmware_constant(STATS_HEADER, "BOL_SEND_ERROR_SLOTS")
    keys = counter_keys("sender_counters")

    fitting = [
        kinds
        for kinds in range(slots + 1)
        if widest_reply(keys, bins, error_kinds=kinds) <= LINE_MAX_BYTES
    ]

    assert fitting, "no sender stats reply fits one line"
    assert max(fitting) >= 1, "a reply states no error code"
    assert max(fitting) < slots, (
        f"the line now carries {max(fitting)} error codes and the counters hold "
        f"{slots}. The boundary moved, so the reply of a pass that meets every "
        f"slot may no longer need the oversized answer."
    )


@pytest.mark.parametrize("name", ["sender_counters", "receiver_counters"])
def test_every_counter_of_the_record_reaches_a_reply(name: str) -> None:
    """The record states no counter that a node cannot report.

    A key in the record that no reply carries is a key the host can never
    fill, so the schema and the contract would disagree.
    """
    keys = counter_keys(name)

    assert keys, f"{name} states no counter"
    assert "rejected_lines" in keys, f"{name} states no rejected line count"
