"""The 0.14 real-time factor may be stated anywhere, provided it carries its condition.

The figure entered the tree on 2026-08-24 as a present-tense property of "the
development host" - no machine, no allocation, no method - and was then copied
into six places plus `CLAUDE.md`, each copy making it look better attested than
it was. `docs/measurements/2026-08-29-real-time-factor-conditions/` established
what it actually describes: this cell confined to about one CPU core. Unconfined,
the same host idles above real time.

ADR-0028's correction states the transferable rule - *"a measurement with no
condition attached cannot be contradicted, only re-taken"* - and this test is
that rule made mechanical for the one figure that has already cost the project a
wrong capability claim in `L2-control-and-hal.md` and a wrong attribution in
ADR-0028 itself.

**The rule enforced here is a citation rule, not a wording one.** A file that
states the figure in a real-time-factor context must name, somewhere in that same
file, the campaign that established the condition. It deliberately does not check
the sentence around the number: prose that a regular expression can grade is prose
written for the regular expression, and the failure mode being prevented is a
figure that travels without its source, not a figure phrased in a particular way.

Two things are deliberately outside the pattern:

- **`docs/measurements/` is not walked.** Campaign material is frozen once its
  first trial has run (`docs/measurements/README.md`), so a finding there is one
  no commit may act on. Two earlier campaigns' `criteria.md` do carry the bare
  figure, and they must keep carrying it: it is what they were written against.
- **The `~21 Hz` half of the pair is not matched.** It is the same measurement
  seen through a different instrument, but the places that quote it - ADR-0036
  in particular - quote it in order to forbid a use of it, and a check that fired
  on those would be arguing with the correction rather than enforcing it.

A HOST TEST. It reads files and needs no ROS, so it runs on the machine most of
this documentation is edited from, which is where the copies were made.
"""

from __future__ import annotations

import re
from pathlib import Path

from cite_tools.tree import our_files

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The campaign that established the condition. Named as a directory rather than
#: as a link, so a citation counts whether it is written as Markdown, as a bare
#: path in a Python comment, or as prose.
CAMPAIGN = "2026-08-29-real-time-factor-conditions"

#: The one document that states the figure together with its condition. Citing it
#: does not satisfy the rule below - the campaign is what a site must name, because
#: a document title can appear in a file for an unrelated reason and a campaign
#: directory cannot. `CLAUDE.md` is the worked example: it named this document in
#: its determinism bullet, which would have let the unconditioned figure two
#: sections further down pass unnoticed.
CANONICAL = Path("docs/architecture/cross-cutting-testing.md")

#: The heading of the canonical statement inside that document.
CANONICAL_HEADING = "Wall-clock ceilings, and the machine condition they were sized for"

#: `0.14`, and not `0.140`, `0.147`, `0.14 degrees` or `0.14°`. The degree cases
#: are real and nearby: ADR-0029 and the friction campaign both report a pad
#: turning 0.14° within a few lines of the words "real-time factor", so a pattern
#: that ignored the unit would fail on a measurement of an angle.
FIGURE = re.compile(r"(?<![\d.])0\.14(?![\d])(?!\s*(?:°|deg\b|degrees\b))")

#: What makes an occurrence a claim about real-time factor rather than a number
#: that happens to read 0.14. Matched against a window whose line breaks, comment
#: markers and Markdown emphasis have been flattened to spaces first: every site
#: this rule exists for wraps "real-time factor" across two lines, so a pattern
#: applied to raw lines matched none of them.
CONTEXT = re.compile(r"real[- _]time[ _]factor|\bRTF\b", re.IGNORECASE)

#: Line prefixes and emphasis that must not break a phrase apart. `#:` opens a
#: Sphinx-style comment in the scenario files; `*` and `` ` `` are Markdown. What
#: is left is collapsed to single spaces by `_flatten`, because a wrapped phrase
#: whose comment marker is removed still leaves two spaces where the pattern
#: expects one - which is how the two scenario files that started this escaped an
#: earlier version of this check.
NOISE = re.compile(r"[\s*_`>]+|(?<=\s)#:?")

#: How far either side of the number the context is looked for. Wide enough to
#: span a wrapped Markdown paragraph or a `#:` comment block, narrow enough that
#: it does not reach the next section.
WINDOW_LINES = 6

#: Paths that state the figure and are not making a claim with it, by exact
#: repository-relative path and with the reason attached.
EXEMPT = {
    #: A fixture for the English-only gate. Its sentence is assembled to carry an
    #: em dash, a degree sign and a plus-minus through that check; the figure is
    #: incidental punctuation-bearing text and asserts nothing about this cell.
    Path("tools/tests/test_english.py"),
    #: This file, which quotes the figure in order to describe the rule.
    Path("tools/tests/test_rtf_figure_conditions.py"),
}

#: Campaign directories are frozen once their first trial has run. See the module
#: docstring.
SKIP_PREFIX = Path("docs/measurements")


def _flatten(window: str) -> str:
    """One line, one space between words, no comment markers or emphasis."""
    return re.sub(r"\s+", " ", NOISE.sub(" ", window))


def _text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def _sites() -> dict[Path, list[int]]:
    """Every file stating the figure in a real-time-factor context, with line numbers."""
    found: dict[Path, list[int]] = {}
    for path in our_files(REPO_ROOT):
        relative = path.relative_to(REPO_ROOT)
        if relative in EXEMPT or relative.is_relative_to(SKIP_PREFIX):
            continue
        content = _text(path)
        if content is None or not FIGURE.search(content):
            continue
        lines = content.splitlines()
        hits = [
            number
            for number, line in enumerate(lines, start=1)
            if FIGURE.search(line)
            and CONTEXT.search(
                _flatten(
                    "\n".join(lines[max(0, number - 1 - WINDOW_LINES) : number + WINDOW_LINES])
                )
            )
        ]
        if hits:
            found[relative] = hits
    return found


def test_every_statement_of_the_figure_cites_its_condition() -> None:
    """A site quoting 0.14 as a real-time factor must point at where the condition is."""
    unattributed = {
        relative: numbers
        for relative, numbers in _sites().items()
        if CAMPAIGN not in (_text(REPO_ROOT / relative) or "")
    }
    assert not unattributed, (
        "these files state the 0.14 real-time factor without citing the condition it "
        f"holds under. Name {CAMPAIGN}/ in the file, or drop the number:\n"
        + "\n".join(
            f"  {relative}: line(s) {', '.join(str(n) for n in numbers)}"
            for relative, numbers in sorted(unattributed.items())
        )
    )


def test_the_figure_is_stated_with_its_condition_in_exactly_one_place() -> None:
    """The canonical statement exists, is where every other site says it is, and cites."""
    content = _text(REPO_ROOT / CANONICAL)
    assert content is not None, f"{CANONICAL} is missing"
    assert CANONICAL_HEADING in content, (
        f"{CANONICAL} no longer carries the canonical statement of the real-time factor. "
        "Every other site in the tree defers to it, so moving it means moving those too."
    )
    assert (
        CAMPAIGN in content
    ), f"{CANONICAL} states the figure and must cite {CAMPAIGN}/, which measured it."


def test_the_scenario_ceilings_defer_to_it() -> None:
    """Each scenario's ceilings are wall clock, so each must name where the basis is."""
    for name in ("bringup.py", "pick_and_place.py", "continuous_line.py"):
        content = _text(REPO_ROOT / "tests" / "scenarios" / name)
        assert content is not None, f"tests/scenarios/{name} is missing"
        assert CANONICAL.name in content or CAMPAIGN in content, (
            f"tests/scenarios/{name} declares wall-clock ceilings without pointing at the "
            "condition they were sized for. A reader hitting a timeout has to be able to "
            "find out that a starved host produces one with nothing broken."
        )
