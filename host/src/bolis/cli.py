"""The bolis flash and bolis run commands.

The command surface follows specification section 5 and thinkbook section 6:
bolis flash <port> <port> writes the firmware image to both nodes, and bolis
run <port> <port> [options] sweeps the link and writes one report. Neither
command is implemented yet. Each one validates its arguments, then raises
BolisNotImplementedError.
"""

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import cast

from bolis import BolisError, __version__

# The 11 transmit power set values, which quantize to 2 to 20 dBm (thinkbook
# section 4). The value is what the user types and what crosses the control
# line. The dBm figure is a label on the set, not a separate input.
POWER_SET_VALUES = (8, 20, 28, 34, 44, 52, 56, 60, 66, 72, 80)

# The channel range that the default country code "01" allows (thinkbook
# section 4). Bolis v0 exposes no country code option, so this range is fixed.
CHANNEL_MIN = 1
CHANNEL_MAX = 11

# The data frame header is 14 bytes (control line wire format record), so a
# payload below that could never form one packet.
PAYLOAD_MIN_BYTES = 14

MODE_CHOICES = ("broadcast", "unicast")
DEFAULT_MODE = "broadcast"

# The fallback baseline when the user gives no channel, power, or payload
# (thinkbook section 8): channel 1, power set value 44 (11 dBm), payload 128
# bytes.
FALLBACK_CHANNEL = 1
FALLBACK_POWER_SET_VALUE = 44
FALLBACK_PAYLOAD_BYTES = 128


class BolisValidationError(BolisError):
    """Raised when a value that the user typed fails validation."""


class BolisNotImplementedError(BolisError):
    """Raised by a command whose implementation has not arrived yet."""


@dataclass(frozen=True)
class FlashArgs:
    """The validated arguments of the flash command."""

    sender_port: str
    receiver_port: str


@dataclass(frozen=True)
class RunArgs:
    """The validated arguments of the run command."""

    sender_port: str
    receiver_port: str
    channel: int
    power_set_value: int
    payload_bytes: int
    mode: str


def validate_channel(value: int) -> int:
    """Checks that a channel falls inside the range the default country code allows.

    Args:
        value: The channel number that the user typed.

    Returns:
        The same channel number, unchanged.

    Raises:
        BolisValidationError: The value sits outside the range CHANNEL_MIN to
            CHANNEL_MAX.
    """
    if not (CHANNEL_MIN <= value <= CHANNEL_MAX):
        raise BolisValidationError(
            f"the channel is {value}. The default country code allows "
            f"{CHANNEL_MIN} to {CHANNEL_MAX}."
        )
    return value


def validate_power_set_value(value: int) -> int:
    """Checks that a transmit power value matches one of the quantized set values.

    Args:
        value: The power set value that the user typed.

    Returns:
        The same power set value, unchanged.

    Raises:
        BolisValidationError: The value is not a member of POWER_SET_VALUES.
    """
    if value not in POWER_SET_VALUES:
        allowed = ", ".join(str(set_value) for set_value in POWER_SET_VALUES)
        raise BolisValidationError(
            f"the power set value is {value}. The radio quantizes to one of: {allowed}."
        )
    return value


def validate_payload_bytes(value: int) -> int:
    """Checks that a payload size meets the minimum the data frame header needs.

    Args:
        value: The payload size, in bytes, that the user typed.

    Returns:
        The same payload size, in bytes, unchanged.

    Raises:
        BolisValidationError: The value is below PAYLOAD_MIN_BYTES.
    """
    if value < PAYLOAD_MIN_BYTES:
        raise BolisValidationError(
            f"the payload is {value} bytes. The data frame header needs "
            f"{PAYLOAD_MIN_BYTES} bytes, so the payload cannot be smaller."
        )
    return value


def validate_distinct_ports(sender_port: str, receiver_port: str) -> None:
    """Checks that the sender port and the receiver port name two different devices.

    Args:
        sender_port: The serial port of the sender node.
        receiver_port: The serial port of the receiver node.

    Raises:
        BolisValidationError: The two ports are equal.
    """
    if sender_port == receiver_port:
        raise BolisValidationError(
            f"the sender port and the receiver port are both {sender_port!r}. "
            "Bolis needs two distinct ports, one per node."
        )


def build_parser() -> argparse.ArgumentParser:
    """Builds the argument parser for the bolis command line.

    Returns:
        A parser with the flash and run subcommands attached.
    """
    parser = argparse.ArgumentParser(
        prog="bolis", description="A bench tool for ESP-NOW."
    )
    parser.add_argument("--version", action="version", version=f"bolis {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    flash_parser = subparsers.add_parser(
        "flash", help="Write the firmware image to both nodes."
    )
    flash_parser.add_argument("sender_port", help="The serial port of the sender node.")
    flash_parser.add_argument(
        "receiver_port", help="The serial port of the receiver node."
    )

    run_parser = subparsers.add_parser(
        "run", help="Sweep the link and write one report."
    )
    run_parser.add_argument("sender_port", help="The serial port of the sender node.")
    run_parser.add_argument(
        "receiver_port", help="The serial port of the receiver node."
    )
    run_parser.add_argument(
        "--channel",
        type=int,
        default=FALLBACK_CHANNEL,
        help=f"The baseline channel, {CHANNEL_MIN} to {CHANNEL_MAX}.",
    )
    run_parser.add_argument(
        "--power",
        dest="power_set_value",
        type=int,
        default=FALLBACK_POWER_SET_VALUE,
        help="The baseline transmit power set value.",
    )
    run_parser.add_argument(
        "--payload",
        dest="payload_bytes",
        type=int,
        default=FALLBACK_PAYLOAD_BYTES,
        help="The baseline payload size, in bytes.",
    )
    run_parser.add_argument(
        "--mode",
        choices=MODE_CHOICES,
        default=DEFAULT_MODE,
        help="Add the unicast pass with unicast. The default is broadcast.",
    )

    return parser


def _parse_flash_args(parsed: argparse.Namespace) -> FlashArgs:
    sender_port = cast(str, parsed.sender_port)
    receiver_port = cast(str, parsed.receiver_port)
    validate_distinct_ports(sender_port, receiver_port)
    return FlashArgs(sender_port=sender_port, receiver_port=receiver_port)


def _parse_run_args(parsed: argparse.Namespace) -> RunArgs:
    sender_port = cast(str, parsed.sender_port)
    receiver_port = cast(str, parsed.receiver_port)
    validate_distinct_ports(sender_port, receiver_port)
    channel = validate_channel(cast(int, parsed.channel))
    power_set_value = validate_power_set_value(cast(int, parsed.power_set_value))
    payload_bytes = validate_payload_bytes(cast(int, parsed.payload_bytes))
    return RunArgs(
        sender_port=sender_port,
        receiver_port=receiver_port,
        channel=channel,
        power_set_value=power_set_value,
        payload_bytes=payload_bytes,
        mode=cast(str, parsed.mode),
    )


def _run_flash(parsed: argparse.Namespace) -> int:
    args = _parse_flash_args(parsed)
    raise BolisNotImplementedError(
        f"bolis flash is not implemented yet. It will flash {args.sender_port} "
        f"and {args.receiver_port} through the esptool Python API."
    )


def _run_run(parsed: argparse.Namespace) -> int:
    args = _parse_run_args(parsed)
    raise BolisNotImplementedError(
        "bolis run is not implemented yet. It will sweep the link between "
        f"{args.sender_port} and {args.receiver_port} from channel {args.channel}, "
        f"power set value {args.power_set_value}, and payload {args.payload_bytes} "
        f"bytes, in {args.mode} mode."
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Parses the command line, runs the chosen command, and returns the exit status.

    Args:
        argv: The argument vector to parse. None reads sys.argv.

    Returns:
        0 on success. A non-zero status when validation fails or the chosen
        command is not implemented yet.
    """
    parser = build_parser()
    parsed = parser.parse_args(argv)
    handlers: dict[str, Callable[[argparse.Namespace], int]] = {
        "flash": _run_flash,
        "run": _run_run,
    }
    try:
        return handlers[parsed.command](parsed)
    # The CLI entry point is the one place that catches a broad exception, so a
    # user sees one message instead of a traceback (coding-standard.md).
    except Exception as error:  # noqa: BLE001
        print(f"bolis: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
