"""Tests for the bolis command line interface."""

import itertools
import json
import re
from pathlib import Path

import pytest

import bolis.flasher
from bolis.cli import (
    BolisValidationError,
    RunArgs,
    build_cell_plan,
    build_parser,
    format_plan,
    generate_seed,
    main,
    resolve_user_baseline,
    validate_channel,
    validate_distinct_ports,
    validate_payload_bytes,
    validate_power_set_value,
)
from bolis.sweep import Baseline

# The literal values below come from thinkbook section 8, decision
# 2026-10-01-local-one-variable-sweep.md, and decision
# 2026-11-10-run-plan-resolution.md, not from bolis.cli's own constants, so a
# typo in the module cannot make its own test pass.
EXPECTED_CHANNEL_MIN = 1
EXPECTED_CHANNEL_MAX = 11
EXPECTED_POWER_SET_VALUES = (8, 20, 28, 34, 44, 52, 56, 60, 66, 72, 80)
EXPECTED_PAYLOAD_MIN_BYTES = 14
EXPECTED_FALLBACK_CHANNEL = 1
EXPECTED_FALLBACK_POWER_SET_VALUE = 44
EXPECTED_FALLBACK_PAYLOAD_BYTES = 128
EXPECTED_PAYLOAD_LIMIT_BYTES_V1 = 250
EXPECTED_PAYLOAD_LIMIT_BYTES_V2 = 1470
EXPECTED_PAYLOAD_BYTES_V1 = (14, 128, 249, 250, 251, 499, 500, 501)
EXPECTED_PAYLOAD_BYTES_V2 = (14, 250, 251, 1469, 1470, 1471, 2940, 2941)
EXPECTED_DEFAULT_PLAN_CELL_COUNT = 36
EXPECTED_GRID_PLAN_CELL_COUNT = 968
EXPECTED_FRAMES_PER_CELL = 2000
EXPECTED_SEED_BITS = 32

# One fixed seed, so a plan test reads the same cell order on every run.
FIXED_SEED = 12345

PORTS = ("/dev/ttyUSB0", "/dev/ttyUSB1")

# Six hexadecimal pairs joined by colons. A role reply carries a MAC address,
# and no plan, log, run record, or report may state one.
MAC_PATTERN = re.compile(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}")

# The fallback value of each baseline option, as the text a user would type.
# A user who types exactly these three values configured a baseline, so the
# plan must not report the fallback baseline.
FALLBACK_TEXT = {
    "--channel": str(EXPECTED_FALLBACK_CHANNEL),
    "--power": str(EXPECTED_FALLBACK_POWER_SET_VALUE),
    "--payload": str(EXPECTED_FALLBACK_PAYLOAD_BYTES),
}
BASELINE_OPTIONS = ("--channel", "--power", "--payload")
OPTION_SUBSETS = [
    subset
    for size in range(len(BASELINE_OPTIONS) + 1)
    for subset in itertools.combinations(BASELINE_OPTIONS, size)
]


def run_args(
    user_baseline: Baseline | None = None,
    payload_limit_bytes: int = EXPECTED_PAYLOAD_LIMIT_BYTES_V2,
    plan: str = "default",
) -> RunArgs:
    """Builds run arguments for a plan test, with the ports held constant.

    Args:
        user_baseline: The baseline the user configured, or None.
        payload_limit_bytes: The packet payload limit L.
        plan: The plan kind, default or grid.

    Returns:
        The validated run arguments.
    """
    return RunArgs(
        sender_port=PORTS[0],
        receiver_port=PORTS[1],
        user_baseline=user_baseline,
        payload_limit_bytes=payload_limit_bytes,
        plan=plan,
        mode="broadcast",
        print_plan=True,
    )


def payload_sizes_in(plan_text: str) -> set[int]:
    """Reads every payload size that the cell table of a plan states.

    Args:
        plan_text: The output of format_plan.

    Returns:
        The distinct payload sizes, in bytes.
    """
    sizes: set[int] = set()
    for line in plan_text.splitlines():
        parts = line.split()
        if len(parts) > 1 and parts[0].isdigit() and "payload" in parts:
            sizes.add(int(parts[parts.index("payload") + 1]))
    return sizes


def test_validate_channel_accepts_the_range_boundaries() -> None:
    """A channel at the minimum or the maximum passes unchanged."""
    assert validate_channel(EXPECTED_CHANNEL_MIN) == EXPECTED_CHANNEL_MIN
    assert validate_channel(EXPECTED_CHANNEL_MAX) == EXPECTED_CHANNEL_MAX


def test_validate_channel_rejects_a_channel_outside_the_range() -> None:
    """A channel outside the range raises, and the message names the value."""
    with pytest.raises(BolisValidationError, match="99"):
        validate_channel(99)


def test_validate_power_set_value_accepts_every_quantized_value() -> None:
    """Each of the eleven quantized power values passes unchanged."""
    for value in EXPECTED_POWER_SET_VALUES:
        assert validate_power_set_value(value) == value


def test_validate_power_set_value_rejects_a_value_outside_the_set() -> None:
    """A power value that the radio does not quantize to raises."""
    with pytest.raises(BolisValidationError, match="13"):
        validate_power_set_value(13)


def test_validate_payload_bytes_accepts_the_minimum() -> None:
    """A payload at the 14-byte header minimum passes unchanged."""
    assert validate_payload_bytes(EXPECTED_PAYLOAD_MIN_BYTES) == (
        EXPECTED_PAYLOAD_MIN_BYTES
    )


def test_validate_payload_bytes_rejects_a_payload_smaller_than_the_header() -> None:
    """A payload smaller than the header raises, and the message names the value."""
    with pytest.raises(BolisValidationError, match="13"):
        validate_payload_bytes(13)


def test_validate_distinct_ports_rejects_two_equal_ports() -> None:
    """Two equal ports raise, because Bolis needs one port per node."""
    with pytest.raises(BolisValidationError, match="ttyUSB0"):
        validate_distinct_ports("/dev/ttyUSB0", "/dev/ttyUSB0")


def test_resolve_user_baseline_returns_none_when_every_option_is_absent() -> None:
    """Three absent options mean the user configured no baseline."""
    assert resolve_user_baseline(None, None, None) is None


@pytest.mark.parametrize(
    ("channel", "power_set_value", "payload_bytes"),
    [
        (6, None, None),
        (None, 20, None),
        (None, None, 500),
        (6, 20, None),
        (6, None, 500),
        (None, 20, 500),
        (6, 20, 500),
    ],
)
def test_resolve_user_baseline_fills_each_absent_option_with_its_fallback(
    channel: int | None, power_set_value: int | None, payload_bytes: int | None
) -> None:
    """One typed option is a configuration, and the other two take the fallback."""
    baseline = resolve_user_baseline(channel, power_set_value, payload_bytes)
    assert baseline is not None
    assert baseline.channel == (
        EXPECTED_FALLBACK_CHANNEL if channel is None else channel
    )
    assert baseline.power_set_value == (
        EXPECTED_FALLBACK_POWER_SET_VALUE
        if power_set_value is None
        else power_set_value
    )
    assert baseline.payload_bytes == (
        EXPECTED_FALLBACK_PAYLOAD_BYTES if payload_bytes is None else payload_bytes
    )


def test_resolve_user_baseline_validates_only_a_typed_value() -> None:
    """A typed value outside its range raises, and the message names the value."""
    with pytest.raises(BolisValidationError, match="99"):
        resolve_user_baseline(99, None, None)


@pytest.mark.parametrize("given", OPTION_SUBSETS)
def test_the_plan_reports_the_fallback_baseline_only_when_all_three_are_absent(
    given: tuple[str, ...], capsys: pytest.CaptureFixture[str]
) -> None:
    """The fallback flag follows the options, not the values the user typed.

    Each option carries its own fallback value here, so a plan that compared
    values rather than presence would report the fallback baseline for every
    one of the eight combinations.
    """
    argv = ["run", *PORTS, "--print-plan"]
    for option in given:
        argv.extend([option, FALLBACK_TEXT[option]])

    assert main(argv) == 0
    out = capsys.readouterr().out
    expected = "fallback" if len(given) == 0 else "user"
    assert f"Baseline source: {expected}" in out


def test_print_plan_returns_zero_and_a_run_without_it_returns_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Two statuses report two outcomes: a plan built, and a run blocked."""
    assert main(["run", *PORTS, "--print-plan"]) == 0
    assert "bolis run plan" in capsys.readouterr().out

    assert main(["run", *PORTS]) == 1
    err = capsys.readouterr().err
    assert "not implemented" in err
    assert "plan holds" in err


def test_the_default_plan_carries_the_cell_count_of_the_thinkbook() -> None:
    """The default plan holds 30 swept cells and 6 baseline repeats."""
    plan = build_cell_plan(run_args(), seed=1)
    assert len(plan.cells) == EXPECTED_DEFAULT_PLAN_CELL_COUNT
    assert plan.frames_per_cell == EXPECTED_FRAMES_PER_CELL


def test_the_grid_plan_carries_every_combination() -> None:
    """The grid plan holds 11 channels by 11 power values by 8 payload sizes."""
    plan = build_cell_plan(run_args(plan="grid"), seed=1)
    assert len(plan.cells) == EXPECTED_GRID_PLAN_CELL_COUNT


@pytest.mark.parametrize(
    ("limit", "expected"),
    [
        (EXPECTED_PAYLOAD_LIMIT_BYTES_V1, EXPECTED_PAYLOAD_BYTES_V1),
        (EXPECTED_PAYLOAD_LIMIT_BYTES_V2, EXPECTED_PAYLOAD_BYTES_V2),
    ],
)
def test_the_limit_selects_the_payload_sizes_of_its_list(
    limit: int, expected: tuple[int, ...]
) -> None:
    """Each payload limit sweeps the eight sizes that thinkbook section 8 lists."""
    plan = build_cell_plan(run_args(payload_limit_bytes=limit), seed=1)
    assert plan.payload_limit_bytes == limit
    text = format_plan(plan, "default", "broadcast")
    assert set(expected) <= payload_sizes_in(text)


def test_the_plan_states_the_seed_that_shuffled_it() -> None:
    """The plan carries the seed, so a reader can rebuild the cell order."""
    plan = build_cell_plan(run_args(), seed=FIXED_SEED)
    assert plan.seed == FIXED_SEED
    assert f"Shuffle seed: {FIXED_SEED}" in format_plan(plan, "default", "broadcast")


def test_generate_seed_stays_inside_its_width() -> None:
    """The generated seed fits the stated number of bits."""
    for _ in range(100):
        assert 0 <= generate_seed() < 2**EXPECTED_SEED_BITS


def test_the_run_command_accepts_no_seed_option() -> None:
    """The run command generates the seed, so it takes no seed from the user."""
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["run", *PORTS, "--seed", "1"])


def test_every_number_that_the_plan_header_states_carries_a_label() -> None:
    """A reader of the plan can tell the origin of each number it states."""
    plan = build_cell_plan(run_args(user_baseline=Baseline(6, 20, 500)), seed=1)
    text = format_plan(plan, "default", "broadcast")
    header, _, table = text.partition("Cells, in the order one pass visits them.")

    for line in header.splitlines():
        if any(character.isdigit() for character in line):
            assert "[configured]" in line, line

    # The cell table states its label once, for every number below it, rather
    # than three times on each of up to 968 lines.
    assert "[configured]" in table.splitlines()[0]


def test_the_plan_states_no_mac_address() -> None:
    """The output names no MAC address, which follows specification section 7."""
    plan = build_cell_plan(run_args(plan="grid"), seed=1)
    text = format_plan(plan, "grid", "broadcast")
    assert MAC_PATTERN.search(text) is None


def test_main_reports_version(capsys: pytest.CaptureFixture[str]) -> None:
    """Bolis --version prints the version and exits with status 0."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    assert "bolis" in capsys.readouterr().out


def test_main_lists_flash_and_run_in_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Bolis --help lists both subcommands."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "flash" in out
    assert "run" in out


def test_main_flash_reports_that_a_checkout_carries_no_image(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A checkout carries no manifest, so the command names that first."""
    status = main(["flash", *PORTS])
    assert status == 1
    err = capsys.readouterr().err
    assert "no prebuilt image" in err
    assert "a checkout does not" in err


def test_main_flash_reports_the_missing_transport_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """With a manifest present, the command names the chip and the real blocker.

    The check that proves what runs on a node reads a hello reply, and no
    transport reads one yet, so the command writes nothing rather than leaving
    a node in a state that no check confirmed.
    """
    manifest = {
        "manifest_version": 1,
        "images": [
            {
                "chip": "esp32",
                "file": "bolis-esp32.bin",
                "sha256": "ab" * 32,
                "elf_sha256": "cd" * 32,
                "bolis_version": "0.1.0",
            }
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(bolis.flasher, "FIRMWARE_DIRECTORY", tmp_path)

    status = main(["flash", *PORTS])
    assert status == 1
    err = capsys.readouterr().err
    assert "esp32" in err
    assert "wrote nothing" in err
    assert "transport" in err


def test_main_flash_refuses_a_url_port(capsys: pytest.CaptureFixture[str]) -> None:
    """A port that pyserial would read as a URL never reaches esptool."""
    status = main(["flash", "rfc2217://10.0.0.5:4000", PORTS[1]])
    assert status == 1
    assert "URL" in capsys.readouterr().err


def test_main_run_uses_the_fallback_baseline_when_no_option_is_given(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Bolis run with no option names the fallback channel, power, and payload."""
    status = main(["run", *PORTS])
    assert status == 1
    err = capsys.readouterr().err
    assert f"channel {EXPECTED_FALLBACK_CHANNEL}" in err
    assert f"power set value {EXPECTED_FALLBACK_POWER_SET_VALUE}" in err
    assert str(EXPECTED_FALLBACK_PAYLOAD_BYTES) in err
    assert "fallback" in err


def test_main_run_rejects_a_channel_outside_the_range(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Bolis run with an out-of-range channel exits non-zero and names the value."""
    status = main(["run", *PORTS, "--channel", "99"])
    assert status == 1
    assert "99" in capsys.readouterr().err


def test_main_run_rejects_a_payload_limit_outside_the_two_the_contract_names(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A limit that ESP-NOW does not define exits non-zero."""
    with pytest.raises(SystemExit):
        main(["run", *PORTS, "--limit", "999"])
    assert "999" in capsys.readouterr().err


def test_main_flash_rejects_two_equal_ports(capsys: pytest.CaptureFixture[str]) -> None:
    """Bolis flash with the same port twice exits non-zero and names the port."""
    status = main(["flash", "/dev/ttyUSB0", "/dev/ttyUSB0"])
    assert status == 1
    assert "ttyUSB0" in capsys.readouterr().err
