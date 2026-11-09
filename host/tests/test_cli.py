"""Tests for the bolis command line interface."""

import pytest

from bolis.cli import (
    CHANNEL_MAX,
    CHANNEL_MIN,
    PAYLOAD_MIN_BYTES,
    POWER_SET_VALUES,
    BolisValidationError,
    main,
    validate_channel,
    validate_distinct_ports,
    validate_payload_bytes,
    validate_power_set_value,
)


def test_validate_channel_accepts_the_range_boundaries() -> None:
    """A channel at the minimum or the maximum passes unchanged."""
    assert validate_channel(CHANNEL_MIN) == CHANNEL_MIN
    assert validate_channel(CHANNEL_MAX) == CHANNEL_MAX


def test_validate_channel_rejects_a_channel_outside_the_range() -> None:
    """A channel outside the range raises, and the message names the value."""
    with pytest.raises(BolisValidationError, match="99"):
        validate_channel(99)


def test_validate_power_set_value_accepts_every_quantized_value() -> None:
    """Each of the eleven quantized power values passes unchanged."""
    for value in POWER_SET_VALUES:
        assert validate_power_set_value(value) == value


def test_validate_power_set_value_rejects_a_value_outside_the_set() -> None:
    """A power value that the radio does not quantize to raises."""
    with pytest.raises(BolisValidationError, match="13"):
        validate_power_set_value(13)


def test_validate_payload_bytes_accepts_the_minimum() -> None:
    """A payload at the 14-byte header minimum passes unchanged."""
    assert validate_payload_bytes(PAYLOAD_MIN_BYTES) == PAYLOAD_MIN_BYTES


def test_validate_payload_bytes_rejects_a_payload_smaller_than_the_header() -> None:
    """A payload smaller than the header raises, and the message names the value."""
    with pytest.raises(BolisValidationError, match="13"):
        validate_payload_bytes(13)


def test_validate_distinct_ports_rejects_two_equal_ports() -> None:
    """Two equal ports raise, because Bolis needs one port per node."""
    with pytest.raises(BolisValidationError, match="ttyUSB0"):
        validate_distinct_ports("/dev/ttyUSB0", "/dev/ttyUSB0")


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


def test_main_flash_is_not_implemented(capsys: pytest.CaptureFixture[str]) -> None:
    """Bolis flash validates its ports, then reports that it is not implemented yet."""
    status = main(["flash", "/dev/ttyUSB0", "/dev/ttyUSB1"])
    assert status == 1
    assert "not implemented" in capsys.readouterr().err


def test_main_run_uses_the_fallback_baseline_when_no_option_is_given(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Bolis run with no option names the fallback channel, power, and payload."""
    status = main(["run", "/dev/ttyUSB0", "/dev/ttyUSB1"])
    assert status == 1
    err = capsys.readouterr().err
    assert "channel 1" in err
    assert "power set value 44" in err
    assert "128" in err


def test_main_run_rejects_a_channel_outside_the_range(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Bolis run with an out-of-range channel exits non-zero and names the value."""
    status = main(["run", "/dev/ttyUSB0", "/dev/ttyUSB1", "--channel", "99"])
    assert status == 1
    assert "99" in capsys.readouterr().err


def test_main_flash_rejects_two_equal_ports(capsys: pytest.CaptureFixture[str]) -> None:
    """Bolis flash with the same port twice exits non-zero and names the port."""
    status = main(["flash", "/dev/ttyUSB0", "/dev/ttyUSB0"])
    assert status == 1
    assert "ttyUSB0" in capsys.readouterr().err
