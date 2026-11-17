"""Tests for the labeled mockup report that the repository shows.

Specification section 6 states that the repository shows a mockup with
placeholders until a verification pair passes, and that the mockup states that
it is a mockup. These cases hold the page to both, and to the rule that Bolis
invents no number.
"""

import re
from pathlib import Path

from bolis.mockup import (
    MOCKUP_NOTICE,
    PLACEHOLDER,
    placeholder,
    render_mockup,
    write_mockup,
)
from bolis.report import CLAIM_LIMIT, LABEL_LEGEND, LIMITS

# The page that the repository shows.
COMMITTED_PAGE = Path(__file__).resolve().parents[2] / "docs" / "mockup-report.html"

# The three tokens that carry a digit and state no measurement. The first is
# the unit of a transmit power set value, the second belongs to the PHY rate
# limit of specification section 4, and the third is the name of a hash.
ALLOWED_DIGIT_TOKENS = frozenset({"0.25", "1", "SHA-256"})


def visible_text(page: str) -> str:
    """Returns the text that a reader of the page sees.

    Drops the stylesheet, the charts, and every tag, so a case reads the prose
    and the tables rather than the geometry.

    Args:
        page: The rendered page.

    Returns:
        The visible text, with runs of space collapsed.
    """
    body = page.split("</style>", 1)[1]
    body = re.sub(r"<svg.*?</svg>", " ", body, flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    return re.sub(r"\s+", " ", body).strip()


def test_the_page_states_that_it_is_a_mockup() -> None:
    """Specification section 6 requires the sentence."""
    page = render_mockup()

    assert MOCKUP_NOTICE in page
    assert "This page is a mockup" in page
    assert "Mockup" in page


def test_the_page_states_no_measurement() -> None:
    """A mockup carries placeholders, and Bolis invents no number."""
    text = visible_text(render_mockup())

    found = set(re.findall(r"\S*\d+\S*", text))
    assert found <= ALLOWED_DIGIT_TOKENS, (
        f"the page states {found - ALLOWED_DIGIT_TOKENS}"
    )


def test_every_value_sits_in_angle_brackets() -> None:
    """A reader cannot mistake a placeholder for a value that a run produced."""
    text = visible_text(render_mockup())

    assert PLACEHOLDER.strip("<>") in text
    # The page writes its placeholders as escaped angle brackets, so the text
    # that a reader sees holds the brackets rather than a bare word.
    assert "&lt;placeholder&gt;" in text
    assert "&lt;run id&gt;" in text
    assert "&lt;timestamp&gt;" in text


def test_the_page_carries_the_claim_limit_and_the_three_limits() -> None:
    """A mockup states the limits that every report states."""
    page = render_mockup()

    assert CLAIM_LIMIT in page
    for limit in LIMITS:
        assert limit in page


def test_the_page_carries_the_legend_of_the_four_labels() -> None:
    """Section 12 calls the artifact a labeled mockup report."""
    page = render_mockup()

    for name, meaning in LABEL_LEGEND:
        assert f"[{name}]" in page
        assert meaning in page


def test_the_page_states_what_replaces_it() -> None:
    """A reader learns that a passing verification pair replaces the page."""
    text = visible_text(render_mockup())

    assert "until a verification pair passes" in text
    assert "later calendar day" in text


def test_the_page_runs_nothing_and_loads_nothing() -> None:
    """The report rules keep one static file with no network request."""
    page = render_mockup()

    assert "<script" not in page
    assert "http://" not in page
    assert "https://" not in page
    assert "innerHTML" not in page


def test_a_placeholder_carries_its_label_only_when_the_value_has_one() -> None:
    """Text that states no quantity carries no origin label."""
    assert "[measured]" in placeholder("measured")
    assert "[" not in placeholder()


def test_the_committed_page_matches_the_renderer() -> None:
    """The page that the repository shows cannot drift from this module.

    A reader of the repository sees `docs/mockup-report.html`. Regenerate it
    with `python3 -m bolis.mockup docs/mockup-report.html` after a change to
    the mockup or to the text that it shares with a report.
    """
    assert COMMITTED_PAGE.is_file(), f"{COMMITTED_PAGE} is absent"
    assert COMMITTED_PAGE.read_text(encoding="utf-8") == render_mockup()


def test_write_mockup_writes_the_page(tmp_path: Path) -> None:
    """The writer puts the page where its caller names."""
    path = write_mockup(tmp_path / "mockup.html")

    assert path.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
