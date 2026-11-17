"""The bolis flash and bolis run commands.

The command surface follows specification section 5 and thinkbook section 6:
bolis flash <port> <port> writes the firmware image to both nodes, and bolis
run <port> <port> [options] sweeps the link and writes one report.

bolis run --print-plan resolves the baseline, builds the cell plan, prints it,
and returns 0 (decision 2026-11-10-run-plan-resolution.md). Without that flag,
bolis run builds the same plan, gives each node its role, runs every cell, and
writes one run record and one report into the directory that --out names. A run
that loses a node keeps the cells that ran and states why it stopped.

bolis flash writes the image to both nodes through the esptool Python API,
then reads the hello reply of each node over the control line transport. That
reply is the check that proves what runs on a node
(decision 2026-11-10-firmware-image-carriage.md).
"""

import argparse
import random
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from bolis import BolisError, __version__
from bolis.protocol import Hello, parse_hello, require_same_firmware
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
    Cell,
    CellPlan,
    build_grid_plan,
    build_plan,
)

MODE_CHOICES = ("broadcast", "unicast")
DEFAULT_MODE = "broadcast"

# The five entries of the declared section of thinkbook section 9, in the
# order the record states them. The schema requires every key and accepts
# empty text, so a user who declares nothing still writes a valid record. A
# verification pair needs the geometry, so the run prints a note when the
# whole section is empty (decision 2026-10-01-reproducibility-verification.md).
DECLARED_KEYS = ("distance", "orientation", "antenna", "enclosure", "surroundings")

# The power-save mode of both nodes. The component always disables power save,
# because a node in modem sleep does not receive ESP-NOW data (thinkbook
# section 4), so the host states the value rather than asking a node for it.
POWER_SAVE = "none"

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

# A value that a node counted or read during the run carries this label
# (decision 2026-10-01-number-origin-labels.md).
MEASURED = "[measured]"


class BolisValidationError(BolisError):
    """Raised when a value that the user typed fails validation."""


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
        out: The directory that the host writes the run record and the report
            into.
        declared_text: The five entries of the declared section, by key. Bolis
            checks none of them.
    """

    sender_port: str
    receiver_port: str
    user_baseline: Baseline | None
    payload_limit_bytes: int
    plan: str
    mode: str
    print_plan: bool
    out: Path
    declared_text: Mapping[str, str]


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
    run_parser.add_argument(
        "--out",
        default=None,
        help=(
            "The directory that the run record goes into. The default is the "
            "working directory."
        ),
    )
    for key in DECLARED_KEYS:
        run_parser.add_argument(
            f"--{key}",
            default="",
            help=(
                f"The {key} of the bench, as you describe it. Bolis does not "
                "check it, and the record states it as declared."
            ),
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
    out = cast("str | None", parsed.out)
    return RunArgs(
        sender_port=sender_port,
        receiver_port=receiver_port,
        user_baseline=user_baseline,
        payload_limit_bytes=cast(int, parsed.payload_limit_bytes),
        plan=cast(str, parsed.plan),
        mode=cast(str, parsed.mode),
        print_plan=cast(bool, parsed.print_plan),
        # The host writes into the working directory when the user gives no
        # --out (decision 2026-11-12-run-record-format.md).
        out=Path.cwd() if out is None else Path(out),
        declared_text={key: cast(str, getattr(parsed, key)) for key in DECLARED_KEYS},
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


def format_node(role: str, port: str, hello: Hello) -> str:
    """States the condition that one node reported in its hello reply.

    Every value here is `[measured]`: a node read it and reported it
    (decision 2026-10-01-number-origin-labels.md).

    Args:
        role: The role that the node takes, sender or receiver.
        port: The serial port of the node.
        hello: The test condition that the node reported.

    Returns:
        One line per node.
    """
    return (
        f"{role} on {port}: {hello.chip} revision {hello.chip_revision} "
        f"{MEASURED}, ESP-IDF {hello.idf_version} {MEASURED}, ESP-NOW version "
        f"{hello.espnow_version} {MEASURED}, payload limit "
        f"{hello.payload_limit_bytes} bytes {MEASURED}, Bolis "
        f"{hello.bolis_version} {MEASURED}, {hello.firmware_path} firmware, "
        f"Bluetooth controller {hello.bluetooth_controller}."
    )


def _run_flash(parsed: argparse.Namespace) -> int:
    args = _parse_flash_args(parsed)
    # The flasher imports esptool, which costs more to import than the rest of
    # this package. The run command needs neither, so the import sits here
    # rather than at the top of the file.
    from bolis import transport  # noqa: PLC0415
    from bolis.flasher import flash_pair  # noqa: PLC0415

    sender, receiver = flash_pair(
        args.sender_port, args.receiver_port, transport.read_hello_line
    )
    print(format_node("sender", args.sender_port, sender))
    print(format_node("receiver", args.receiver_port, receiver))
    print("Both nodes run the image that this package carries.")
    return 0


def utc_now() -> str:
    """Returns the present instant in the form that a run record states.

    Returns:
        The instant in UTC, in RFC 3339 form with a Z suffix and whole
        seconds.
    """
    stamp = datetime.now(tz=timezone.utc).replace(microsecond=0)
    return stamp.isoformat().replace("+00:00", "Z")


def condition_of(cell: Cell, plan: CellPlan) -> dict[str, int]:
    """Builds the condition that one cell of a plan sends.

    Args:
        cell: The cell of the plan.
        plan: The plan that holds the frame budget of every cell.

    Returns:
        The channel, the transmit power, the payload size, and the frames.
    """
    return {
        "channel": cell.channel,
        "power_set_value": cell.power_set_value,
        "payload_bytes": cell.payload_bytes,
        "frames": plan.frames_per_cell,
    }


def _sweep(
    runner: Any,  # noqa: ANN401
    plan: CellPlan,
    mode: str,
) -> tuple[list[Any], str | None]:
    """Runs every cell of a plan and reports why the run stopped.

    A run that loses a node keeps the cells that ran, because the record of a
    partial run still states what the bench measured
    (decision 2026-11-12-serial-transport-reply-timeouts.md).

    Args:
        runner: The orchestrator of this run.
        plan: The cells to run, in the order the plan states.
        mode: The run mode, broadcast or unicast.

    Returns:
        The entries of every cell that ran, and the reason the run stopped, or
        None when the run reached the end of its plan.
    """
    entries: list[Any] = []
    for cell_id, cell in enumerate(plan.cells):
        try:
            entries.append(runner.run_cell(cell_id, condition_of(cell, plan), mode))
        except BolisError as error:
            return entries, f"cell {cell_id} stopped the run: {error}"
    return entries, None


def _run_run(parsed: argparse.Namespace) -> int:
    args = _parse_run_args(parsed)
    plan = build_cell_plan(args, generate_seed())
    if args.print_plan:
        print(format_plan(plan, args.plan, args.mode))
        return 0

    # These modules land here rather than at the top, because --print-plan
    # touches no port and the transport imports pyserial.
    from bolis import transport  # noqa: PLC0415
    from bolis.orchestrator import (  # noqa: PLC0415
        Bench,
        Orchestrator,
        build_cells,
        build_declared,
        build_firmware,
        build_nodes,
        build_run,
        build_setup,
    )
    from bolis.record import (  # noqa: PLC0415
        draw_run_id,
        prepare_directory,
        write_record,
    )
    from bolis.report import write_report  # noqa: PLC0415

    # A run that the host cannot record is a run that wasted a bench, so the
    # directory is checked before the first cell
    # (decision 2026-11-12-run-record-format.md).
    prepare_directory(args.out)
    run_id = draw_run_id(args.out)

    sender_port = transport.open_serial_port(args.sender_port)
    try:
        receiver_port = transport.open_serial_port(args.receiver_port)
        try:
            sender_line = transport.Transport(sender_port)
            receiver_line = transport.Transport(receiver_port)
            sender = parse_hello(sender_line.command("hello"))
            receiver = parse_hello(receiver_line.command("hello"))
            require_same_firmware(sender, receiver)
            print(format_node("sender", args.sender_port, sender))
            print(format_node("receiver", args.receiver_port, receiver))
            print(summarize_plan(plan, args.plan))

            started_at = utc_now()
            runner = Orchestrator(sender_line, receiver_line)
            runner.assign_roles(run_id)
            entries, stopped_reason = _sweep(runner, plan, args.mode)
            ended_at = utc_now()
        finally:
            receiver_port.close()
    finally:
        sender_port.close()

    bench = Bench(
        country_code=sender.country_code,
        power_save=POWER_SAVE,
        declared_text=args.declared_text,
    )
    document = {
        "run": build_run(
            run_id,
            started_at=started_at,
            ended_at=ended_at,
            bolis_version=sender.bolis_version,
            mode=args.mode,
            plan_name=args.plan,
            seed=plan.seed,
            stopped_reason=stopped_reason,
        ),
        "firmware": build_firmware(sender),
        "nodes": build_nodes(sender, receiver),
        "setup": build_setup(plan, bench, sender.bluetooth_controller),
        "declared": build_declared(bench),
        "cells": build_cells(entries),
    }
    path = write_record(document, args.out)
    # The report reads the record that the host just wrote, so a reader of one
    # holds the other beside it.
    report = write_report(document, args.out)

    print(f"bolis wrote the run record {path}")
    print(f"bolis wrote the report {report}")
    if not any(args.declared_text.values()):
        print(
            "The declared section is empty. A verification pair needs the "
            "geometry of the bench, so state it with --distance and the "
            "options beside it."
        )
    if stopped_reason is not None:
        print(f"The run stopped early. {stopped_reason}", file=sys.stderr)
        return 1
    return 0


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
