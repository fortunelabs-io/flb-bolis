"""Builders of one example run record, shared by the test modules.

The schema cases and the writer cases both drive a complete record, so the
builders sit here rather than in either module.
"""

from typing import Any

# The histogram of every pass holds sixteen bins (record
# docs/adr/2026-11-11-control-line-command-fields.md).
EXPECTED_BINS = 16

# The run ID of the example record.
EXAMPLE_RUN_ID = 2749382104


def measured(value: float) -> dict[str, Any]:
    """Builds a number that a node read during the run."""
    return {"value": value, "label": "measured"}


def configured(value: float) -> dict[str, Any]:
    """Builds a number that Bolis set."""
    return {"value": value, "label": "configured"}


def declared(value: str) -> dict[str, Any]:
    """Builds text that the user typed."""
    return {"value": value, "label": "declared"}


def derived(value: float) -> dict[str, Any]:
    """Builds a number computed only from measured values."""
    return {"value": value, "label": "derived"}


def histogram() -> dict[str, Any]:
    """Builds one sixteen-bin histogram."""
    return {"value": [0] * EXPECTED_BINS, "label": "measured"}


def loss(ratio: float = 0.0065) -> dict[str, Any]:
    """Builds one loss quantity with its Wilson interval.

    Args:
        ratio: The share of the denominator that was lost.

    Returns:
        The ratio and the two bounds of its interval.
    """
    return {
        "ratio": derived(ratio),
        "wilson_interval_low": derived(ratio / 2),
        "wilson_interval_high": derived(ratio * 2),
    }


def sender_counters() -> dict[str, Any]:
    """Builds the counters that a sender reports for one pass."""
    return {
        "frames_sent": measured(2000),
        "messages_sent": measured(2000),
        "packets_sent": measured(2000),
        "send_errors": [{"err": "ESP_ERR_ESPNOW_NO_MEM", "count": measured(3)}],
        "callback_ok": measured(1997),
        "callback_failed": measured(3),
        "no_mem_events": measured(3),
        "send_to_callback_us_histogram": histogram(),
        "rejected_lines": measured(0),
    }


def receiver_counters() -> dict[str, Any]:
    """Builds the counters that a receiver reports for one pass."""
    return {
        "packets_received": measured(1987),
        "duplicates": measured(0),
        "foreign_packets": measured(0),
        "messages_complete": measured(1987),
        "messages_incomplete": measured(0),
        "corrupt_packets": measured(0),
        "loss_run_length_histogram": histogram(),
        "rssi_min_dbm": measured(-71.0),
        "rssi_mean_dbm": measured(-63.5),
        "rssi_max_dbm": measured(-58.0),
        "rejected_lines": measured(0),
    }


def record() -> dict[str, Any]:
    """Builds one complete run record that the schema accepts."""
    return {
        "record_version": 1,
        "run": {
            "run_id": EXAMPLE_RUN_ID,
            "started_at": "2026-11-13T09:00:00Z",
            "ended_at": "2026-11-13T09:04:00Z",
            "bolis_version": "0.1.0",
            "mode": "broadcast",
            "plan": "default",
            "seed": configured(2196111516),
            "verification_pair_run_id": None,
            "status": "complete",
        },
        "firmware": {
            "firmware_path": "prebuilt",
            "elf_sha256": "ab" * 32,
            "idf_version": "v5.5.4",
            "espnow_version": measured(2),
            "payload_limit_bytes": measured(1470),
        },
        "nodes": [
            {"role": "sender", "chip": "esp32", "chip_revision": measured(301)},
            {"role": "receiver", "chip": "esp32", "chip_revision": measured(301)},
        ],
        "setup": {
            "country_code": "01",
            "phy_rate_mbps": configured(1),
            "power_save": "none",
            "bluetooth_controller": "disabled",
            "payload_list_bytes": {
                "value": [14, 250, 251, 1469, 1470, 1471, 2940, 2941],
                "label": "configured",
            },
            "baseline_source": "fallback",
            "baseline": {
                "channel": configured(1),
                "power_set_value": configured(44),
                "payload_bytes": configured(128),
            },
        },
        "declared": {
            "distance": declared("2 m"),
            "orientation": declared("antennas parallel"),
            "antenna": declared("on board"),
            "enclosure": declared("none"),
            "surroundings": declared("office desk"),
        },
        "cells": [
            {
                "cell_id": 0,
                "pass": "broadcast",
                "valid": True,
                "condition": {
                    "channel": configured(1),
                    "power_set_value": configured(44),
                    "payload_bytes": configured(128),
                    "frames": configured(2000),
                },
                "read_back": {
                    "channel": measured(1),
                    "payload_bytes": measured(128),
                    "power_set_value_read_back": measured(44),
                },
                "sender": sender_counters(),
                "receiver": receiver_counters(),
                "first_attempt_loss": loss(),
                "message_loss": loss(),
            }
        ],
    }
