"""Tests for the orchestrator of one run.

Every case runs with no serial port and with no node. The orchestrator drives
two transports, so a case scripts the replies of each one and checks the
order of the commands and the record that the run produces.
"""

import re
from typing import Any

import pytest
from examples import EXPECTED_BINS

from bolis.orchestrator import (
    BROADCAST,
    CELL_ATTEMPTS,
    UNICAST,
    Bench,
    BolisRunError,
    Orchestrator,
    build_cells,
    build_declared,
    build_firmware,
    build_nodes,
    build_run,
    build_setup,
)
from bolis.protocol import Hello
from bolis.record import validate_record
from bolis.sweep import PAYLOAD_LIMIT_BYTES_V2, CellPlan, build_plan
from bolis.transport import BolisNodeResetError, BolisPassSilentError

# Six hexadecimal pairs joined by colons. A role reply carries a MAC address,
# and no record may state one.
MAC_PATTERN = re.compile(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}")

RECEIVER_MAC = "aa:bb:cc:dd:ee:ff"

# The run ID that these cases send in the role command.
RUN_ID = 7

# The condition of the one cell that these cases run.
CONDITION = {
    "channel": 1,
    "power_set_value": 44,
    "payload_bytes": 128,
    "frames": 2000,
}

PACKETS_SENT = 2000
PACKETS_RECEIVED = 1987
MESSAGES_SENT = 2000
MESSAGES_COMPLETE = 1987
CALLBACK_FAILED = 3


class FakeReply:
    """One decoded reply, with the fields that a node stated."""

    def __init__(self, fields: dict[str, Any]) -> None:
        """Holds the fields of one reply.

        Args:
            fields: Every key that the envelope does not own.
        """
        self.fields = fields


class FakeTransport:
    """A transport that answers from a script and records what it was sent."""

    def __init__(self, replies: dict[str, Any] | None = None) -> None:
        """Scripts the reply of each command name.

        Args:
            replies: One entry per command name. A value that is an exception
                is raised instead of returned.
        """
        self.replies = replies or {}
        self.sent: list[tuple[str, dict[str, Any]]] = []

    def command(self, name: str, fields: dict[str, Any] | None = None) -> FakeReply:
        """Records one command and returns its scripted reply."""
        self.sent.append((name, dict(fields or {})))
        answer = self.replies.get(name, {})
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, list):
            answer = answer.pop(0)
            if isinstance(answer, Exception):
                raise answer
        return FakeReply(dict(answer))

    def run_pass(self, fields: dict[str, Any], on_progress: object = None) -> FakeReply:
        """Records one go command and returns its scripted reply."""
        self.sent.append(("go", dict(fields)))
        answer = self.replies.get("go", {})
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, list):
            answer = answer.pop(0)
            if isinstance(answer, Exception):
                raise answer
        return FakeReply(dict(answer))


def sender_stats(**overrides: object) -> dict[str, Any]:
    """Builds the fields of a sender stats reply."""
    fields: dict[str, Any] = {
        "messages_sent": MESSAGES_SENT,
        "packets_sent": PACKETS_SENT,
        "callback_ok": PACKETS_SENT - CALLBACK_FAILED,
        "callback_failed": CALLBACK_FAILED,
        "no_mem_events": 0,
        "rejected_lines": 0,
        "send_to_callback_us_histogram": [0] * EXPECTED_BINS,
        "send_errors": [{"err": "ESP_ERR_ESPNOW_NO_MEM", "count": 3}],
    }
    fields.update(overrides)
    return fields


def receiver_stats(**overrides: object) -> dict[str, Any]:
    """Builds the fields of a receiver stats reply."""
    fields: dict[str, Any] = {
        "packets_received": PACKETS_RECEIVED,
        "duplicates": 0,
        "foreign_packets": 0,
        "messages_complete": MESSAGES_COMPLETE,
        "messages_incomplete": 13,
        "corrupt_packets": 0,
        "dropped_packets": 0,
        "rejected_lines": 0,
        "loss_run_length_histogram": [0] * EXPECTED_BINS,
        "rssi_min_dbm": -71.0,
        "rssi_mean_dbm": -63.5,
        "rssi_max_dbm": -58.0,
    }
    fields.update(overrides)
    return fields


def read_back() -> dict[str, Any]:
    """Builds the fields of a cell reply."""
    return {
        "cell_id": 0,
        "channel": 1,
        "payload_bytes": 128,
        "power_set_value_read_back": 44,
    }


def pair(
    sender_extra: dict[str, Any] | None = None,
    receiver_extra: dict[str, Any] | None = None,
) -> tuple[FakeTransport, FakeTransport]:
    """Builds one pair of transports that answer a whole pass.

    Args:
        sender_extra: Replies to add or replace on the sender.
        receiver_extra: Replies to add or replace on the receiver.

    Returns:
        The sender and the receiver, in that order.
    """
    sender = FakeTransport(
        {
            "role": {"role": "sender", "mac": "11:22:33:44:55:66"},
            "cell": read_back(),
            "go": {"cell_id": 0, "done": True, "frames_sent": PACKETS_SENT},
            "stats": sender_stats(),
        }
    )
    receiver = FakeTransport(
        {
            "role": {"role": "receiver", "mac": RECEIVER_MAC},
            "cell": read_back(),
            "stats": receiver_stats(),
        }
    )
    sender.replies.update(sender_extra or {})
    receiver.replies.update(receiver_extra or {})
    return sender, receiver


def orchestrator(sender: FakeTransport, receiver: FakeTransport) -> Orchestrator:
    """Builds an orchestrator that waits for nothing."""
    return Orchestrator(sender, receiver, sleep=lambda _seconds: None)


def hello(role_chip: str = "esp32") -> Hello:
    """Builds the condition that a node states."""
    return Hello(
        chip=role_chip,
        chip_revision=301,
        idf_version="v5.5.4",
        espnow_version=2,
        payload_limit_bytes=1470,
        bolis_version="0.1.0",
        firmware_path="prebuilt",
        elf_sha256="ab" * 32,
        bluetooth_controller="disabled",
    )


def test_the_receiver_takes_its_role_before_the_sender() -> None:
    """The MAC address of the receiver reaches the sender as peer_mac."""
    sender, receiver = pair()

    orchestrator(sender, receiver).assign_roles(RUN_ID)

    assert receiver.sent[0][0] == "role"
    assert receiver.sent[0][1] == {"role": "receiver", "run_id": RUN_ID}
    assert sender.sent[0][1]["peer_mac"] == RECEIVER_MAC
    assert sender.sent[0][1]["run_id"] == RUN_ID


def test_a_receiver_that_states_no_address_stops_the_run() -> None:
    """The sender cannot address a unicast pass without the peer address."""
    sender, receiver = pair(receiver_extra={"role": {"role": "receiver"}})

    with pytest.raises(BolisRunError, match="MAC address"):
        orchestrator(sender, receiver).assign_roles(RUN_ID)


def test_the_receiver_takes_the_cell_before_the_sender() -> None:
    """The receiver listens on the new channel before the first frame."""
    sender, receiver = pair()

    orchestrator(sender, receiver).run_cell(0, CONDITION, BROADCAST)

    assert [name for name, _ in receiver.sent] == ["cell", "stats"]
    assert [name for name, _ in sender.sent] == ["cell", "go", "stats"]


def test_the_host_waits_before_it_reads_the_counters() -> None:
    """A settle time catches late frames before the receiver reports."""
    sender, receiver = pair()
    waits: list[float] = []
    runner = Orchestrator(sender, receiver, sleep=waits.append, settle_s=0.25)

    runner.run_cell(0, CONDITION, BROADCAST)

    assert waits == [0.25]


def test_a_broadcast_run_sends_one_pass() -> None:
    """Every run carries a broadcast pass."""
    sender, receiver = pair()

    entries = orchestrator(sender, receiver).run_cell(0, CONDITION, BROADCAST)

    assert [entry["pass"] for entry in entries] == [BROADCAST]


def test_a_unicast_run_sends_the_broadcast_pass_first() -> None:
    """A unicast pass follows the broadcast pass of the same cell."""
    sender, receiver = pair()

    entries = orchestrator(sender, receiver).run_cell(0, CONDITION, UNICAST)

    assert [entry["pass"] for entry in entries] == [BROADCAST, UNICAST]


def test_a_broadcast_pass_states_its_first_attempt_loss() -> None:
    """The share divides the packets that the receiver missed."""
    sender, receiver = pair()

    entry = orchestrator(sender, receiver).run_cell(0, CONDITION, BROADCAST)[0]

    expected = (PACKETS_SENT - PACKETS_RECEIVED) / PACKETS_SENT
    assert entry["first_attempt_loss"]["ratio"]["value"] == expected
    assert "post_retry_loss" not in entry


def test_a_unicast_pass_states_its_post_retry_loss() -> None:
    """The share divides the send callbacks that failed."""
    sender, receiver = pair()

    entries = orchestrator(sender, receiver).run_cell(0, CONDITION, UNICAST)
    unicast = entries[1]

    assert (
        unicast["post_retry_loss"]["ratio"]["value"] == CALLBACK_FAILED / PACKETS_SENT
    )
    assert "first_attempt_loss" not in unicast


def test_every_pass_states_its_message_loss() -> None:
    """A message that produced no fragment counts as lost."""
    sender, receiver = pair()

    entry = orchestrator(sender, receiver).run_cell(0, CONDITION, BROADCAST)[0]

    expected = (MESSAGES_SENT - MESSAGES_COMPLETE) / MESSAGES_SENT
    assert entry["message_loss"]["ratio"]["value"] == expected


def test_the_frame_count_comes_from_the_reply_that_ended_the_pass() -> None:
    """The sender states the frames it sent when the pass ends."""
    sender, receiver = pair(
        sender_extra={"go": {"cell_id": 0, "done": True, "frames_sent": 1999}}
    )

    entry = orchestrator(sender, receiver).run_cell(0, CONDITION, BROADCAST)[0]

    assert entry["sender"]["frames_sent"] == {"value": 1999, "label": "measured"}


def test_a_node_that_resets_invalidates_the_attempt_and_runs_it_again() -> None:
    """Thinkbook section 11 reruns a cell that a reset interrupted."""
    sender, receiver = pair(
        sender_extra={
            "go": [
                BolisNodeResetError(3),
                {"cell_id": 0, "done": True, "frames_sent": PACKETS_SENT},
            ]
        }
    )

    entry = orchestrator(sender, receiver).run_cell(0, CONDITION, BROADCAST)[0]

    assert entry["valid"] is True
    assert [name for name, _ in sender.sent].count("go") == CELL_ATTEMPTS


def test_a_pass_that_falls_silent_twice_stays_invalid() -> None:
    """One rerun is the budget, and the entry names what invalidated it."""
    sender, receiver = pair(sender_extra={"go": BolisPassSilentError(3, 3.0, 700)})

    entry = orchestrator(sender, receiver).run_cell(0, CONDITION, BROADCAST)[0]

    assert entry["valid"] is False
    assert "700 frames" in entry["invalid_reason"]
    assert "first_attempt_loss" not in entry
    assert "sender" not in entry


def test_counters_that_disagree_invalidate_the_attempt() -> None:
    """A receiver cannot count more packets than the sender sent."""
    sender, receiver = pair(
        receiver_extra={"stats": receiver_stats(packets_received=PACKETS_SENT + 1)}
    )

    entry = orchestrator(sender, receiver).run_cell(0, CONDITION, BROADCAST)[0]

    assert entry["valid"] is False
    assert "more packets" in entry["invalid_reason"]


def test_a_pass_that_sent_nothing_states_no_loss() -> None:
    """A share needs a denominator."""
    sender, receiver = pair(
        sender_extra={
            "stats": sender_stats(packets_sent=0, messages_sent=0, callback_failed=0),
            "go": {"cell_id": 0, "done": True, "frames_sent": 0},
        },
        receiver_extra={
            "stats": receiver_stats(packets_received=0, messages_complete=0)
        },
    )

    entry = orchestrator(sender, receiver).run_cell(0, CONDITION, BROADCAST)[0]

    assert entry["valid"] is True
    assert "first_attempt_loss" not in entry
    assert "message_loss" not in entry


def test_a_run_builds_a_record_that_meets_the_schema() -> None:
    """The document of one run passes the check that the writer runs."""
    sender, receiver = pair()
    runner = orchestrator(sender, receiver)
    runner.assign_roles(2749382104)
    entries = [runner.run_cell(0, CONDITION, BROADCAST)]

    bench = Bench(
        country_code="01",
        power_save="none",
        declared_text={"distance": "2 m", "antenna": "on board"},
    )
    document = {
        "run": build_run(
            2749382104,
            started_at="2026-11-13T09:00:00Z",
            ended_at="2026-11-13T09:04:00Z",
            bolis_version="0.1.0",
            mode=BROADCAST,
            plan_name="default",
            seed=2196111516,
        ),
        "firmware": build_firmware(hello()),
        "nodes": build_nodes(hello(), hello()),
        "setup": build_setup(_plan(), bench, "disabled"),
        "declared": build_declared(bench),
        "cells": build_cells(entries),
    }
    document["record_version"] = 1

    validate_record(document)


def test_a_record_of_a_run_states_no_mac_address() -> None:
    """The address of the receiver reaches the sender and no record."""
    sender, receiver = pair()
    runner = orchestrator(sender, receiver)
    runner.assign_roles(RUN_ID)
    entries = runner.run_cell(0, CONDITION, BROADCAST)

    assert MAC_PATTERN.search(repr(entries)) is None


def test_a_stopped_run_states_why() -> None:
    """A run that stopped early names the reason in its run section."""
    section = build_run(
        7,
        started_at="2026-11-13T09:00:00Z",
        ended_at="2026-11-13T09:01:00Z",
        bolis_version="0.1.0",
        mode=BROADCAST,
        plan_name="default",
        seed=1,
        stopped_reason="the sender answered no stats command.",
    )

    assert section["status"] == "stopped"
    assert "stopped_reason" in section


def test_a_declared_entry_that_the_user_left_out_is_empty() -> None:
    """Bolis checks none of the declared section, and states what it holds."""
    bench = Bench(country_code="01", power_save="none", declared_text={})

    section = build_declared(bench)

    assert section["distance"] == {"value": "", "label": "declared"}


def _plan() -> CellPlan:
    """Builds one default plan for the setup section."""
    return build_plan(None, PAYLOAD_LIMIT_BYTES_V2, seed=2196111516)
