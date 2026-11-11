"""The bolis flash and bolis run commands.

The command surface follows specification section 5 and thinkbook section 6:
bolis flash <port> <port> writes the firmware image to both nodes, and bolis
run <port> <port> [options] sweeps the link and writes one report.

bolis run --print-plan resolves the baseline, builds the cell plan, prints it,
and returns 0 (decision 2026-11-10-run-plan-resolution.md). Without that flag,
bolis run builds the same plan and then reports the missing control line.

bolis flash validates its ports and reads the firmware manifest, then reports
the missing control line transport. It writes nothing to a node, because the
check that proves what runs on a node reads a hello reply over that transport
(decision 2026-11-10-firmware-image-carriage.md).
"""

import argparse
import random
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import cast

from bolis import BolisError, __version__
from bolis.sweep import (
    CHANNEL_MAX,
    CHANNEL_MIN,
    FALLBACK_CHANNEL,
    FALLBACK_PAYLOAD_BYTES,
    FALLBACK_POWER_SET_VALUE,
    PAYLOAD_LIMIT_BYTES_V1,
    PAYLOAD_LIMIT_BYTES_V2,
    PAYLOAD_MIN_BYTES,
    POWER_SET_VALUES,
    Baseline,
    CellPlan,
    build_grid_plan,
    build_plan,
)

MODE_CHOICES = ("broadcast", "unicast")
DEFAULT_MODE = "broadcast"

# The two plans of thinkbook section 8. The default plan varies one variable
# at a time; the grid plan visits every combination.
PLAN_CHOICES = ("default", "grid")
DEFAULT_PLAN = "default"

# The packet payload limit L that --limit selects (thinkbook section 8). The
# v2.0 limit is the default (decision 2026-11-10-run-plan-resolution.md).
PAYLOAD_LIMIT_CHOICES = (PAYLOAD_LIMIT_BYTES_V1, PAYLOAD_LIMIT_BYTES_V2)
DEFAULT_PAYLOAD_LIMIT_BYTES = PAYLOAD_LIMIT_BYTES_V2

# The width of the generated shuffle seed, in bits. The run command generates
# the seed and accepts no seed option, so one cell order never repeats across
# runs by accident (decision 2026-11-10-run-plan-resolution.md).
SEED_BITS = 32

# Every number that a plan states is [configured]: Bolis set it before the
# run, and no node measured it (decision 2026-10-01-number-origin-labels.md).
# A value computed from a [configured] input carries the label of that input,
# which covers the cell count and the frames per cell.
CONFIGURED = "[configured]"


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
    """The validated arguments of the run command.

    Attributes:
        sender_port: The serial port of the sender node.
        receiver_port: The serial port of the receiver node.
        user_baseline: The baseline that the user configured, or None when the
            user gave no channel, no transmit power, and no payload size.
        payload_limit_bytes: The packet payload limit L, 250 or 1470.
        plan: One of PLAN_CHOICES.
        mode: One of MODE_CHOICES.
        print_plan: Whether to print the plan and return 0.
    """

    sender_port: str
    receiver_port: str
    user_baseline: Baseline | None
    payload_limit_bytes: int
    plan: str
    mode: str
    print_plan: bool


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


def resolve_user_baseline(
    channel: int | None, power_set_value: int | None, payload_bytes: int | None
) -> Baseline | None:
    """Builds the baseline that the user configured, or None for the fallback.

    A baseline option that the user omits takes its fallback value. A plan
    carries the fallback baseline only when the user gives no channel, no
    transmit power, and no payload size (decision
    2026-11-10-run-plan-resolution.md). This function validates each value
    that the user typed and leaves a fallback value unchecked, because the
    fallback values of thinkbook section 8 are inside every range.

    Args:
        channel: The channel the user typed, or None.
        power_set_value: The transmit power set value the user typed, or None.
        payload_bytes: The payload size, in bytes, the user typed, or None.

    Returns:
        The baseline, with a fallback value in place of each omitted option,
        or None when the user omitted all three options.

    Raises:
        BolisValidationError: A value that the user typed sits outside its
            valid range.
    """
    if channel is None and power_set_value is None and payload_bytes is None:
        return None
    return Baseline(
        channel=FALLBACK_CHANNEL if channel is None else validate_channel(channel),
        power_set_value=(
            FALLBACK_POWER_SET_VALUE
            if power_set_value is None
            else validate_power_set_value(power_set_value)
        ),
        payload_bytes=(
            FALLBACK_PAYLOAD_BYTES
            if payload_bytes is None
            else validate_payload_bytes(payload_bytes)
        ),
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
    # Each baseline option defaults to None, not to its fallback value. The
    # plan carries the fallback baseline only when all three are absent, and a
    # fallback default would make a typed baseline and an absent baseline
    # arrive here as the same three integers.
    run_parser.add_argument(
        "--channel",
        type=int,
        default=None,
        help=(
            f"The baseline channel, {CHANNEL_MIN} to {CHANNEL_MAX}. "
            f"The fallback is {FALLBACK_CHANNEL}."
        ),
    )
    run_parser.add_argument(
        "--power",
        dest="power_set_value",
        type=int,
        default=None,
        help=(
            "The baseline transmit power set value. The fallback is "
            f"{FALLBACK_POWER_SET_VALUE}."
        ),
    )
    run_parser.add_argument(
        "--payload",
        dest="payload_bytes",
        type=int,
        default=None,
        help=(
            "The baseline payload size, in bytes. The fallback is "
            f"{FALLBACK_PAYLOAD_BYTES}."
        ),
    )
    run_parser.add_argument(
        "--limit",
        dest="payload_limit_bytes",
        type=int,
        choices=PAYLOAD_LIMIT_CHOICES,
        default=DEFAULT_PAYLOAD_LIMIT_BYTES,
        help=(
            "The packet payload limit L, in bytes. The default is "
            f"{DEFAULT_PAYLOAD_LIMIT_BYTES}."
        ),
    )
    run_parser.add_argument(
        "--plan",
        choices=PLAN_CHOICES,
        default=DEFAULT_PLAN,
        help=(
            "Visit every combination with grid. The default varies one "
            "variable at a time."
        ),
    )
    run_parser.add_argument(
        "--mode",
        choices=MODE_CHOICES,
        default=DEFAULT_MODE,
        help="Add the unicast pass with unicast. The default is broadcast.",
    )
    run_parser.add_argument(
        "--print-plan",
        dest="print_plan",
        action="store_true",
        help="Print the resolved cell plan and exit without touching a node.",
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
    user_baseline = resolve_user_baseline(
        cast("int | None", parsed.channel),
        cast("int | None", parsed.power_set_value),
        cast("int | None", parsed.payload_bytes),
    )
    return RunArgs(
        sender_port=sender_port,
        receiver_port=receiver_port,
        user_baseline=user_baseline,
        payload_limit_bytes=cast(int, parsed.payload_limit_bytes),
        plan=cast(str, parsed.plan),
        mode=cast(str, parsed.mode),
        print_plan=cast(bool, parsed.print_plan),
    )


def generate_seed() -> int:
    """Generates the shuffle seed of one run.

    The run command generates the seed and accepts no seed option (decision
    2026-11-10-run-plan-resolution.md).

    Returns:
        A seed of SEED_BITS bits.
    """
    # The seed makes the cell order of one run reproducible from its record.
    # It is not a secret, so Bandit's S311 does not apply (coding-standard.md).
    # getrandbits does not raise S311, so this line carries no suppression,
    # unlike the shuffle in bolis.sweep.
    return random.getrandbits(SEED_BITS)


def build_cell_plan(args: RunArgs, seed: int) -> CellPlan:
    """Builds the cell plan that the run arguments select.

    Args:
        args: The validated arguments of the run command.
        seed: The seed that shuffles the cell order.

    Returns:
        The cell plan of the selected plan kind.

    Raises:
        BolisSweepError: The baseline or the payload limit sits outside the
            range that the sweep covers.
    """
    builder = build_grid_plan if args.plan == "grid" else build_plan
    return builder(args.user_baseline, args.payload_limit_bytes, seed)


def format_plan(plan: CellPlan, plan_name: str, mode: str) -> str:
    """Formats a cell plan as the text that --print-plan writes.

    Every number carries the label `[configured]`. The output states no MAC
    address, which follows specification section 7. It is not the report:
    specification section 6 governs the report, and this text carries no
    chart, no interval, and no link to a run record.

    Args:
        plan: The cell plan to format.
        plan_name: One of PLAN_CHOICES, which names the plan kind.
        mode: One of MODE_CHOICES, which names the send mode of the run.

    Returns:
        The plan as text, with one line per cell and no trailing newline.
    """
    baseline_source = "fallback" if plan.is_fallback_baseline else "user"
    lines = [
        "bolis run plan",
        "",
        f"Plan: {plan_name}",
        f"Mode: {mode}",
        f"Baseline source: {baseline_source}",
        f"Baseline channel: {plan.baseline.channel} {CONFIGURED}",
        f"Baseline power set value: {plan.baseline.power_set_value} {CONFIGURED}",
        f"Baseline payload: {plan.baseline.payload_bytes} bytes {CONFIGURED}",
        f"Payload limit: {plan.payload_limit_bytes} bytes {CONFIGURED}",
        f"Shuffle seed: {plan.seed} {CONFIGURED}",
        f"Frames per cell: {plan.frames_per_cell} {CONFIGURED}",
        f"Cells: {len(plan.cells)} {CONFIGURED}",
        "",
        (
            "Cells, in the order one pass visits them. Every number below is "
            f"{CONFIGURED}."
        ),
        "",
    ]
    lines.extend(
        f"{index:>5}  channel {cell.channel:>2}  "
        f"power {cell.power_set_value:>2}  "
        f"payload {cell.payload_bytes:>4} bytes  {cell.variable.value}"
        for index, cell in enumerate(plan.cells, start=1)
    )
    return "\n".join(lines)


def summarize_plan(plan: CellPlan, plan_name: str) -> str:
    """States a cell plan in one sentence, for a message that carries no table.

    Args:
        plan: The cell plan to summarize.
        plan_name: One of PLAN_CHOICES, which names the plan kind.

    Returns:
        The summary, with a label on every number.
    """
    baseline_source = "the fallback" if plan.is_fallback_baseline else "the configured"
    return (
        f"The {plan_name} plan holds {len(plan.cells)} cells {CONFIGURED} around "
        f"{baseline_source} baseline of channel {plan.baseline.channel} "
        f"{CONFIGURED}, power set value {plan.baseline.power_set_value} "
        f"{CONFIGURED}, and payload {plan.baseline.payload_bytes} bytes "
        f"{CONFIGURED}, with seed {plan.seed} {CONFIGURED} and "
        f"{plan.frames_per_cell} frames per cell {CONFIGURED}."
    )


def _run_flash(parsed: argparse.Namespace) -> int:
    args = _parse_flash_args(parsed)
    # The flasher imports esptool, which costs more to import than the rest of
    # this package. The run command needs neither, so the import sits here
    # rather than at the top of the file.
    from bolis.flasher import read_manifest, validate_local_port  # noqa: PLC0415

    validate_local_port(args.sender_port)
    validate_local_port(args.receiver_port)

    # The carriage record makes the hello reply after a write the one check
    # that proves what runs on a node, and no transport reads that reply yet.
    # Writing an image that nothing then confirms would leave a node in a
    # state no record states, so this command writes nothing. Reading the
    # manifest is the part of the flash that needs no node, and it reports
    # whether this package carries an image at all.
    manifest = read_manifest()
    carried = ", ".join(sorted(manifest))
    raise BolisNotImplementedError(
        f"bolis flash is not implemented yet. This package carries an image "
        f"for: {carried}. The flasher writes an image through the esptool "
        "Python API, then reads the hello reply of a node to prove what runs "
        "on it. No control line transport reads that reply yet, so this "
        f"command wrote nothing to {args.sender_port} or {args.receiver_port}."
    )


def _run_run(parsed: argparse.Namespace) -> int:
    args = _parse_run_args(parsed)
    plan = build_cell_plan(args, generate_seed())
    if args.print_plan:
        print(format_plan(plan, args.plan, args.mode))
        return 0
    summary = summarize_plan(plan, args.plan)
    raise BolisNotImplementedError(
        "bolis run is not implemented yet. It will sweep the link between "
        f"{args.sender_port} and {args.receiver_port} in {args.mode} mode once "
        f"the host reaches a node over the control line. {summary}"
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
