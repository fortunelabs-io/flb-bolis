"""Tests for the report builder of one run.

Every case builds a run record in memory and renders it. No case opens a port
and no case reaches a network, which specification section 7 requires of the
whole package.
"""

import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import pytest
from examples import (
    EXAMPLE_RUN_ID,
    configured,
    declared,
    derived,
    histogram,
    receiver_counters,
    record,
    sender_counters,
)

from bolis.report import (
    _CHART_BOTTOM,
    _CHART_HEIGHT,
    _CHART_LEFT,
    _CHART_RIGHT,
    _CHART_TOP,
    _CHART_WIDTH,
    BASELINE,
    CLAIM_LIMIT,
    LIMITS,
    BolisReportError,
    baseline_ratios,
    cell_variable,
    drift_band,
    moved_loss,
    render,
    report_path,
    write_report,
)

# The fallback baseline of thinkbook section 8, which the example record uses.
BASE_CHANNEL = 1
BASE_POWER = 44
BASE_PAYLOAD = 128

RECORD_NAME = f"bolis-{EXAMPLE_RUN_ID}.json"

# Two swept channels of the default plan, away from the baseline channel.
SWEPT_CHANNEL_LOW = 6
SWEPT_CHANNEL_HIGH = 11


def loss_at(ratio: float, low: float, high: float) -> dict[str, Any]:
    """Builds one loss quantity with the interval that a case needs.

    Args:
        ratio: The share of the denominator that was lost.
        low: The lower bound of the Wilson interval.
        high: The upper bound of that interval.

    Returns:
        The ratio and the two bounds.
    """
    return {
        "ratio": derived(ratio),
        "wilson_interval_low": derived(low),
        "wilson_interval_high": derived(high),
    }


# The helper carries one keyword per field of a cell condition, so a case
# states only the field it varies.
def cell(  # noqa: PLR0913
    cell_id: int,
    *,
    unicast: bool = False,
    channel: int = BASE_CHANNEL,
    power: int = BASE_POWER,
    payload: int = BASE_PAYLOAD,
    loss: dict[str, Any] | None = None,
    valid: bool = True,
) -> dict[str, Any]:
    """Builds one cell entry of a run record.

    Args:
        cell_id: The cell of this entry.
        unicast: Whether this entry is the unicast pass of its cell. A unicast
            pass states post-retry loss and a broadcast pass states
            first-attempt loss.
        channel: The channel of the condition.
        power: The transmit power set value of the condition.
        payload: The payload size of the condition, in bytes.
        loss: The loss quantity of the pass, or None for one at 0.0065.
        valid: Whether the run kept this attempt.

    Returns:
        The cell entry.
    """
    which = "unicast" if unicast else "broadcast"
    quantity = "post_retry_loss" if unicast else "first_attempt_loss"
    entry: dict[str, Any] = {
        "cell_id": cell_id,
        "pass": which,
        "valid": valid,
        "condition": {
            "channel": configured(channel),
            "power_set_value": configured(power),
            "payload_bytes": configured(payload),
            "frames": configured(2000),
        },
        "read_back": {
            "channel": configured(channel),
            "payload_bytes": configured(payload),
            "power_set_value_read_back": configured(power),
        },
    }
    if valid:
        entry["sender"] = sender_counters()
        entry["receiver"] = receiver_counters()
        entry[quantity] = loss or loss_at(0.0065, 0.0038, 0.0111)
        entry["message_loss"] = loss_at(0.0100, 0.0070, 0.0140)
    else:
        entry["invalid_reason"] = "the node fell silent."
    return entry


def document_with(cells: list[dict[str, Any]], **run: object) -> dict[str, Any]:
    """Builds a run record whose cells a case states.

    Args:
        cells: The cells section.
        run: Keys to replace in the run section.

    Returns:
        The record.
    """
    built = record()
    built["cells"] = cells
    built["run"].update(run)
    return built


def test_a_cell_that_repeats_the_baseline_is_a_baseline_cell() -> None:
    """A cell whose condition equals the baseline marks the drift repeat."""
    baseline = record()["setup"]["baseline"]
    assert cell_variable(cell(0)["condition"], baseline) == BASELINE


def test_a_cell_that_varies_one_variable_names_it() -> None:
    """One variable away from the baseline names that variable."""
    baseline = record()["setup"]["baseline"]
    assert cell_variable(cell(1, channel=6)["condition"], baseline) == "channel"
    assert cell_variable(cell(2, power=20)["condition"], baseline) == "power_set_value"
    assert (
        cell_variable(cell(3, payload=1470)["condition"], baseline) == "payload_bytes"
    )


def test_a_cell_of_the_grid_names_no_variable() -> None:
    """A cell that varies several variables attributes loss to none of them."""
    baseline = record()["setup"]["baseline"]
    assert cell_variable(cell(4, channel=6, power=20)["condition"], baseline) is None


def test_the_drift_band_of_a_broadcast_pass_reads_first_attempt_loss() -> None:
    """The band is the width between the highest and lowest baseline ratio."""
    baseline = record()["setup"]["baseline"]
    cells = [
        cell(0, loss=loss_at(0.004, 0.003, 0.005)),
        cell(1, loss=loss_at(0.006, 0.005, 0.007)),
    ]

    assert baseline_ratios(cells, baseline, "broadcast") == [0.004, 0.006]
    assert drift_band(cells, baseline, "broadcast") == pytest.approx(0.002)


def test_the_drift_band_of_a_unicast_pass_reads_post_retry_loss() -> None:
    """A unicast pass states post-retry loss, so its band reads that quantity.

    The record of a unicast pass holds no first-attempt loss, so a band that
    read that quantity would be 0 and the drift of the bench would stop
    guarding the conclusion (decision
    2026-11-17-the-drift-band-of-a-unicast-pass.md).
    """
    baseline = record()["setup"]["baseline"]
    cells = [
        cell(0, unicast=True, loss=loss_at(0.001, 0.0005, 0.002)),
        cell(1, unicast=True, loss=loss_at(0.003, 0.002, 0.004)),
    ]

    assert baseline_ratios(cells, baseline, "unicast") == [0.001, 0.003]
    assert drift_band(cells, baseline, "unicast") == pytest.approx(0.002)


def test_a_pass_of_fewer_than_two_baseline_cells_has_no_band() -> None:
    """One repeat states no spread, so the band is 0."""
    baseline = record()["setup"]["baseline"]
    assert drift_band([cell(0)], baseline, "broadcast") == 0.0
    assert drift_band([], baseline, "broadcast") == 0.0


def test_an_invalid_baseline_cell_reaches_no_band() -> None:
    """The band reads the valid baseline cells of its pass."""
    baseline = record()["setup"]["baseline"]
    cells = [
        cell(0, loss=loss_at(0.004, 0.003, 0.005)),
        cell(1, valid=False),
    ]
    assert drift_band(cells, baseline, "broadcast") == 0.0


def test_a_variable_moved_loss_when_it_clears_both_tests() -> None:
    """Separated intervals and a difference above the band name a variable."""
    baseline = record()["setup"]["baseline"]
    cells = [
        cell(0, loss=loss_at(0.004, 0.003, 0.005)),
        cell(1, loss=loss_at(0.006, 0.005, 0.007)),
        cell(2, channel=6, loss=loss_at(0.004, 0.003, 0.005)),
        cell(3, channel=11, loss=loss_at(0.020, 0.018, 0.022)),
    ]

    moved = moved_loss(cells, baseline, "broadcast")

    assert [entry["variable"] for entry in moved] == ["channel"]
    assert moved[0]["low"]["x"] == SWEPT_CHANNEL_LOW
    assert moved[0]["high"]["x"] == SWEPT_CHANNEL_HIGH
    assert moved[0]["difference"] == pytest.approx(0.016)


def test_overlapping_intervals_move_no_loss() -> None:
    """Two cells whose intervals overlap name no variable."""
    baseline = record()["setup"]["baseline"]
    cells = [
        cell(0, loss=loss_at(0.004, 0.003, 0.005)),
        cell(1, loss=loss_at(0.006, 0.005, 0.007)),
        cell(2, channel=6, loss=loss_at(0.004, 0.003, 0.030)),
        cell(3, channel=11, loss=loss_at(0.020, 0.018, 0.022)),
    ]

    assert moved_loss(cells, baseline, "broadcast") == []


def test_a_difference_inside_the_drift_band_moves_no_loss() -> None:
    """A difference that the drift of the bench covers names no variable."""
    baseline = record()["setup"]["baseline"]
    cells = [
        cell(0, loss=loss_at(0.000, 0.000, 0.001)),
        cell(1, loss=loss_at(0.500, 0.400, 0.600)),
        cell(2, channel=6, loss=loss_at(0.004, 0.003, 0.005)),
        cell(3, channel=11, loss=loss_at(0.020, 0.018, 0.022)),
    ]

    # The band is 0.5, which is wider than the difference of 0.016.
    assert drift_band(cells, baseline, "broadcast") == pytest.approx(0.5)
    assert moved_loss(cells, baseline, "broadcast") == []


def test_the_report_states_the_claim_limit_and_the_three_limits() -> None:
    """Every report carries the claim limit and the three limits of section 4."""
    page = render(record(), RECORD_NAME)

    assert CLAIM_LIMIT in page
    for limit in LIMITS:
        assert limit in page


def test_the_report_states_the_legend_of_the_four_labels() -> None:
    """A reader of a number reads what its label means."""
    page = render(record(), RECORD_NAME)

    for label in ("measured", "configured", "derived", "declared"):
        assert f"[{label}]" in page


def test_the_report_links_every_number_to_the_record() -> None:
    """A number carries the JSON Pointer of the key that states it."""
    page = render(record(), RECORD_NAME)

    assert f'href="{RECORD_NAME}#/run/seed/value"' in page
    assert f'href="{RECORD_NAME}#/setup/phy_rate_mbps/value"' in page


def test_the_report_escapes_the_text_that_the_user_typed() -> None:
    """The declared section holds text that Bolis did not check."""
    document = record()
    document["declared"]["distance"] = declared('2 m <script>alert("x")</script>')

    page = render(document, RECORD_NAME)

    assert "<script>" not in page
    assert "&lt;script&gt;" in page


def test_the_report_carries_no_script_and_no_network_reference() -> None:
    """The file loads nothing and runs nothing (thinkbook section 10)."""
    page = render(record(), RECORD_NAME)

    assert "<script" not in page
    assert "http://" not in page
    assert "https://" not in page
    assert "innerHTML" not in page


def test_the_report_of_a_stopped_run_states_why_it_stopped() -> None:
    """A run that stopped early still reports the cells that ran."""
    document = document_with(
        [cell(0)], status="stopped", stopped_reason="cell 1 stopped the run: silence"
    )

    page = render(document, RECORD_NAME)

    assert "stopped before the end of its plan" in page
    assert "cell 1 stopped the run" in page


def test_the_report_names_the_variables_that_moved_loss() -> None:
    """The paragraph names the variable and the two cells, with no cause."""
    document = document_with(
        [
            cell(0, loss=loss_at(0.004, 0.003, 0.005)),
            cell(1, loss=loss_at(0.006, 0.005, 0.007)),
            cell(2, channel=6, loss=loss_at(0.004, 0.003, 0.005)),
            cell(3, channel=11, loss=loss_at(0.020, 0.018, 0.022)),
        ]
    )

    page = render(document, RECORD_NAME)

    assert "Channel" in page
    assert "The report states no cause" in page


def test_the_report_states_when_no_variable_moved_loss() -> None:
    """A run where nothing moved says so, rather than saying nothing."""
    page = render(record(), RECORD_NAME)

    assert "No variable moved loss" in page


def test_a_record_without_a_section_builds_no_report() -> None:
    """A record that carries no cells section names the missing section."""
    document = record()
    del document["cells"]

    with pytest.raises(BolisReportError, match="cells"):
        render(document, RECORD_NAME)


def test_the_report_sits_beside_the_record_with_the_same_stem() -> None:
    """A user who copies a pair keeps both files."""
    assert report_path(Path("out"), 7).name == "bolis-7.html"


def test_write_report_writes_one_file(tmp_path: Path) -> None:
    """The writer puts the report in the directory that holds the record."""
    path = write_report(record(), tmp_path)

    assert path == tmp_path / f"bolis-{EXAMPLE_RUN_ID}.html"
    assert path.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
    assert not list(tmp_path.glob("*.part"))


def test_write_report_refuses_a_record_without_a_run_id(tmp_path: Path) -> None:
    """A record that states no run ID names no report file."""
    document = record()
    document["run"] = dict(document["run"])
    del document["run"]["run_id"]

    with pytest.raises(BolisReportError, match="run ID"):
        write_report(document, tmp_path)


def test_the_unicast_histogram_reaches_the_report() -> None:
    """Each unicast pass states its send-to-callback histogram."""
    document = document_with([cell(0, unicast=True)])
    document["cells"][0]["sender"]["send_to_callback_us_histogram"] = histogram()

    page = render(document, RECORD_NAME)

    assert "Send-to-callback time" in page
    assert "/sender/send_to_callback_us_histogram/value" in page


def test_every_mark_of_a_chart_sits_inside_its_plot_area() -> None:
    """A point or an interval outside the axes would render off the chart.

    A case that only reads the text of a page cannot see a mark that the
    viewBox clips, so this case checks the geometry of every chart.
    """
    document = document_with(
        [
            cell(0, loss=loss_at(0.004, 0.003, 0.005)),
            cell(1, loss=loss_at(0.006, 0.005, 0.007)),
            cell(2, channel=SWEPT_CHANNEL_LOW, loss=loss_at(0.0045, 0.0035, 0.0055)),
            cell(3, channel=SWEPT_CHANNEL_HIGH, loss=loss_at(0.030, 0.027, 0.033)),
        ]
    )
    page = render(document, RECORD_NAME)

    bottom = _CHART_HEIGHT - _CHART_BOTTOM
    right = _CHART_WIDTH - _CHART_RIGHT
    charts = re.findall(r'<svg class="chart".*?</svg>', page, re.S)
    assert charts

    for chart in charts:
        # The page came from render above, so the parser reads text that
        # this process produced rather than input from elsewhere.
        for element in ElementTree.fromstring(chart).iter():  # noqa: S314
            tag = element.tag.split("}")[-1]
            if tag == "circle":
                assert _CHART_TOP - 1 <= float(element.get("cy", "0")) <= bottom + 1
                assert _CHART_LEFT - 1 <= float(element.get("cx", "0")) <= right + 1
            if tag == "rect":
                assert float(element.get("height", "0")) >= 0
                assert _CHART_TOP - 1 <= float(element.get("y", "0")) <= bottom + 1
