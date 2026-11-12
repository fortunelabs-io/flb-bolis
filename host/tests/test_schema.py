"""Tests for the JSON Schema of the run record format.

The schema is the normative statement of the format
(record docs/adr/2026-11-12-run-record-format.md), so these cases drive the
schema file itself rather than a module of the package. A valid record passes,
and each case below removes or changes one part of it and expects a rejection.
"""

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

# The schema sits beside the repository root rather than inside the package.
SCHEMA_PATH = Path(__file__).parents[2] / "schema" / "run-record.schema.json"

# The histogram of every pass holds sixteen bins (record
# docs/adr/2026-11-11-control-line-command-fields.md).
EXPECTED_BINS = 16

# The cell range that fifteen bits of the frame header carry.
EXPECTED_CELL_ID_MAX = 32767

# The widest run ID that four bytes of the frame header carry.
EXPECTED_RUN_ID_MAX = 4294967295


def measured(value: float) -> dict[str, Any]:
    """Builds a number that a node read during the run."""
    return {"value": value, "label": "measured"}


def configured(value: float) -> dict[str, Any]:
    """Builds a number that Bolis set."""
    return {"value": value, "label": "configured"}


def declared(value: str) -> dict[str, Any]:
    """Builds text that the user typed."""
    return {"value": value, "label": "declared"}


def histogram() -> dict[str, Any]:
    """Builds one sixteen-bin histogram."""
    return {"value": [0] * EXPECTED_BINS, "label": "measured"}


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
            "run_id": 2749382104,
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
            }
        ],
    }


@pytest.fixture(scope="module")
def validator() -> jsonschema.protocols.Validator:
    """Builds one validator from the schema file.

    Returns:
        A validator of the dialect that the schema names.
    """
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    return cls(schema)


def test_the_schema_is_a_valid_schema_of_its_dialect(
    validator: jsonschema.protocols.Validator,
) -> None:
    """The schema itself meets the dialect that it names."""
    assert validator.schema["$schema"].endswith("2020-12/schema")


def test_a_complete_record_passes(
    validator: jsonschema.protocols.Validator,
) -> None:
    """The example record meets the format."""
    validator.validate(record())


def test_a_record_without_a_version_fails(
    validator: jsonschema.protocols.Validator,
) -> None:
    """A reader of an old record learns which rules it follows from the version."""
    document = record()
    del document["record_version"]
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)


@pytest.mark.parametrize(
    "section", ["run", "firmware", "nodes", "setup", "declared", "cells"]
)
def test_every_section_of_thinkbook_section_9_is_required(
    validator: jsonschema.protocols.Validator, section: str
) -> None:
    """The record holds the six sections that thinkbook section 9 names."""
    document = record()
    del document[section]
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)


def test_a_bare_number_fails(validator: jsonschema.protocols.Validator) -> None:
    """Every number that states a quantity of the run carries its origin label."""
    document = record()
    document["cells"][0]["sender"]["packets_sent"] = 2000
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)


def test_a_counter_labelled_configured_fails(
    validator: jsonschema.protocols.Validator,
) -> None:
    """A counter of a node is measured, so no other label passes."""
    document = record()
    document["cells"][0]["sender"]["packets_sent"] = configured(2000)
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)


def test_a_label_outside_the_four_fails(
    validator: jsonschema.protocols.Validator,
) -> None:
    """The four labels of the origin record are the whole set."""
    document = record()
    document["cells"][0]["sender"]["packets_sent"] = {
        "value": 2000,
        "label": "estimated",
    }
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)


@pytest.mark.parametrize("bins", [15, 17, 24])
def test_a_histogram_of_another_bin_count_fails(
    validator: jsonschema.protocols.Validator, bins: int
) -> None:
    """A histogram holds sixteen bins, and a wider one needs a new record."""
    document = record()
    document["cells"][0]["receiver"]["loss_run_length_histogram"] = {
        "value": [0] * bins,
        "label": "measured",
    }
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)


def test_a_stopped_run_states_why(validator: jsonschema.protocols.Validator) -> None:
    """A run that stopped early names the reason."""
    document = record()
    document["run"]["status"] = "stopped"
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)

    document["run"]["stopped_reason"] = "the sender answered no stats command."
    validator.validate(document)


def test_a_complete_run_states_no_stopped_reason(
    validator: jsonschema.protocols.Validator,
) -> None:
    """A reason on a complete run would state a stop that did not happen."""
    document = record()
    document["run"]["stopped_reason"] = "none"
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)


def test_an_invalid_cell_states_why(
    validator: jsonschema.protocols.Validator,
) -> None:
    """An attempt that the run invalidated names the cause."""
    document = record()
    document["cells"][0]["valid"] = False
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)

    document["cells"][0]["invalid_reason"] = "the node started again during the pass."
    validator.validate(document)


def test_a_record_holding_an_unknown_key_fails(
    validator: jsonschema.protocols.Validator,
) -> None:
    """A key that no record names cannot enter the format by accident."""
    document = record()
    document["run"]["operator_name"] = "someone"
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)


def test_a_node_holding_a_mac_address_fails(
    validator: jsonschema.protocols.Validator,
) -> None:
    """The record stores no MAC address (specification section 7)."""
    document = record()
    document["nodes"][0]["mac"] = "aa:bb:cc:dd:ee:ff"
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)


@pytest.mark.parametrize("run_id", [-1, EXPECTED_RUN_ID_MAX + 1])
def test_a_run_id_outside_four_bytes_fails(
    validator: jsonschema.protocols.Validator, run_id: int
) -> None:
    """The frame header carries the run ID in four bytes."""
    document = record()
    document["run"]["run_id"] = run_id
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)


@pytest.mark.parametrize("cell_id", [-1, EXPECTED_CELL_ID_MAX + 1])
def test_a_cell_id_outside_fifteen_bits_fails(
    validator: jsonschema.protocols.Validator, cell_id: int
) -> None:
    """The frame header carries the cell in fifteen bits."""
    document = record()
    document["cells"][0]["cell_id"] = cell_id
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)


def test_a_timestamp_outside_utc_fails(
    validator: jsonschema.protocols.Validator,
) -> None:
    """Thinkbook section 9 states the start and the end in UTC."""
    document = record()
    document["run"]["started_at"] = "2026-11-13T09:00:00+07:00"
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)


def test_a_verification_pair_names_the_other_run(
    validator: jsonschema.protocols.Validator,
) -> None:
    """A run of a pair names the run ID of the other run."""
    document = record()
    document["run"]["verification_pair_run_id"] = 11
    validator.validate(document)


def test_a_record_of_a_stopped_run_keeps_the_cells_that_ran(
    validator: jsonschema.protocols.Validator,
) -> None:
    """A run that stops keeps a partial record rather than none."""
    document = record()
    document["run"]["status"] = "stopped"
    document["run"]["stopped_reason"] = "the sender fell silent during a pass."
    document["cells"] = []
    validator.validate(document)
