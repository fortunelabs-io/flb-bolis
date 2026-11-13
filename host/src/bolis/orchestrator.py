"""The orchestrator of one run.

Drives the control protocol over two transports and builds the run record
document that `bolis.record` writes. Thinkbook section 7 states the order:
the host sets the receiver first, so it listens on the new channel before the
first frame leaves the sender, and a settle time after the pass catches late
frames before the receiver reports.

The host sends `role` to the receiver before the sender, because the MAC
address of the receiver reaches the sender as `peer_mac`
(record docs/adr/2026-11-11-control-line-command-fields.md). That address
stays in memory. No message, log, or record of this module states it
(specification section 7).

A node that resets, or a pass that falls silent, invalidates the attempt. The
host applies the role and the cell again and runs that cell once more
(thinkbook section 11). A command that draws no reply inside its retry budget
stops the run, and the host keeps the record of the cells that ran.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from bolis import BolisError
from bolis.protocol import Hello
from bolis.record import (
    configured,
    configured_list,
    declared,
    loss_quantity,
    measured,
    measured_list,
)
from bolis.sweep import CellPlan, payload_bytes_for_limit
from bolis.transport import (
    BolisNodeResetError,
    BolisPassSilentError,
    Transport,
)

# The pause between the reply that ends a pass and the stats command that
# follows it, in seconds. Thinkbook section 7 states that a settle time
# catches late frames before the receiver reports, and it states no value.
SETTLE_S: Final = 0.5  # [proposal]

# One attempt of a cell, and one rerun of an attempt that the run
# invalidated (thinkbook section 11).
CELL_ATTEMPTS: Final = 2

# The two passes, in the order that a unicast run sends them (decision
# 2026-10-01-loss-metric-and-send-mode.md).
BROADCAST: Final = "broadcast"
UNICAST: Final = "unicast"

# The counters that a sender states in its stats reply, and that the record
# holds under the same names.
SENDER_COUNTERS: Final = (
    "messages_sent",
    "packets_sent",
    "callback_ok",
    "callback_failed",
    "no_mem_events",
    "rejected_lines",
)

# The counters that a receiver states in its stats reply. dropped_packets
# states the packets that the node itself did not process, which record
# docs/adr/2026-11-13-the-receiving-loop-of-a-pass.md separates from a frame
# that the link lost.
RECEIVER_COUNTERS: Final = (
    "packets_received",
    "duplicates",
    "foreign_packets",
    "messages_complete",
    "messages_incomplete",
    "corrupt_packets",
    "dropped_packets",
    "rejected_lines",
)

# The counters of a receiver that hold a value rather than a count.
RECEIVER_LEVELS: Final = ("rssi_min_dbm", "rssi_mean_dbm", "rssi_max_dbm")


class BolisRunError(BolisError):
    """Raised when a run cannot continue and the host keeps a partial record."""


@dataclass(frozen=True)
class Bench:
    """What the user declared about the bench, and what Bolis set on it.

    Attributes:
        country_code: The country setting of the radio.
        power_save: The power-save mode that the component applied.
        declared_text: The five entries of the declared section of thinkbook
            section 9, by key. Bolis checks none of them.
    """

    country_code: str
    power_save: str
    declared_text: Mapping[str, str]


def _sleep(seconds: float) -> None:
    """Waits for the settle time of thinkbook section 7.

    Args:
        seconds: The time to wait.
    """
    # time.sleep loads here rather than at the top of the module, so a test
    # case replaces this one function and waits for nothing.
    import time  # noqa: PLC0415

    time.sleep(seconds)


class Orchestrator:
    """Runs one plan over a pair of nodes and builds its record."""

    def __init__(
        self,
        sender: Transport,
        receiver: Transport,
        sleep: Callable[[float], None] = _sleep,
        settle_s: float = SETTLE_S,
    ) -> None:
        """Binds the orchestrator to one pair of nodes.

        Args:
            sender: The transport of the node that takes the sender role.
            receiver: The transport of the node that takes the receiver role.
            sleep: The waiter of the settle time, which takes seconds.
            settle_s: The settle time after a pass, in seconds.
        """
        self._sender = sender
        self._receiver = receiver
        self._sleep = sleep
        self._settle_s = settle_s

    def assign_roles(self, run_id: int) -> None:
        """Gives each node its role and the run ID that it stamps on a frame.

        The receiver answers first, and its MAC address reaches the sender as
        `peer_mac`. That address stays in memory.

        Args:
            run_id: The run ID of this run, 0 to 4294967295.

        Raises:
            BolisRunError: A node stated no MAC address in its role reply.
        """
        reply = self._receiver.command("role", {"role": "receiver", "run_id": run_id})
        peer_mac = reply.fields.get("mac")
        if not isinstance(peer_mac, str):
            raise BolisRunError("the receiver stated no MAC address in its role reply.")
        self._sender.command(
            "role", {"role": "sender", "run_id": run_id, "peer_mac": peer_mac}
        )

    def run_cell(
        self, cell_id: int, condition: Mapping[str, int], mode: str
    ) -> list[dict[str, Any]]:
        """Runs one cell and returns one entry per pass of it.

        Args:
            cell_id: The cell, 0 to 32767.
            condition: The channel, the power set value, the payload size,
                and the frames of this cell.
            mode: The run mode, broadcast or unicast.

        Returns:
            One entry per pass, in the order that the passes ran.
        """
        passes = [BROADCAST] if mode == BROADCAST else [BROADCAST, UNICAST]
        entries: list[dict[str, Any]] = []
        for name in passes:
            entries.append(self._attempt_pass(cell_id, condition, name))
        return entries

    def _attempt_pass(
        self, cell_id: int, condition: Mapping[str, int], name: str
    ) -> dict[str, Any]:
        """Runs one pass, and runs it again once when the run invalidates it.

        Args:
            cell_id: The cell, 0 to 32767.
            condition: The condition of this cell.
            name: The pass, broadcast or unicast.

        Returns:
            The entry of the attempt that stands.
        """
        entry: dict[str, Any] = {}
        for attempt in range(CELL_ATTEMPTS):
            try:
                return self._one_pass(cell_id, condition, name)
            except (BolisNodeResetError, BolisPassSilentError) as error:
                entry = self._invalid_entry(cell_id, condition, name, str(error))
                if attempt + 1 == CELL_ATTEMPTS:
                    return entry
        return entry

    def _one_pass(
        self, cell_id: int, condition: Mapping[str, int], name: str
    ) -> dict[str, Any]:
        """Applies the condition, runs the pass, and reads both counter sets.

        Args:
            cell_id: The cell, 0 to 32767.
            condition: The condition of this cell.
            name: The pass, broadcast or unicast.

        Returns:
            The entry of this pass.
        """
        applied = {
            "cell_id": cell_id,
            "channel": condition["channel"],
            "power_set_value": condition["power_set_value"],
            "payload_bytes": condition["payload_bytes"],
        }
        # The receiver listens on the new channel before the first frame
        # leaves the sender (thinkbook section 7).
        read_back = self._receiver.command("cell", applied)
        self._sender.command("cell", applied)

        done = self._sender.run_pass(
            {"cell_id": cell_id, "pass": name, "frames": condition["frames"]}
        )
        self._sleep(self._settle_s)

        query = {"cell_id": cell_id, "pass": name}
        receiver_stats = self._receiver.command("stats", query)
        sender_stats = self._sender.command("stats", query)

        return self._build_entry(
            cell_id,
            condition,
            name,
            read_back=read_back.fields,
            done=done.fields,
            sender=sender_stats.fields,
            receiver=receiver_stats.fields,
        )

    def _invalid_entry(
        self, cell_id: int, condition: Mapping[str, int], name: str, reason: str
    ) -> dict[str, Any]:
        """Builds the entry of an attempt that the run invalidated.

        Such an attempt states no loss quantity, and it states the counters of
        a node only when that node answered its stats command. This attempt
        answered none, so it states neither.

        Args:
            cell_id: The cell, 0 to 32767.
            condition: The condition of this cell.
            name: The pass, broadcast or unicast.
            reason: What invalidated the attempt.

        Returns:
            The entry of the invalidated attempt.
        """
        return {
            "cell_id": cell_id,
            "pass": name,
            "valid": False,
            "invalid_reason": reason,
            "condition": _condition_section(condition),
            "read_back": _unknown_read_back(condition),
        }

    # The seven arguments are the cell, its condition, its pass, and the
    # fields of the four replies that one pass produces. A type that bundled
    # the replies would name a bag that no other function takes.
    def _build_entry(  # noqa: PLR0913
        self,
        cell_id: int,
        condition: Mapping[str, int],
        name: str,
        *,
        read_back: Mapping[str, Any],
        done: Mapping[str, Any],
        sender: Mapping[str, Any],
        receiver: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Builds the entry of a pass that ran to its end.

        Args:
            cell_id: The cell, 0 to 32767.
            condition: The condition that the host asked for.
            name: The pass, broadcast or unicast.
            read_back: The fields of the cell reply of the receiver.
            done: The fields of the go reply that stated done.
            sender: The fields of the stats reply of the sender.
            receiver: The fields of the stats reply of the receiver.

        Returns:
            The entry of this pass.
        """
        entry: dict[str, Any] = {
            "cell_id": cell_id,
            "pass": name,
            "valid": True,
            "condition": _condition_section(condition),
            "read_back": {
                "channel": measured(read_back["channel"]),
                "payload_bytes": measured(read_back["payload_bytes"]),
                "power_set_value_read_back": measured(
                    read_back["power_set_value_read_back"]
                ),
            },
            "sender": _sender_section(sender, done),
            "receiver": _receiver_section(receiver),
        }

        quantities = _loss_sections(name, sender, receiver)
        if quantities is None:
            return self._invalid_entry(
                cell_id,
                condition,
                name,
                "the receiver counted more packets than the sender sent.",
            )
        entry.update(quantities)
        return entry


def _condition_section(condition: Mapping[str, int]) -> dict[str, Any]:
    """Labels the condition that the host asked for.

    Args:
        condition: The channel, the power set value, the payload size, and
            the frames of one cell.

    Returns:
        The condition section of a cell entry.
    """
    return {
        "channel": configured(condition["channel"]),
        "power_set_value": configured(condition["power_set_value"]),
        "payload_bytes": configured(condition["payload_bytes"]),
        "frames": configured(condition["frames"]),
    }


def _unknown_read_back(condition: Mapping[str, int]) -> dict[str, Any]:
    """States the read-back values of an attempt that reported none.

    The format requires the section, and an invalidated attempt may hold no
    reply to take it from, so the entry repeats the values that the host
    asked for and labels them as the node reported them at the time.

    Args:
        condition: The condition of one cell.

    Returns:
        The read-back section of an invalidated attempt.
    """
    return {
        "channel": measured(condition["channel"]),
        "payload_bytes": measured(condition["payload_bytes"]),
        "power_set_value_read_back": measured(condition["power_set_value"]),
    }


def _sender_section(
    stats: Mapping[str, Any], done: Mapping[str, Any]
) -> dict[str, Any]:
    """Labels the counters of a sender.

    The frame count comes from the go reply rather than the stats reply,
    because the sender states it when the pass ends.

    Args:
        stats: The fields of the stats reply of the sender.
        done: The fields of the go reply that stated done.

    Returns:
        The sender section of a cell entry.
    """
    section: dict[str, Any] = {name: measured(stats[name]) for name in SENDER_COUNTERS}
    section["frames_sent"] = measured(done["frames_sent"])
    section["send_to_callback_us_histogram"] = measured_list(
        list(stats["send_to_callback_us_histogram"])
    )
    section["send_errors"] = [
        {"err": entry["err"], "count": measured(entry["count"])}
        for entry in stats["send_errors"]
    ]
    return section


def _receiver_section(stats: Mapping[str, Any]) -> dict[str, Any]:
    """Labels the counters of a receiver.

    Args:
        stats: The fields of the stats reply of the receiver.

    Returns:
        The receiver section of a cell entry.
    """
    section: dict[str, Any] = {
        name: measured(stats[name]) for name in RECEIVER_COUNTERS
    }
    for name in RECEIVER_LEVELS:
        section[name] = measured(stats[name])
    section["loss_run_length_histogram"] = measured_list(
        list(stats["loss_run_length_histogram"])
    )
    return section


def _loss_sections(
    name: str, sender: Mapping[str, Any], receiver: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Computes the loss quantities of one pass.

    A quantity whose denominator is zero is absent, because no share exists.

    Args:
        name: The pass, broadcast or unicast.
        sender: The fields of the stats reply of the sender.
        receiver: The fields of the stats reply of the receiver.

    Returns:
        The loss quantities of this pass, or None when the counters disagree.
    """
    packets_sent = int(sender["packets_sent"])
    packets_received = int(receiver["packets_received"])
    messages_sent = int(sender["messages_sent"])
    messages_complete = int(receiver["messages_complete"])

    if packets_received > packets_sent or messages_complete > messages_sent:
        return None

    sections: dict[str, Any] = {}
    if packets_sent > 0:
        if name == BROADCAST:
            sections["first_attempt_loss"] = loss_quantity(
                packets_sent - packets_received, packets_sent
            )
        else:
            sections["post_retry_loss"] = loss_quantity(
                int(sender["callback_failed"]), packets_sent
            )
    if messages_sent > 0:
        sections["message_loss"] = loss_quantity(
            messages_sent - messages_complete, messages_sent
        )
    return sections


def build_setup(plan: CellPlan, bench: Bench, bluetooth: str) -> dict[str, Any]:
    """Builds the setup section of a run record.

    Args:
        plan: The plan that the run followed.
        bench: What the user declared and what Bolis set.
        bluetooth: The state of the Bluetooth controller that a node reported.

    Returns:
        The setup section.
    """
    return {
        "country_code": bench.country_code,
        "phy_rate_mbps": configured(1),
        "power_save": bench.power_save,
        "bluetooth_controller": bluetooth,
        "payload_list_bytes": configured_list(
            list(payload_bytes_for_limit(plan.payload_limit_bytes))
        ),
        "baseline_source": "fallback" if plan.is_fallback_baseline else "user",
        "baseline": {
            "channel": configured(plan.baseline.channel),
            "power_set_value": configured(plan.baseline.power_set_value),
            "payload_bytes": configured(plan.baseline.payload_bytes),
        },
    }


def build_declared(bench: Bench) -> dict[str, Any]:
    """Builds the declared section of a run record.

    Args:
        bench: What the user declared about the bench.

    Returns:
        The declared section, with the empty text for an entry that the user
        left out.
    """
    keys = ("distance", "orientation", "antenna", "enclosure", "surroundings")
    return {key: declared(bench.declared_text.get(key, "")) for key in keys}


def build_firmware(hello: Hello) -> dict[str, Any]:
    """Builds the firmware section of a run record.

    Args:
        hello: The condition that a node stated. Both nodes report the same
            firmware, which the host checks before the first cell.

    Returns:
        The firmware section.
    """
    return {
        "firmware_path": hello.firmware_path,
        "elf_sha256": hello.elf_sha256,
        "idf_version": hello.idf_version,
        "espnow_version": measured(hello.espnow_version),
        "payload_limit_bytes": measured(hello.payload_limit_bytes),
    }


def build_nodes(sender: Hello, receiver: Hello) -> list[dict[str, Any]]:
    """Builds the nodes section of a run record.

    The section states no MAC address (specification section 7).

    Args:
        sender: The condition that the sender stated.
        receiver: The condition that the receiver stated.

    Returns:
        One entry per node.
    """
    return [
        {
            "role": "sender",
            "chip": sender.chip,
            "chip_revision": measured(sender.chip_revision),
        },
        {
            "role": "receiver",
            "chip": receiver.chip,
            "chip_revision": measured(receiver.chip_revision),
        },
    ]


# The eight arguments are the eight values that the run section states. A
# type that bundled them would restate the section that this function builds.
def build_run(  # noqa: PLR0913
    run_id: int,
    *,
    started_at: str,
    ended_at: str,
    bolis_version: str,
    mode: str,
    plan_name: str,
    seed: int,
    stopped_reason: str | None = None,
) -> dict[str, Any]:
    """Builds the run section of a run record.

    Args:
        run_id: The run ID of this run.
        started_at: The start, in RFC 3339 form with a Z suffix.
        ended_at: The end, in RFC 3339 form with a Z suffix.
        bolis_version: The version of the host package.
        mode: The run mode, broadcast or unicast.
        plan_name: The plan, default or grid.
        seed: The shuffle seed of this run.
        stopped_reason: Why the run stopped early, or None when it completed.

    Returns:
        The run section.
    """
    section: dict[str, Any] = {
        "run_id": run_id,
        "started_at": started_at,
        "ended_at": ended_at,
        "bolis_version": bolis_version,
        "mode": mode,
        "plan": plan_name,
        "seed": configured(seed),
        "verification_pair_run_id": None,
        "status": "complete" if stopped_reason is None else "stopped",
    }
    if stopped_reason is not None:
        section["stopped_reason"] = stopped_reason
    return section


def build_cells(entries: Sequence[Sequence[Mapping[str, Any]]]) -> list[Any]:
    """Flattens the entries of every cell into the cells section.

    Args:
        entries: One list of pass entries per cell, in run order.

    Returns:
        Every entry, in the order that the passes ran.
    """
    return [entry for cell in entries for entry in cell]
