"""The labeled mockup report that the repository shows.

Specification section 6 states that the repository shows a mockup with
placeholders until a verification pair passes, and that the mockup states that
it is a mockup. Section 12 lists a labeled mockup report among the done
conditions.

The mockup carries no number. Every value sits in angle brackets, beside the
origin label that the value will carry once a run produces it, so a reader sees
the shape of a report without reading a measurement that no bench produced.

The page reuses the text and the style of `bolis.report`, so the mockup cannot
drift away from the report that a run writes. `docs/mockup-report.html` holds
the rendered page, and a test keeps that file equal to this renderer.

Regenerate the committed page with:

    python3 -m bolis.mockup docs/mockup-report.html
"""

import html
import sys
from pathlib import Path

from bolis.report import (
    _CHART_BOTTOM,
    _CHART_HEIGHT,
    _CHART_LEFT,
    _CHART_RIGHT,
    _CHART_TOP,
    _CHART_WIDTH,
    _STYLE,
    CLAIM_LIMIT,
    LABEL_LEGEND,
    LIMITS,
    VARIABLE_TITLES,
)

# Every value of the mockup. The angle brackets follow the rule that a value
# nobody has produced is written as a placeholder and named as one.
PLACEHOLDER = "<placeholder>"

# The sentence that specification section 6 requires of the page.
MOCKUP_NOTICE = (
    "This page is a mockup. No run produced it, and it states no measurement. "
    "Every value below is a placeholder beside its origin label."
)

# What replaces the mockup, from specification section 6 and decision record
# 2026-10-01-reproducibility-verification.md.
MOCKUP_REPLACEMENT = (
    "The repository shows this page until a verification pair passes. A pair is "
    "two runs on one bench and one declared geometry, with both nodes removed "
    "and placed again between them, and the second run on a later calendar day. "
    "The pair passes when the baseline loss intervals of the two runs overlap "
    "and the lists of variables that moved loss are identical."
)

# The rows of the test condition table, in the order a report states them.
CONDITION_ROWS = (
    ("Firmware path", None),
    ("ELF SHA-256", None),
    ("ESP-IDF version", None),
    ("ESP-NOW version", "measured"),
    ("Packet payload limit (bytes)", "measured"),
    ("PHY rate (Mbps)", "configured"),
    ("Country code", None),
    ("Run mode", None),
    ("Power save", None),
    ("Bluetooth controller", None),
    ("Baseline source", None),
    ("Baseline channel", "configured"),
    ("Baseline transmit power (units of 0.25 dBm)", "configured"),
    ("Baseline payload size (bytes)", "configured"),
)

# The five entries of the declared section of thinkbook section 9.
DECLARED_ROWS = ("antenna", "distance", "enclosure", "orientation", "surroundings")

# The style that the banner of the mockup adds to the style of a report.
_MOCKUP_STYLE = """
.mockup { background: #fde68a33; border: 1px solid #b4530088; border-radius: 4px;
          margin: 1rem 0; padding: 0.75rem 1rem; }
.mockup strong { display: block; margin-bottom: 0.25rem; }
.ph { font-family: ui-monospace, monospace; white-space: nowrap; }
.empty { fill: currentColor; font-size: 12px; opacity: 0.6; }
"""


def _text(value: object) -> str:
    """Escapes one value for the body of the page."""
    return html.escape(str(value), quote=True)


def placeholder(label: str | None = None) -> str:
    """Renders one placeholder, with the label that its value will carry.

    Args:
        label: The origin label of the value, or None for text that carries no
            label because it states no quantity.

    Returns:
        The placeholder, and its label when the value carries one.
    """
    shown = f'<span class="ph">{_text(PLACEHOLDER)}</span>'
    if label is None:
        return shown
    return f'{shown}<span class="lbl">[{_text(label)}]</span>'


def _empty_chart(title: str) -> str:
    """Draws the axes of one chart with no point and no band.

    A mockup states no loss, so the chart shows the frame that a report fills
    and says that it holds no data.

    Args:
        title: The heading of the horizontal axis.

    Returns:
        The chart as one SVG element.
    """
    plot_width = _CHART_WIDTH - _CHART_LEFT - _CHART_RIGHT
    plot_height = _CHART_HEIGHT - _CHART_TOP - _CHART_BOTTOM
    bottom = _CHART_TOP + plot_height
    middle_x = _CHART_LEFT + (plot_width / 2)
    return (
        f'<svg class="chart" viewBox="0 0 {_CHART_WIDTH} {_CHART_HEIGHT}" '
        f'role="img" aria-label="{_text(title)}, with no data">'
        f'<line class="axis" x1="{_CHART_LEFT}" y1="{_CHART_TOP}" '
        f'x2="{_CHART_LEFT}" y2="{bottom}"></line>'
        f'<line class="axis" x1="{_CHART_LEFT}" y1="{bottom}" '
        f'x2="{_CHART_LEFT + plot_width}" y2="{bottom}"></line>'
        f'<text class="tick" x="{_CHART_LEFT - 8}" y="{_CHART_TOP + 4}" '
        f'text-anchor="end">&lt;high&gt;</text>'
        f'<text class="tick" x="{_CHART_LEFT - 8}" y="{bottom}" '
        f'text-anchor="end">&lt;low&gt;</text>'
        f'<text class="empty" x="{middle_x:.0f}" '
        f'y="{_CHART_TOP + (plot_height / 2):.0f}" text-anchor="middle">'
        f"&lt;no data: this chart holds the points of a run&gt;</text>"
        f'<text class="axis-title" x="{middle_x:.0f}" y="{_CHART_HEIGHT - 8}" '
        f'text-anchor="middle">{_text(title)}</text>'
        "</svg>"
    )


def render_mockup() -> str:
    """Builds the labeled mockup report.

    Returns:
        One static HTML page that states no number.
    """
    condition = "".join(
        f"<tr><th>{_text(name)}</th><td>{placeholder(label)}</td></tr>"
        for name, label in CONDITION_ROWS
    )
    declared = "".join(
        f"<tr><th>{_text(name)}</th><td>{placeholder('declared')}</td></tr>"
        for name in DECLARED_ROWS
    )
    charts = "".join(
        f"<h3>{_text(title)}</h3>"
        f"<p>&lt;pass&gt; pass, &lt;loss quantity&gt;.</p>" + _empty_chart(title)
        for title in VARIABLE_TITLES.values()
    )
    legend = "".join(
        f"<dt>[{_text(name)}]</dt><dd>{_text(meaning)}</dd>"
        for name, meaning in LABEL_LEGEND
    )
    limits = "".join(f"<li>{_text(limit)}</li>" for limit in LIMITS)

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Bolis report mockup</title>"
        f"<style>{_STYLE}{_MOCKUP_STYLE}</style></head><body>"
        "<h1>Bolis run &lt;run id&gt;</h1>"
        f'<div class="mockup"><strong>Mockup</strong>{_text(MOCKUP_NOTICE)}</div>'
        f"<p>{_text(CLAIM_LIMIT)}</p>"
        "<p>Started &lt;timestamp&gt;, ended &lt;timestamp&gt;. Plan &lt;plan&gt;, "
        "mode &lt;mode&gt;, Bolis &lt;version&gt;. Seed "
        f"{placeholder('configured')}.</p>"
        f"<h2>Test condition</h2><table>{condition}</table>"
        f"<h2>Declared geometry</h2><table>{declared}</table>"
        "<h2>Loss by variable</h2>"
        "<p>The shaded range is the drift band.</p>"
        f"{charts}"
        "<h2>What moved loss</h2>"
        "<p>The drift band is "
        f"{placeholder('derived')} of &lt;loss quantity&gt;, from &lt;count&gt; "
        "baseline cells.</p>"
        "<p>A report names here the variables that moved loss, with the two "
        "cells of each one and their values.</p>"
        f'<h2>Coverage and limits</h2><ul class="limits">{limits}</ul>'
        f'<h2>Origin labels</h2><dl class="legend">{legend}</dl>'
        "<p>This page links to no record.</p>"
        f'<div class="mockup"><strong>What replaces this page</strong>'
        f"{_text(MOCKUP_REPLACEMENT)}</div>"
        "</body></html>\n"
    )


def write_mockup(path: Path) -> Path:
    """Writes the mockup to one path.

    Args:
        path: The file to write.

    Returns:
        The path that the renderer wrote.
    """
    path.write_text(render_mockup(), encoding="utf-8")
    return path


if __name__ == "__main__":
    # A developer entry point rather than a command of the CLI. Specification
    # section 5 names bolis flash and bolis run, and no third command.
    write_mockup(Path(sys.argv[1]))
