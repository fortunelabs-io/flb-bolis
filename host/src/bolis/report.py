"""The report builder of one run.

The builder reads one run record and writes one static HTML file (thinkbook
section 10, specification section 6). The file loads nothing from a network:
every style sits inline and every chart is inline SVG. The builder writes no
script, so no value of a record reaches a page through innerHTML.

Every number of the report carries its origin label and a link to the key of
the run record that states it (decision 2026-10-01-number-origin-labels.md and
decision 2026-11-16-the-drift-band-and-the-record-link-of-a-report.md).
"""

import html
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bolis import BolisError

# The claim limit of specification section 4. Every report states it.
CLAIM_LIMIT = (
    "This report shows how the tested configuration performs "
    " under the conditions of the test run."
    " It does not diagnose failures outside the test environment."
)

# The three limits that every report states (specification section 4).
LIMITS = (
    "The results apply to a PHY rate of 1 Mbps.",
    "The conclusions hold at the baseline of this run.",
    "The sweep does not test interactions between the variables.",
)

# The legend of the four origin labels (decision 2026-10-01-number-origin-labels.md).
LABEL_LEGEND = (
    ("measured", "A value that a node counted or read during the run."),
    ("configured", "A value that Bolis set before the run."),
    ("derived", "A value computed only from measured values."),
    ("declared", "Text that the user typed and that Bolis did not check."),
)

# The three variables that a sweep varies (specification section 4).
VARIABLES = ("channel", "power_set_value", "payload_bytes")

# The heading of the chart of each variable, with the unit of its axis.
VARIABLE_TITLES = {
    "channel": "Channel",
    "power_set_value": "Transmit power (units of 0.25 dBm)",
    "payload_bytes": "Payload size (bytes)",
}

# The loss quantity that each pass states (decision
# 2026-11-13-loss-quantities-in-a-cell.md). The drift band of a pass reads the
# quantity of that pass (decision 2026-11-17-the-drift-band-of-a-unicast-pass.md).
PASS_QUANTITY = {
    "broadcast": "first_attempt_loss",
    "unicast": "post_retry_loss",
}

# The name that each loss quantity carries in the report.
QUANTITY_TITLES = {
    "first_attempt_loss": "first-attempt loss",
    "post_retry_loss": "post-retry loss",
    "message_loss": "message loss",
}

# The marker of a cell whose condition equals the baseline, including every
# drift repeat (thinkbook section 8).
BASELINE = "baseline"

# The bins of every histogram (decision 2026-11-11-control-line-command-fields.md).
HISTOGRAM_BINS = 16

# The baseline cells that a pass needs before its repeats state a spread. A
# pass below this count has a drift band of 0 (decision
# 2026-11-17-the-drift-band-of-a-unicast-pass.md).
MINIMUM_BASELINE_CELLS = 2

# The geometry of one chart, in the units of its viewBox.
_CHART_WIDTH = 640
_CHART_HEIGHT = 260
_CHART_LEFT = 72
_CHART_RIGHT = 16
_CHART_TOP = 16
_CHART_BOTTOM = 44

# A histogram carries the width of a chart, so one font size renders at the
# same height on both. A viewBox narrower than a chart scales its text up.
_HISTOGRAM_HEIGHT = 160


class BolisReportError(BolisError):
    """Raised when a run record does not carry what a report needs."""


def _text(value: object) -> str:
    """Escapes one value of a record for the body of the report.

    Every string of a record reaches the page through this function, because a
    declared entry holds text that the user typed and Bolis did not check.

    Args:
        value: The value to escape.

    Returns:
        The value as text that carries no markup.
    """
    return html.escape(str(value), quote=True)


def _value(entry: Mapping[str, Any]) -> float:
    """Returns the number that one labelled entry of a record holds.

    Args:
        entry: The entry, which holds a value and a label.

    Returns:
        The value of that entry.

    Raises:
        BolisReportError: The entry holds no number.
    """
    value = entry.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise BolisReportError(
            f"the record holds {value!r} where a report needs a number."
        )
    return float(value)


def _digits(value: float) -> str:
    """Formats one number for the page.

    A loss ratio sits near zero, so a share keeps four decimal places. A whole
    number keeps none.

    Args:
        value: The number to format.

    Returns:
        The number as text.
    """
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.4f}"


def _sentence_case(text: str) -> str:
    """Raises the first letter of one phrase and leaves the rest alone.

    A unit such as dBm keeps its case, because only the first letter moves.

    Args:
        text: The phrase to raise.

    Returns:
        The phrase with its first letter in upper case.
    """
    return f"{text[:1].upper()}{text[1:]}"


def labelled(entry: Mapping[str, Any], pointer: str, record_name: str) -> str:
    """Renders one labelled number with its origin label and its record link.

    Args:
        entry: The entry of the record, which holds a value and a label.
        pointer: The JSON Pointer of the key that states the value.
        record_name: The file name of the run record.

    Returns:
        The number, its label, and a link to the key of the record.
    """
    label = _text(entry.get("label", ""))
    href = f"{_text(record_name)}#{_text(pointer)}"
    return (
        f'<span class="n">{_text(_digits(_value(entry)))}'
        f'<a class="lbl" href="{href}">[{label}]</a></span>'
    )


def labelled_no_link(value: float, label: str) -> str:
    """Renders one labelled number that no single key of the record states.

    The report reads several keys to reach this number, so no JSON Pointer
    names it and the number carries its origin label alone. A number that one
    key states carries a link as well, through `labelled`.

    Args:
        value: The number to render.
        label: The origin label of the number, one of the four of decision
            2026-10-01-number-origin-labels.md.

    Returns:
        The number and its label.
    """
    return (
        f'<span class="n">{_text(_digits(value))}'
        f'<span class="lbl">[{_text(label)}]</span></span>'
    )


def cell_variable(
    condition: Mapping[str, Any], baseline: Mapping[str, Any]
) -> str | None:
    """Returns the variable that one cell varies away from the baseline.

    Args:
        condition: The condition of the cell.
        baseline: The baseline condition of the run.

    Returns:
        BASELINE when the cell repeats the baseline, the name of the one
        variable that differs, or None when several differ. A cell of the full
        grid varies several variables at once, so it attributes loss to none of
        them (thinkbook section 8).
    """
    differs = [
        name for name in VARIABLES if _value(condition[name]) != _value(baseline[name])
    ]
    if not differs:
        return BASELINE
    if len(differs) == 1:
        return differs[0]
    return None


def _pass_cells(
    cells: Sequence[Mapping[str, Any]], pass_name: str
) -> list[tuple[int, Mapping[str, Any]]]:
    """Returns every valid cell of one pass, with its index in the record."""
    return [
        (index, cell)
        for index, cell in enumerate(cells)
        if cell.get("pass") == pass_name and cell.get("valid") is True
    ]


def baseline_points(
    cells: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, Any],
    pass_name: str,
) -> list[tuple[int, float]]:
    """Returns the cell and the loss ratio of each baseline repeat of one pass.

    The ratios come from the loss quantity that the pass states, which the
    drift band of that pass reads. The cell of each ratio names the key of the
    record that states it, so a report links the ratio to that key.

    Args:
        cells: The cells section of the record.
        baseline: The baseline condition of the run.
        pass_name: The pass, broadcast or unicast.

    Returns:
        One pair of cell and ratio per valid baseline cell of that pass that
        states the quantity.
    """
    quantity = PASS_QUANTITY[pass_name]
    points: list[tuple[int, float]] = []
    for index, cell in _pass_cells(cells, pass_name):
        if cell_variable(cell["condition"], baseline) != BASELINE:
            continue
        loss = cell.get(quantity)
        if isinstance(loss, Mapping):
            points.append((index, _value(loss["ratio"])))
    return points


def baseline_ratios(
    cells: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, Any],
    pass_name: str,
) -> list[float]:
    """Returns the loss ratios of the baseline repeats of one pass.

    Args:
        cells: The cells section of the record.
        baseline: The baseline condition of the run.
        pass_name: The pass, broadcast or unicast.

    Returns:
        One ratio per valid baseline cell of that pass that states the
        quantity.
    """
    return [ratio for _index, ratio in baseline_points(cells, baseline, pass_name)]


def drift_band(
    cells: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, Any],
    pass_name: str,
) -> float:
    """Returns the drift band of one pass, as a width.

    The band is the difference between the highest and the lowest ratio of the
    loss quantity of that pass, across its valid baseline cells. A pass with
    fewer than two such cells has a band of 0 (decision
    2026-11-17-the-drift-band-of-a-unicast-pass.md).

    Args:
        cells: The cells section of the record.
        baseline: The baseline condition of the run.
        pass_name: The pass, broadcast or unicast.

    Returns:
        The width of the band, as a share of frames.
    """
    ratios = baseline_ratios(cells, baseline, pass_name)
    if len(ratios) < MINIMUM_BASELINE_CELLS:
        return 0.0
    return max(ratios) - min(ratios)


def _points(
    cells: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, Any],
    pass_name: str,
    variable: str,
    quantity: str,
) -> list[dict[str, Any]]:
    """Collects the points of one chart, in the order of the variable."""
    found: list[dict[str, Any]] = []
    for index, cell in _pass_cells(cells, pass_name):
        if cell_variable(cell["condition"], baseline) != variable:
            continue
        loss = cell.get(quantity)
        if not isinstance(loss, Mapping):
            continue
        found.append(
            {
                "index": index,
                "x": _value(cell["condition"][variable]),
                "ratio": _value(loss["ratio"]),
                "low": _value(loss["wilson_interval_low"]),
                "high": _value(loss["wilson_interval_high"]),
            }
        )
    found.sort(key=lambda point: point["x"])
    return found


def moved_loss(
    cells: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, Any],
    pass_name: str,
) -> list[dict[str, Any]]:
    """Names the variables that moved loss on one pass.

    A variable moved loss when two of its valid cells hold Wilson intervals
    that do not overlap and the difference between their ratios exceeds the
    drift band of that pass. Both tests read the record and nothing else, so
    two readers of one record name the same variables (thinkbook section 10).

    Args:
        cells: The cells section of the record.
        baseline: The baseline condition of the run.
        pass_name: The pass, broadcast or unicast.

    Returns:
        One entry per variable that moved loss, each naming the variable, the
        two cells, and their ratios.
    """
    band = drift_band(cells, baseline, pass_name)
    quantity = PASS_QUANTITY[pass_name]
    moved: list[dict[str, Any]] = []

    for variable in VARIABLES:
        points = _points(cells, baseline, pass_name, variable, quantity)
        best: dict[str, Any] | None = None
        for low_point in points:
            for high_point in points:
                if low_point is high_point:
                    continue
                separated = low_point["high"] < high_point["low"]
                difference = high_point["ratio"] - low_point["ratio"]
                if not separated or difference <= band:
                    continue
                if best is None or difference > best["difference"]:
                    best = {
                        "variable": variable,
                        "low": low_point,
                        "high": high_point,
                        "difference": difference,
                    }
        if best is not None:
            moved.append(best)
    return moved


def _axis_maximum(points: Sequence[Mapping[str, Any]], band_high: float) -> float:
    """Returns the top of the vertical axis of one chart."""
    highest = max([point["high"] for point in points] + [band_high], default=0.0)
    if highest <= 0.0:
        return 1.0
    return highest * 1.1


def _chart(
    title: str,
    points: Sequence[Mapping[str, Any]],
    band_low: float,
    band_high: float,
    extra: Sequence[Mapping[str, Any]] = (),
) -> str:
    """Draws one chart as inline SVG, with no script and no external asset.

    Args:
        title: The heading of the horizontal axis.
        points: The points of the loss quantity of this pass.
        band_low: The lowest baseline ratio, which shades the drift band.
        band_high: The highest baseline ratio.
        extra: A second series, such as the message loss of a payload chart.

    Returns:
        The chart as one SVG element.
    """
    top = _axis_maximum(points, band_high)
    plot_width = _CHART_WIDTH - _CHART_LEFT - _CHART_RIGHT
    plot_height = _CHART_HEIGHT - _CHART_TOP - _CHART_BOTTOM

    def y_of(ratio: float) -> float:
        return _CHART_TOP + plot_height * (1.0 - (ratio / top))

    def x_of(position: int, count: int) -> float:
        if count <= 1:
            return _CHART_LEFT + (plot_width / 2.0)
        step = plot_width / float(count - 1)
        return _CHART_LEFT + (step * position)

    parts: list[str] = [
        f'<svg class="chart" viewBox="0 0 {_CHART_WIDTH} {_CHART_HEIGHT}" '
        f'role="img" aria-label="{_text(title)}">'
    ]

    if band_high > band_low:
        height = y_of(band_low) - y_of(band_high)
        parts.append(
            f'<rect class="band" x="{_CHART_LEFT}" y="{y_of(band_high):.1f}" '
            f'width="{plot_width}" height="{height:.1f}"></rect>'
        )

    parts.append(
        f'<line class="axis" x1="{_CHART_LEFT}" y1="{_CHART_TOP}" '
        f'x2="{_CHART_LEFT}" y2="{_CHART_TOP + plot_height}"></line>'
        f'<line class="axis" x1="{_CHART_LEFT}" y1="{_CHART_TOP + plot_height}" '
        f'x2="{_CHART_LEFT + plot_width}" y2="{_CHART_TOP + plot_height}"></line>'
    )
    parts.append(
        f'<text class="tick" x="{_CHART_LEFT - 8}" y="{_CHART_TOP + 4}" '
        f'text-anchor="end">{_text(_digits(top))}</text>'
        f'<text class="tick" x="{_CHART_LEFT - 8}" '
        f'y="{_CHART_TOP + plot_height}" text-anchor="end">0</text>'
    )

    count = len(points)
    for position, point in enumerate(points):
        x = x_of(position, count)
        parts.append(
            f'<line class="iv" x1="{x:.1f}" y1="{y_of(point["high"]):.1f}" '
            f'x2="{x:.1f}" y2="{y_of(point["low"]):.1f}"></line>'
            f'<circle class="pt" cx="{x:.1f}" cy="{y_of(point["ratio"]):.1f}" '
            f'r="3"></circle>'
            f'<text class="tick" x="{x:.1f}" '
            f'y="{_CHART_TOP + plot_height + 16}" text-anchor="middle">'
            f"{_text(_digits(point['x']))}</text>"
        )

    for position, point in enumerate(extra):
        x = x_of(position, len(extra))
        parts.append(
            f'<rect class="msg" x="{x - 3:.1f}" '
            f'y="{y_of(point["ratio"]):.1f}" width="6" height="6"></rect>'
        )

    parts.append(
        f'<text class="axis-title" x="{_CHART_LEFT + (plot_width / 2):.0f}" '
        f'y="{_CHART_HEIGHT - 8}" text-anchor="middle">{_text(title)}</text>'
        "</svg>"
    )
    return "".join(parts)


def _histogram(counts: Sequence[Any], title: str) -> str:
    """Draws one histogram of BOL_HISTOGRAM_BINS bins as inline SVG."""
    values = [float(count) for count in counts]
    top = max(values, default=0.0) or 1.0
    width = _CHART_WIDTH
    height = _HISTOGRAM_HEIGHT
    bar = width / float(max(len(values), 1))
    parts = [
        f'<svg class="hist" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{_text(title)}">'
    ]
    for position, value in enumerate(values):
        bar_height = (height - 18) * (value / top)
        parts.append(
            f'<rect class="bar" x="{position * bar:.1f}" '
            f'y="{height - 18 - bar_height:.1f}" width="{bar - 1:.1f}" '
            f'height="{bar_height:.1f}"></rect>'
        )
    parts.append(
        f'<text class="tick" x="0" y="{height - 4}">bin 0</text>'
        f'<text class="tick" x="{width}" y="{height - 4}" text-anchor="end">'
        f"bin {len(values) - 1}</text></svg>"
    )
    return "".join(parts)


_STYLE = """
:root { color-scheme: light dark; }
body { font-family: system-ui, sans-serif; line-height: 1.5; margin: 0 auto;
       max-width: 52rem; padding: 2rem 1rem; }
h1 { font-size: 1.5rem; } h2 { font-size: 1.15rem; margin-top: 2rem; }
h3 { font-size: 1rem; margin-bottom: 0.25rem; }
table { border-collapse: collapse; width: 100%; }
th, td { border-bottom: 1px solid #8884; padding: 0.3rem 0.4rem;
         text-align: left; vertical-align: top; }
td { overflow-wrap: anywhere; }
.n { white-space: nowrap; }
.lbl { font-size: 0.75em; margin-left: 0.25rem; text-decoration: none;
       color: inherit; opacity: 0.65; }
a.lbl:hover, a.lbl:focus { text-decoration: underline; opacity: 1; }
.chart, .hist { width: 100%; height: auto; }
.axis { stroke: currentColor; stroke-width: 1; }
.tick, .axis-title { fill: currentColor; font-size: 11px; }
.iv { stroke: currentColor; stroke-width: 2; }
.pt { fill: currentColor; }
.band { fill: currentColor; opacity: 0.12; }
.msg { fill: none; stroke: currentColor; stroke-width: 1.5; }
.bar { fill: currentColor; opacity: 0.65; }
.limits li { margin-bottom: 0.25rem; }
.legend dt { font-weight: 600; margin-top: 0.4rem; }
.note { border-left: 3px solid #8886; margin: 1rem 0; padding: 0.25rem 0.75rem; }
"""


def _condition_rows(
    setup: Mapping[str, Any],
    firmware: Mapping[str, Any],
    run: Mapping[str, Any],
    record_name: str,
) -> str:
    """Builds the rows of the test condition table."""
    rows = [
        ("Firmware path", _text(firmware["firmware_path"])),
        ("ELF SHA-256", _text(firmware["elf_sha256"])),
        ("ESP-IDF version", _text(firmware["idf_version"])),
        (
            "ESP-NOW version",
            labelled(
                firmware["espnow_version"],
                "/firmware/espnow_version/value",
                record_name,
            ),
        ),
        (
            "Packet payload limit (bytes)",
            labelled(
                firmware["payload_limit_bytes"],
                "/firmware/payload_limit_bytes/value",
                record_name,
            ),
        ),
        (
            "PHY rate (Mbps)",
            labelled(setup["phy_rate_mbps"], "/setup/phy_rate_mbps/value", record_name),
        ),
        ("Country code", _text(setup["country_code"])),
        ("Run mode", _text(run["mode"])),
        ("Power save", _text(setup["power_save"])),
        ("Bluetooth controller", _text(setup["bluetooth_controller"])),
        ("Baseline source", _text(setup["baseline_source"])),
    ]
    for name in VARIABLES:
        # Only the first letter falls, so a unit such as dBm keeps its case.
        title = VARIABLE_TITLES[name]
        rows.append(
            (
                f"Baseline {title[:1].lower()}{title[1:]}",
                labelled(
                    setup["baseline"][name],
                    f"/setup/baseline/{name}/value",
                    record_name,
                ),
            )
        )
    return "".join(f"<tr><th>{key}</th><td>{value}</td></tr>" for key, value in rows)


def _declared_rows(declared: Mapping[str, Any], record_name: str) -> str:
    """Builds the rows of the declared geometry table."""
    rows = []
    for key in sorted(declared):
        entry = declared[key]
        value = _text(entry.get("value", ""))
        label = _text(entry.get("label", "declared"))
        href = f"{_text(record_name)}#{_text(f'/declared/{key}/value')}"
        shown = value or "<em>not stated</em>"
        rows.append(
            f"<tr><th>{_text(key)}</th><td>{shown}"
            f'<a class="lbl" href="{href}">[{label}]</a></td></tr>'
        )
    return "".join(rows)


def _paragraph(
    cells: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, Any],
    pass_name: str,
    record_name: str,
) -> str:
    """Builds the paragraph that names the variables that moved loss."""
    band = drift_band(cells, baseline, pass_name)
    moved = moved_loss(cells, baseline, pass_name)
    quantity = QUANTITY_TITLES[PASS_QUANTITY[pass_name]]
    quantity_key = PASS_QUANTITY[pass_name]
    points = baseline_points(cells, baseline, pass_name)

    lines = [
        f"<h3>The {_text(pass_name)} pass</h3>",
        f"<p>The drift band is {labelled_no_link(band, 'derived')} of "
        f"{_text(quantity)}, from {len(points)} baseline cells.</p>",
    ]
    if points:
        low_cell, low_ratio = min(points, key=lambda point: point[1])
        high_cell, high_ratio = max(points, key=lambda point: point[1])
        lowest = labelled(
            {"value": low_ratio, "label": "derived"},
            f"/cells/{low_cell}/{quantity_key}/ratio/value",
            record_name,
        )
        highest = labelled(
            {"value": high_ratio, "label": "derived"},
            f"/cells/{high_cell}/{quantity_key}/ratio/value",
            record_name,
        )
        lines.append(f"<p>The baseline loss runs from {lowest} to {highest}.</p>")
    if not moved:
        lines.append("<p>No variable moved loss on this pass.</p>")
        return "".join(lines)

    items = []
    for entry in moved:
        variable = entry["variable"]
        parts = []
        for point in (entry["low"], entry["high"]):
            index = point["index"]
            pointer = f"/cells/{index}/{quantity_key}/ratio/value"
            shown = labelled(
                {"value": point["ratio"], "label": "derived"}, pointer, record_name
            )
            parts.append(f"{_text(_digits(point['x']))} states {shown}")
        items.append(
            f"<li>{_text(VARIABLE_TITLES[variable])}: " + " and ".join(parts) + ".</li>"
        )
    lines.append(
        "<p>These variables moved loss on this pass.</p><ul>" + "".join(items) + "</ul>"
    )
    return "".join(lines)


def _charts(
    cells: Sequence[Mapping[str, Any]],
    setup: Mapping[str, Any],
    pass_name: str,
    payload_limit_bytes: float,
) -> str:
    """Builds one chart per swept variable of one pass.

    Args:
        cells: The cells section of the record.
        setup: The setup section, which holds the baseline.
        pass_name: The pass, broadcast or unicast.
        payload_limit_bytes: The packet payload limit L. The payload chart adds
            message loss for a payload above it (thinkbook section 10).

    Returns:
        The charts of this pass.
    """
    baseline = setup["baseline"]
    quantity = PASS_QUANTITY[pass_name]
    ratios = baseline_ratios(cells, baseline, pass_name)
    band_low = min(ratios) if ratios else 0.0
    band_high = max(ratios) if ratios else 0.0
    sections: list[str] = []

    for variable in VARIABLES:
        points = _points(cells, baseline, pass_name, variable, quantity)
        if not points:
            continue
        extra: list[dict[str, Any]] = []
        note = ""
        if variable == "payload_bytes":
            message_points = _points(
                cells, baseline, pass_name, variable, "message_loss"
            )
            extra = [
                point for point in message_points if point["x"] > payload_limit_bytes
            ]
            if extra:
                note = "<p>The open squares state message loss.</p>"
        sections.append(
            f"<h3>{_text(VARIABLE_TITLES[variable])}</h3>"
            f"<p>{_text(_sentence_case(QUANTITY_TITLES[quantity]))}.</p>"
            + _chart(VARIABLE_TITLES[variable], points, band_low, band_high, extra)
            + note
        )
    if not sections:
        return (
            f"<p>This run states no cell of a swept variable on the "
            f"{_text(pass_name)} pass.</p>"
        )
    return "<p>The shaded range is the drift band.</p>" + "".join(sections)


def _histograms(cells: Sequence[Mapping[str, Any]], record_name: str) -> str:
    """Builds the send-to-callback histogram of every unicast pass."""
    sections: list[str] = []
    for index, cell in _pass_cells(cells, "unicast"):
        sender = cell.get("sender")
        if not isinstance(sender, Mapping):
            continue
        entry = sender.get("send_to_callback_us_histogram")
        if not isinstance(entry, Mapping):
            continue
        counts = entry.get("value")
        if not isinstance(counts, list):
            continue
        href = (
            f"{_text(record_name)}"
            f"#{_text(f'/cells/{index}/sender/send_to_callback_us_histogram/value')}"
        )
        sections.append(
            f"<h3>Cell {_text(cell['cell_id'])}"
            f'<a class="lbl" href="{href}">[{_text(entry.get("label", ""))}]</a></h3>'
            + _histogram(counts, f"Send-to-callback time of cell {cell['cell_id']}")
        )
    if not sections:
        return ""
    return (
        "<h2>Send-to-callback time</h2><p>One histogram per unicast pass. The "
        "16 bins double in width.</p>" + "".join(sections)
    )


def render(document: Mapping[str, Any], record_name: str) -> str:
    """Builds the report of one run record.

    Args:
        document: The run record, as `write_record` wrote it.
        record_name: The file name of that record, which every link uses.

    Returns:
        One static HTML page.

    Raises:
        BolisReportError: The record carries no section that a report needs.
    """
    for section in ("run", "firmware", "nodes", "setup", "declared", "cells"):
        if section not in document:
            raise BolisReportError(
                f"the record states no {section} section, so no report follows."
            )

    run = document["run"]
    setup = document["setup"]
    cells = document["cells"]
    passes = [name for name in ("broadcast", "unicast") if _pass_cells(cells, name)]

    stopped = ""
    if run.get("status") != "complete":
        stopped = (
            f'<p class="note">This run stopped before the end of its plan. '
            f"Reason: {_text(run.get('stopped_reason', 'none stated'))}</p>"
        )

    body = [
        f"<h1>Bolis run {_text(run['run_id'])}</h1>",
        f"<p>{_text(CLAIM_LIMIT)}</p>",
        stopped,
        f"<p>Started {_text(run['started_at'])}, ended {_text(run['ended_at'])}. "
        f"Plan {_text(run['plan'])}, mode {_text(run['mode'])}, Bolis "
        f"{_text(run['bolis_version'])}. Seed "
        f"{labelled(run['seed'], '/run/seed/value', record_name)}.</p>",
        "<h2>Test condition</h2><table>"
        + _condition_rows(setup, document["firmware"], run, record_name)
        + "</table>",
        "<h2>Declared geometry</h2><table>"
        + _declared_rows(document["declared"], record_name)
        + "</table>",
    ]

    payload_limit_bytes = _value(document["firmware"]["payload_limit_bytes"])
    for pass_name in passes:
        body.append(f"<h2>Loss by variable in {_text(pass_name)} pass</h2>")
        body.append(_charts(cells, setup, pass_name, payload_limit_bytes))

    body.append("<h2>What moved loss</h2>")
    for pass_name in passes:
        body.append(_paragraph(cells, setup["baseline"], pass_name, record_name))

    body.append(_histograms(cells, record_name))

    body.append(
        '<h2>Coverage and limits</h2><ul class="limits">'
        + "".join(f"<li>{_text(limit)}</li>" for limit in LIMITS)
        + "</ul>"
    )
    body.append(
        '<h2>Origin labels</h2><dl class="legend">'
        + "".join(
            f"<dt>[{_text(name)}]</dt><dd>{_text(meaning)}</dd>"
            for name, meaning in LABEL_LEGEND
        )
        + "</dl>"
        f'<p>Run record: <a href="{_text(record_name)}">{_text(record_name)}</a></p>'
    )

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Bolis run {_text(run['run_id'])}</title>"
        f"<style>{_STYLE}</style></head><body>" + "".join(body) + "</body></html>\n"
    )


def report_path(directory: Path, run_id: int) -> Path:
    """Returns the path of the report of one run.

    Args:
        directory: The directory that the host writes into.
        run_id: The run ID of this run.

    Returns:
        The path, beside the record and with the same stem.
    """
    return directory / f"bolis-{run_id}.html"


def write_report(document: Mapping[str, Any], directory: Path) -> Path:
    """Writes the report of one run beside its record.

    Args:
        document: The run record, as `write_record` wrote it.
        directory: The directory that holds the record of this run.

    Returns:
        The path of the report that the host wrote.

    Raises:
        BolisReportError: The record carries no section that a report needs, or
            the report did not reach the file.
    """
    run_id = document.get("run", {}).get("run_id")
    if not isinstance(run_id, int) or isinstance(run_id, bool):
        raise BolisReportError(f"the run ID is {run_id!r}, which names no report file.")

    path = report_path(directory, run_id)
    page = render(document, f"bolis-{run_id}.json")
    temporary = path.with_name(f"{path.name}.part")
    try:
        temporary.write_text(page, encoding="utf-8")
        temporary.replace(path)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise BolisReportError(
            f"the host did not write the report {path}. The system reported: {error}"
        ) from error
    return path
