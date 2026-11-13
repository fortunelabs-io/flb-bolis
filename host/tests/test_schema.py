"""Tests for the JSON Schema of the run record format.

The schema is the normative statement of the format
(record docs/adr/2026-11-12-run-record-format.md), so these cases drive the
schema file itself rather than a module of the package. A valid record passes,
and each case below removes or changes one part of it and expects a rejection.
"""

import json
from pathlib import Path

import jsonschema
import pytest
from examples import (
    configured,
    loss,
    measured,
    record,
)

# The schema sits beside the repository root rather than inside the package.
SCHEMA_PATH = Path(__file__).parents[2] / "schema" / "run-record.schema.json"

# The cell range that fifteen bits of the frame header carry.
EXPECTED_CELL_ID_MAX = 32767

# The widest run ID that four bytes of the frame header carry.
EXPECTED_RUN_ID_MAX = 4294967295


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
    cell = document["cells"][0]
    cell["valid"] = False
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)

    cell["invalid_reason"] = "the node started again during the pass."
    del cell["first_attempt_loss"]
    del cell["message_loss"]
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


def test_a_broadcast_pass_states_its_first_attempt_loss(
    validator: jsonschema.protocols.Validator,
) -> None:
    """A valid broadcast pass that sent frames states the share that failed."""
    document = record()
    del document["cells"][0]["first_attempt_loss"]
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)


def test_a_pass_states_its_message_loss(
    validator: jsonschema.protocols.Validator,
) -> None:
    """Both modes state the share of messages that did not arrive whole."""
    document = record()
    del document["cells"][0]["message_loss"]
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)


def test_a_broadcast_pass_states_no_post_retry_loss(
    validator: jsonschema.protocols.Validator,
) -> None:
    """A broadcast pass allows no retry, so the quantity has no meaning on it."""
    document = record()
    document["cells"][0]["post_retry_loss"] = loss()
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)


def test_a_unicast_pass_states_post_retry_loss_and_no_first_attempt_loss(
    validator: jsonschema.protocols.Validator,
) -> None:
    """The observable of a unicast pass is the send callback failure."""
    document = record()
    cell = document["cells"][0]
    # The key names a broadcast or a unicast pass (thinkbook section 7). S105
    # reads the name as a credential, and the accepted records fix the key.
    cell["pass"] = "unicast"  # noqa: S105
    del cell["first_attempt_loss"]
    cell["post_retry_loss"] = loss()
    validator.validate(document)

    cell["first_attempt_loss"] = loss()
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)


def test_a_pass_that_sent_nothing_states_no_loss(
    validator: jsonschema.protocols.Validator,
) -> None:
    """A share needs a denominator, and a pass that sent nothing has none."""
    document = record()
    cell = document["cells"][0]
    cell["sender"]["packets_sent"] = measured(0)
    cell["sender"]["messages_sent"] = measured(0)
    del cell["first_attempt_loss"]
    del cell["message_loss"]
    validator.validate(document)


def test_an_invalidated_attempt_states_no_loss(
    validator: jsonschema.protocols.Validator,
) -> None:
    """A conclusion needs counters that no stats command completed."""
    document = record()
    cell = document["cells"][0]
    cell["valid"] = False
    cell["invalid_reason"] = "the node started again during the pass."
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)


def test_an_invalidated_attempt_needs_no_counters(
    validator: jsonschema.protocols.Validator,
) -> None:
    """A pass that a reset ended answered no stats command."""
    document = record()
    document["cells"][0] = {
        "cell_id": 0,
        "pass": "broadcast",
        "valid": False,
        "invalid_reason": "the pass fell silent after 700 frames.",
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
    }
    validator.validate(document)


def test_a_valid_attempt_states_the_counters_of_both_nodes(
    validator: jsonschema.protocols.Validator,
) -> None:
    """A pass that ran reports from both nodes."""
    document = record()
    del document["cells"][0]["receiver"]
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)


def test_a_loss_quantity_carries_the_derived_label(
    validator: jsonschema.protocols.Validator,
) -> None:
    """A value computed from measured values is derived, not measured."""
    document = record()
    document["cells"][0]["first_attempt_loss"]["ratio"] = measured(0.0065)
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)


def test_a_loss_quantity_states_both_interval_bounds(
    validator: jsonschema.protocols.Validator,
) -> None:
    """A ratio without its interval leaves a reader to compute one."""
    document = record()
    del document["cells"][0]["first_attempt_loss"]["wilson_interval_high"]
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(document)
