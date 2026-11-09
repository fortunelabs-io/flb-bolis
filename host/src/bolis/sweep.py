"""The sweep cell plan (decision 2026-10-01-local-one-variable-sweep.md).

Builds the ordered sequence of cells that one pass of a run visits: the
default plan varies one variable at a time around a baseline, and the grid
plan visits every combination (thinkbook section 8). Both plans shuffle
their cells with a recorded seed, and the default plan repeats the baseline
cell after every BASELINE_REPEAT_INTERVAL cells to track drift. This module
computes a plan only. It makes no serial access and no network access, and
it writes no run record.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from bolis import BolisError

# The channel range that the default country code "01" allows (thinkbook
# section 4 and section 8).
CHANNEL_MIN = 1
CHANNEL_MAX = 11
CHANNELS: tuple[int, ...] = tuple(range(CHANNEL_MIN, CHANNEL_MAX + 1))

# The 11 transmit power set values, which quantize to 2 to 20 dBm (thinkbook
# section 4 and section 8).
POWER_SET_VALUES: tuple[int, ...] = (8, 20, 28, 34, 44, 52, 56, 60, 66, 72, 80)

# The packet payload limit L, in bytes (thinkbook section 3.1). L_V1 selects
# the v1.0 payload list with --limit 250. L_V2 is the default. The limit
# reaches this module as an int, because it arrives from the command line,
# so payload_bytes_for_limit checks it at run time.
PAYLOAD_LIMIT_BYTES_V1 = 250
PAYLOAD_LIMIT_BYTES_V2 = 1470

# The data frame header is 14 bytes (control line wire format record), so a
# payload below that could never form one packet.
PAYLOAD_MIN_BYTES = 14

# The swept payload sizes, in bytes, around the frame boundary for each
# limit above (thinkbook section 8).
PAYLOAD_BYTES_V1: tuple[int, ...] = (14, 128, 249, 250, 251, 499, 500, 501)
PAYLOAD_BYTES_V2: tuple[int, ...] = (14, 250, 251, 1469, 1470, 1471, 2940, 2941)

# The fallback baseline when the user gives no configuration (thinkbook
# section 8): channel 1, power set value 44 (11 dBm), payload 128 bytes.
FALLBACK_CHANNEL = 1
FALLBACK_POWER_SET_VALUE = 44
FALLBACK_PAYLOAD_BYTES = 128

# The baseline cell repeats after every 5 cells, to measure drift (decision
# 4, thinkbook section 8).
BASELINE_REPEAT_INTERVAL = 5

# Frames that one pass sends per cell, at 1 Mbps (decision 2, thinkbook
# section 8, citing section 3.7).
FRAMES_PER_CELL = 2000


class BolisSweepError(BolisError):
    """Raised when a sweep plan cannot be built from its arguments."""


class Variable(Enum):
    """The variable a cell varies away from the baseline.

    BASELINE marks the baseline cell itself, including every drift repeat.
    GRID marks a cell of the full factorial grid, which varies every
    variable at once and attributes loss to no single one of them.
    """

    BASELINE = "baseline"
    CHANNEL = "channel"
    POWER = "power"
    PAYLOAD = "payload"
    GRID = "grid"


@dataclass(frozen=True)
class Baseline:
    """The channel, power, and payload around which a plan varies.

    Attributes:
        channel: The baseline channel, CHANNEL_MIN to CHANNEL_MAX.
        power_set_value: The baseline transmit power set value, one of
            POWER_SET_VALUES.
        payload_bytes: The baseline payload size, in bytes.
    """

    channel: int
    power_set_value: int
    payload_bytes: int


FALLBACK_BASELINE = Baseline(
    channel=FALLBACK_CHANNEL,
    power_set_value=FALLBACK_POWER_SET_VALUE,
    payload_bytes=FALLBACK_PAYLOAD_BYTES,
)


@dataclass(frozen=True)
class Cell:
    """One condition that a pass sends: a channel, a power, and a payload.

    Attributes:
        channel: The channel of this cell.
        power_set_value: The transmit power set value of this cell.
        payload_bytes: The payload size of this cell, in bytes.
        variable: The variable this cell varies away from the baseline.
    """

    channel: int
    power_set_value: int
    payload_bytes: int
    variable: Variable


@dataclass(frozen=True)
class CellPlan:
    """The ordered sequence of cells that one pass of a run visits.

    Attributes:
        baseline: The baseline this plan varies around.
        is_fallback_baseline: True when the user gave no configuration, so
            the fallback baseline of thinkbook section 8 applied. The run
            record states this (decision 4).
        payload_limit_bytes: The packet payload limit L that the payload
            list follows, 250 or 1470 (thinkbook section 3.1).
        seed: The seed that shuffled the cells, so the order is reproducible
            (thinkbook section 8).
        frames_per_cell: The frames that one pass sends per cell. The run
            record states this value (decision 4).
        cells: The cells in the order a pass visits them.
    """

    baseline: Baseline
    is_fallback_baseline: bool
    payload_limit_bytes: int
    seed: int
    frames_per_cell: int
    cells: tuple[Cell, ...]


def validate_baseline(baseline: Baseline) -> Baseline:
    """Checks that every value of a baseline falls inside the swept range.

    The command line validates the same three values before a run starts.
    This module repeats the check, because it accepts a Baseline from any
    caller, and an out-of-range value would otherwise reach the plan. The
    channel sweep iterates CHANNELS and would discard a bad channel
    silently, which yields a plan whose baseline cells and swept cells
    disagree.

    Args:
        baseline: The channel, power, and payload to check.

    Returns:
        The same baseline, unchanged.

    Raises:
        BolisSweepError: A value sits outside the range that the sweep
            covers. The message names the value and the valid range.
    """
    if not (CHANNEL_MIN <= baseline.channel <= CHANNEL_MAX):
        raise BolisSweepError(
            f"the baseline channel is {baseline.channel}. The default country "
            f"code allows {CHANNEL_MIN} to {CHANNEL_MAX}."
        )
    if baseline.power_set_value not in POWER_SET_VALUES:
        allowed = ", ".join(str(value) for value in POWER_SET_VALUES)
        raise BolisSweepError(
            f"the baseline power set value is {baseline.power_set_value}. The "
            f"radio quantizes to one of: {allowed}."
        )
    if baseline.payload_bytes < PAYLOAD_MIN_BYTES:
        raise BolisSweepError(
            f"the baseline payload is {baseline.payload_bytes} bytes. The data "
            f"frame header needs {PAYLOAD_MIN_BYTES} bytes, so the payload "
            "cannot be smaller."
        )
    return baseline


def resolve_baseline(user_baseline: Baseline | None) -> tuple[Baseline, bool]:
    """Resolves the run baseline from the user's configuration, or the fallback.

    Args:
        user_baseline: The user's channel, power, and payload, or None if the
            user gave no configuration.

    Returns:
        A tuple of the resolved baseline and whether it is the fallback
        baseline of thinkbook section 8. The second value is True only when
        user_baseline is None.

    Raises:
        BolisSweepError: user_baseline holds a value outside the swept range.
    """
    if user_baseline is not None:
        return validate_baseline(user_baseline), False
    return FALLBACK_BASELINE, True


def payload_bytes_for_limit(payload_limit_bytes: int) -> tuple[int, ...]:
    """Returns the swept payload sizes for one packet payload limit L.

    Args:
        payload_limit_bytes: The packet payload limit L: 250 for ESP-NOW
            v1.0 or 1470 for v2.0 (thinkbook section 3.1).

    Returns:
        The eight payload sizes that thinkbook section 8 lists for that
        limit, in bytes.

    Raises:
        BolisSweepError: payload_limit_bytes is neither 250 nor 1470.
    """
    if payload_limit_bytes == PAYLOAD_LIMIT_BYTES_V1:
        return PAYLOAD_BYTES_V1
    if payload_limit_bytes == PAYLOAD_LIMIT_BYTES_V2:
        return PAYLOAD_BYTES_V2
    raise BolisSweepError(
        f"the payload limit is {payload_limit_bytes} bytes. ESP-NOW defines "
        "250 bytes for v1.0 or 1470 bytes for v2.0."
    )


def _baseline_cell(baseline: Baseline) -> Cell:
    return Cell(
        channel=baseline.channel,
        power_set_value=baseline.power_set_value,
        payload_bytes=baseline.payload_bytes,
        variable=Variable.BASELINE,
    )


def _swept_cells(baseline: Baseline, payload_limit_bytes: int) -> list[Cell]:
    """Builds the one-variable-at-a-time cells, before the shuffle and the repeats."""
    cells = [
        Cell(
            channel=channel,
            power_set_value=baseline.power_set_value,
            payload_bytes=baseline.payload_bytes,
            variable=Variable.CHANNEL,
        )
        for channel in CHANNELS
    ]
    cells.extend(
        Cell(
            channel=baseline.channel,
            power_set_value=power_set_value,
            payload_bytes=baseline.payload_bytes,
            variable=Variable.POWER,
        )
        for power_set_value in POWER_SET_VALUES
    )
    cells.extend(
        Cell(
            channel=baseline.channel,
            power_set_value=baseline.power_set_value,
            payload_bytes=payload_bytes,
            variable=Variable.PAYLOAD,
        )
        for payload_bytes in payload_bytes_for_limit(payload_limit_bytes)
    )
    return cells


def _with_baseline_repeats(
    cells: Sequence[Cell], baseline: Baseline
) -> tuple[Cell, ...]:
    """Inserts a baseline repeat after every BASELINE_REPEAT_INTERVAL cells."""
    baseline_cell = _baseline_cell(baseline)
    result: list[Cell] = []
    for index, cell in enumerate(cells, start=1):
        result.append(cell)
        if index % BASELINE_REPEAT_INTERVAL == 0:
            result.append(baseline_cell)
    return tuple(result)


def build_plan(
    user_baseline: Baseline | None, payload_limit_bytes: int, seed: int
) -> CellPlan:
    """Builds the default one-variable-at-a-time cell plan (decision 4).

    Varies the channel, then the transmit power, then the payload, one at a
    time around the baseline, holding the other two variables at the
    baseline. Shuffles the combined list with the given seed, then repeats
    the baseline cell after every BASELINE_REPEAT_INTERVAL cells to form the
    drift band.

    Args:
        user_baseline: The user's channel, power, and payload, or None to use
            the fallback baseline.
        payload_limit_bytes: The packet payload limit L: 250 or 1470.
        seed: The seed that shuffles the cell order. The caller records this
            seed so the order is reproducible.

    Returns:
        The cell plan, with about 36 cells for either payload limit: 11
        channel cells, 11 power cells, and 8 payload cells, plus 6 baseline
        repeats.

    Raises:
        BolisSweepError: payload_limit_bytes is neither 250 nor 1470, or
            user_baseline holds a value outside the swept range.
    """
    baseline, is_fallback_baseline = resolve_baseline(user_baseline)
    swept = _swept_cells(baseline, payload_limit_bytes)
    # The seed makes the shuffle reproducible, so slow drift spreads across
    # all variables (decision 4). It is not a secret, so Bandit's S311 does
    # not apply.
    random.Random(seed).shuffle(swept)  # noqa: S311
    cells = _with_baseline_repeats(swept, baseline)
    return CellPlan(
        baseline=baseline,
        is_fallback_baseline=is_fallback_baseline,
        payload_limit_bytes=payload_limit_bytes,
        seed=seed,
        frames_per_cell=FRAMES_PER_CELL,
        cells=cells,
    )


def build_grid_plan(
    user_baseline: Baseline | None, payload_limit_bytes: int, seed: int
) -> CellPlan:
    """Builds the full factorial grid cell plan, which the user selects (decision 4).

    Visits every combination of channel, transmit power, and payload. A grid
    cell varies every variable at once, so the plan attributes loss to no
    single one of them. The grid carries no baseline repeat: thinkbook
    section 8 states its cell count as the exact product of its three
    variable counts, with no drift band added.

    Args:
        user_baseline: The user's channel, power, and payload, or None to use
            the fallback baseline. The run record states this baseline even
            though no grid cell holds it fixed.
        payload_limit_bytes: The packet payload limit L: 250 or 1470.
        seed: The seed that shuffles the cell order. The caller records this
            seed so the order is reproducible.

    Returns:
        The cell plan, with 11 x 11 x 8 = 968 cells.

    Raises:
        BolisSweepError: payload_limit_bytes is neither 250 nor 1470, or
            user_baseline holds a value outside the swept range.
    """
    baseline, is_fallback_baseline = resolve_baseline(user_baseline)
    payload_points = payload_bytes_for_limit(payload_limit_bytes)
    cells = [
        Cell(
            channel=channel,
            power_set_value=power_set_value,
            payload_bytes=payload_bytes,
            variable=Variable.GRID,
        )
        for channel in CHANNELS
        for power_set_value in POWER_SET_VALUES
        for payload_bytes in payload_points
    ]
    # See the comment above the shuffle in build_plan: the seed is not a
    # secret, so Bandit's S311 does not apply.
    random.Random(seed).shuffle(cells)  # noqa: S311
    return CellPlan(
        baseline=baseline,
        is_fallback_baseline=is_fallback_baseline,
        payload_limit_bytes=payload_limit_bytes,
        seed=seed,
        frames_per_cell=FRAMES_PER_CELL,
        cells=tuple(cells),
    )
