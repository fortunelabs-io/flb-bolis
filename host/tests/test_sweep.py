"""Tests for the sweep cell plan (thinkbook section 8)."""

import pytest

from bolis.sweep import (
    Baseline,
    BolisSweepError,
    Variable,
    build_grid_plan,
    build_plan,
    payload_bytes_for_limit,
    resolve_baseline,
    validate_baseline,
)

# The literal values below come from thinkbook section 8 and decision
# 2026-10-01-local-one-variable-sweep.md, not from bolis.sweep's own
# constants, so a typo in the module cannot make its own test pass.
EXPECTED_CHANNELS = tuple(range(1, 12))
EXPECTED_POWER_SET_VALUES = (8, 20, 28, 34, 44, 52, 56, 60, 66, 72, 80)
EXPECTED_PAYLOAD_BYTES_V1 = (14, 128, 249, 250, 251, 499, 500, 501)
EXPECTED_PAYLOAD_BYTES_V2 = (14, 250, 251, 1469, 1470, 1471, 2940, 2941)
PAYLOAD_LIMIT_BYTES_V1 = 250
PAYLOAD_LIMIT_BYTES_V2 = 1470
FALLBACK_BASELINE = Baseline(channel=1, power_set_value=44, payload_bytes=128)
DEFAULT_PLAN_CELL_COUNT = 36
GRID_PLAN_CELL_COUNT = 968
BASELINE_REPEAT_POSITIONS = (5, 11, 17, 23, 29, 35)
EXPECTED_FRAMES_PER_CELL = 2000
PAYLOAD_MIN_BYTES = 14


def test_payload_bytes_for_limit_v1_matches_the_thinkbook() -> None:
    """The v1.0 payload list follows L = 250 bytes, as thinkbook section 8 states."""
    assert payload_bytes_for_limit(PAYLOAD_LIMIT_BYTES_V1) == EXPECTED_PAYLOAD_BYTES_V1


def test_payload_bytes_for_limit_v2_matches_the_thinkbook() -> None:
    """The v2.0 payload list follows L = 1470 bytes, as thinkbook section 8 states."""
    assert payload_bytes_for_limit(PAYLOAD_LIMIT_BYTES_V2) == EXPECTED_PAYLOAD_BYTES_V2


def test_payload_bytes_for_limit_rejects_an_unknown_limit() -> None:
    """A limit that is neither 250 nor 1470 raises, and the message names it."""
    with pytest.raises(BolisSweepError, match="999"):
        payload_bytes_for_limit(999)


def test_resolve_baseline_falls_back_when_the_user_gives_none() -> None:
    """With no user configuration, the fallback baseline of section 8 applies."""
    baseline, is_fallback = resolve_baseline(None)
    assert baseline == FALLBACK_BASELINE
    assert is_fallback is True


def test_resolve_baseline_keeps_the_user_configuration_unchanged() -> None:
    """A user baseline passes through unchanged, and is_fallback is False."""
    user_baseline = Baseline(channel=6, power_set_value=60, payload_bytes=500)
    baseline, is_fallback = resolve_baseline(user_baseline)
    assert baseline == user_baseline
    assert is_fallback is False


def test_validate_baseline_accepts_the_fallback() -> None:
    """The fallback baseline passes validation unchanged."""
    assert validate_baseline(FALLBACK_BASELINE) == FALLBACK_BASELINE


def test_validate_baseline_accepts_the_range_boundaries() -> None:
    """A baseline at the channel and payload minimums passes."""
    edge = Baseline(
        channel=EXPECTED_CHANNELS[0],
        power_set_value=EXPECTED_POWER_SET_VALUES[0],
        payload_bytes=PAYLOAD_MIN_BYTES,
    )
    assert validate_baseline(edge) == edge


def test_validate_baseline_rejects_a_channel_outside_the_range() -> None:
    """A baseline channel outside 1 to 11 raises and names the value."""
    with pytest.raises(BolisSweepError, match="99"):
        validate_baseline(Baseline(channel=99, power_set_value=44, payload_bytes=128))


def test_validate_baseline_rejects_an_unquantized_power_value() -> None:
    """A baseline power the radio does not quantize to raises and names it."""
    with pytest.raises(BolisSweepError, match="13"):
        validate_baseline(Baseline(channel=1, power_set_value=13, payload_bytes=128))


def test_validate_baseline_rejects_a_payload_below_the_header() -> None:
    """A baseline payload smaller than the 14-byte header raises."""
    with pytest.raises(BolisSweepError, match="13"):
        validate_baseline(Baseline(channel=1, power_set_value=44, payload_bytes=13))


def test_build_plan_rejects_an_invalid_user_baseline() -> None:
    """An out-of-range baseline raises instead of yielding an inconsistent plan."""
    bad = Baseline(channel=99, power_set_value=7, payload_bytes=1)
    with pytest.raises(BolisSweepError):
        build_plan(bad, PAYLOAD_LIMIT_BYTES_V2, seed=1)


def test_build_grid_plan_rejects_an_invalid_user_baseline() -> None:
    """The grid builder validates its baseline on the same terms."""
    bad = Baseline(channel=99, power_set_value=7, payload_bytes=1)
    with pytest.raises(BolisSweepError):
        build_grid_plan(bad, PAYLOAD_LIMIT_BYTES_V2, seed=1)


def test_both_plans_state_the_frames_each_cell_sends() -> None:
    """Each plan carries the 2000 frames per cell that decision 4 states."""
    plan = build_plan(None, PAYLOAD_LIMIT_BYTES_V2, seed=1)
    grid = build_grid_plan(None, PAYLOAD_LIMIT_BYTES_V2, seed=1)
    assert plan.frames_per_cell == EXPECTED_FRAMES_PER_CELL
    assert grid.frames_per_cell == EXPECTED_FRAMES_PER_CELL


def test_build_plan_has_about_36_cells_for_either_payload_limit() -> None:
    """The default plan has about 36 cells per pass, for both payload limits."""
    for payload_limit_bytes in (PAYLOAD_LIMIT_BYTES_V1, PAYLOAD_LIMIT_BYTES_V2):
        plan = build_plan(None, payload_limit_bytes, seed=1)
        assert len(plan.cells) == DEFAULT_PLAN_CELL_COUNT


def test_build_plan_sweeps_every_channel_the_country_code_allows() -> None:
    """The channel cells cover 1 to 11, the range the default country code allows."""
    plan = build_plan(None, PAYLOAD_LIMIT_BYTES_V2, seed=2)
    channels = {
        cell.channel for cell in plan.cells if cell.variable is Variable.CHANNEL
    }
    assert channels == set(EXPECTED_CHANNELS)


def test_build_plan_sweeps_every_quantized_power_set_value() -> None:
    """The power cells cover the 11 quantized set values."""
    plan = build_plan(None, PAYLOAD_LIMIT_BYTES_V2, seed=2)
    powers = {
        cell.power_set_value for cell in plan.cells if cell.variable is Variable.POWER
    }
    assert powers == set(EXPECTED_POWER_SET_VALUES)


def test_build_plan_sweeps_every_listed_payload_size() -> None:
    """The payload cells cover the eight listed sizes for the given limit."""
    plan = build_plan(None, PAYLOAD_LIMIT_BYTES_V2, seed=2)
    payloads = {
        cell.payload_bytes for cell in plan.cells if cell.variable is Variable.PAYLOAD
    }
    assert payloads == set(EXPECTED_PAYLOAD_BYTES_V2)


def test_build_plan_holds_the_other_two_variables_at_the_baseline() -> None:
    """Varying one variable at a time holds the other two fixed at the baseline."""
    plan = build_plan(None, PAYLOAD_LIMIT_BYTES_V2, seed=4)
    for cell in plan.cells:
        if cell.variable is Variable.CHANNEL:
            assert cell.power_set_value == FALLBACK_BASELINE.power_set_value
            assert cell.payload_bytes == FALLBACK_BASELINE.payload_bytes
        elif cell.variable is Variable.POWER:
            assert cell.channel == FALLBACK_BASELINE.channel
            assert cell.payload_bytes == FALLBACK_BASELINE.payload_bytes
        elif cell.variable is Variable.PAYLOAD:
            assert cell.channel == FALLBACK_BASELINE.channel
            assert cell.power_set_value == FALLBACK_BASELINE.power_set_value


def test_build_plan_repeats_the_baseline_cell_after_every_five_cells() -> None:
    """The baseline cell repeats at fixed positions, forming the drift band."""
    plan = build_plan(None, PAYLOAD_LIMIT_BYTES_V2, seed=5)
    repeat_positions = tuple(
        index
        for index, cell in enumerate(plan.cells)
        if cell.variable is Variable.BASELINE
    )
    assert repeat_positions == BASELINE_REPEAT_POSITIONS


def test_build_plan_same_seed_yields_the_same_order() -> None:
    """The seeded shuffle is reproducible: the same seed yields the same order."""
    plan_a = build_plan(None, PAYLOAD_LIMIT_BYTES_V2, seed=99)
    plan_b = build_plan(None, PAYLOAD_LIMIT_BYTES_V2, seed=99)
    assert plan_a.cells == plan_b.cells


def test_build_plan_states_the_seed_it_was_built_with() -> None:
    """The plan carries its own seed, so the host can record it."""
    chosen_seed = 123
    plan = build_plan(None, PAYLOAD_LIMIT_BYTES_V2, seed=chosen_seed)
    assert plan.seed == chosen_seed


def test_build_plan_uses_the_user_baseline_when_one_is_given() -> None:
    """A user baseline overrides the fallback, and is_fallback becomes False."""
    user_baseline = Baseline(channel=6, power_set_value=60, payload_bytes=500)
    plan = build_plan(user_baseline, PAYLOAD_LIMIT_BYTES_V2, seed=8)
    assert plan.baseline == user_baseline
    assert plan.is_fallback_baseline is False


def test_build_grid_plan_has_968_cells() -> None:
    """The full grid visits 11 channels by 11 power levels by 8 payloads."""
    grid = build_grid_plan(None, PAYLOAD_LIMIT_BYTES_V2, seed=6)
    assert len(grid.cells) == GRID_PLAN_CELL_COUNT


def test_build_grid_plan_visits_every_combination_exactly_once() -> None:
    """The full grid visits every combination once: none missing, none repeated."""
    grid = build_grid_plan(None, PAYLOAD_LIMIT_BYTES_V2, seed=6)
    seen = {
        (cell.channel, cell.power_set_value, cell.payload_bytes) for cell in grid.cells
    }
    expected = {
        (channel, power, payload)
        for channel in EXPECTED_CHANNELS
        for power in EXPECTED_POWER_SET_VALUES
        for payload in EXPECTED_PAYLOAD_BYTES_V2
    }
    assert seen == expected
    assert len(grid.cells) == len(seen)
