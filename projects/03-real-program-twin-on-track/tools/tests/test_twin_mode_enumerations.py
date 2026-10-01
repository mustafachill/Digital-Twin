"""The twin mode set is defined once, in `TwinMode.msg`, and re-typed in eleven places.

`uint8 MODE_VIRTUAL_LEAD=5` landed on 2026-08-29 and every document that
enumerates the mode set had to be edited by hand to keep agreeing with it.
Charter v1.9's own §14 entry records how that went: a `grep` found twelve
locations in nine files, `§3.1 was a third charter location that two reviews
missed`, a thirteenth was invisible to the instrument entirely, and a fourteenth
was found **wrong** rather than merely incomplete - `docs/onboarding/glossary.md`
introduced the modes as *"corresponding to the levels above"*, which was already
false before the sixth mode falsified it again.

That is P1's shape at the level of prose. One enumeration needing this many
places to agree cannot be kept true by care, and this project has already had a
stale one. So the set is parsed from the message and the documents are made to
answer to it.

**Membership is the cheap half. The load-bearing half is the two literal cells
below it.** A name-set assertion passes a tree in which `VIRTUAL_LEAD`'s Level
cell has been filled in with `L3`, and passes one in which `CLOSED_LOOP`'s row has
been rewritten to give the direction without the gate. Those are the two edits
[ADR-0011](../../docs/adr/0011-twin-maturity-model-and-modes.md)'s 2026-08-29
amendment names as fatal to itself: the amendment adds a mode carrying L3's
*direction* without L3's *validation gate*, and it says in terms that the argument
does **not** close on its own level table - it closes on charter §2's L3 row and on
`L5-twin-synchronization.md`'s `CLOSED_LOOP` row, *"and nowhere else"*. Two
sentences in two documents. If either is ever read as putting the direction alone
at L3, the mode has to be re-argued. Nothing was watching them.

Asserting a protected document's text is not editing it. Charter §12's protection
is exactly why a silent drift there would be the worst case: a document that
changes only by explicit decision is a document nobody re-reads.

A HOST TEST, deliberately, and the reasoning is
`test_interface_counts.py`'s rather than a new one - read it there. In short:
`cite_interfaces`' own tests run under `ament_add_pytest_test`, so they need a
container and a build, and the documents guarded here are edited from a macOS host
that has neither. A check inside a workspace package would also have to reach up
into the repository `docs/` tree, which would make a ROS package depend on the
documentation around it; `tools/tests/` already depends downward on the workspace,
which is the arrow that exists.

## What this check cannot see

- **`DivergenceMetrics.msg` is the thirteenth site and no parser reaches it.** It
  constrains the mode set in prose that names no constant: *"meaningful in SHADOW
  and VALIDATED; in SIM the fields are zero"*, with `VIRTUAL_LEAD` deliberately
  absent rather than excluded. It is a **partial list by design** - the file says
  so twice and files the remainder as an open L5 question - so membership is the
  wrong question to ask it, and a check keyed on bare words in a comment would fire
  on the sentence that says the list is partial. It is named here rather than
  silently missed. What would settle it is L5 answering whether divergence is
  defined under `VIRTUAL_LEAD`, not a regular expression.
- **Three sites name a subset on purpose and are excluded**, so a drift that
  *removes* a mode from the set will not be caught there:
  `docs/architecture/cross-cutting-safety.md`, `docs/operations/safety-procedures.md`
  and `cite_interfaces/srv/SetMode.srv`'s header each name the three dangerous
  transitions, not the mode set.
- **`docs/adr/` is not read.** An ADR records what was decided when it was written;
  ADR-0011's Decision still names five modes with an amendment note beside it, and
  that is correct. A membership check there would demand the record be rewritten,
  which is the opposite of what a decision record is for.
- **Charter §8's Phase 2 sentence is excluded, and it does not enumerate the set** -
  see `test_the_charter_sites_are_a_deliberate_pair` below, which is where that
  judgement is written down.
- **Nothing here checks that a mode *means* the same thing in two places.** Two
  documents may agree on six names and describe them differently. Only the two
  literal cells below are held to their wording, because only those two are
  load-bearing for a written argument.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The definition. Parsed from this file and nothing else: a `MODE_*` scan across
#: `cite_interfaces` also reaches `ConveyorState.msg`'s `MODE_STOPPED`,
#: `MODE_RUNNING` and `MODE_FAULTED`, which are belt states and not twin modes.
TWIN_MODE = REPO_ROOT / "workspace" / "src" / "cite_interfaces" / "msg" / "TwinMode.msg"

CHARTER = REPO_ROOT / "what-we-are-doing.md"
L5_DOCUMENT = REPO_ROOT / "docs" / "architecture" / "L5-twin-synchronization.md"
GLOSSARY = REPO_ROOT / "docs" / "onboarding" / "glossary.md"
INTERFACES_README = REPO_ROOT / "docs" / "interfaces" / "README.md"
BASELINE = REPO_ROOT / "workspace" / "src" / "cite_interfaces" / "test" / "interfaces.baseline"

#: `uint8 MODE_VIRTUAL_LEAD=5   # trailing comment`, in a `.msg` or quoted in a
#: fenced block. Anchored at the start of a line so the message's own continuation
#: comments, which are indented, cannot be read as declarations.
MODE_CONSTANT = re.compile(r"^uint8\s+MODE_([A-Z][A-Z0-9_]*)\s*=\s*(\d+)", re.MULTILINE)

#: A mode name as a document writes it: backticked, all capitals.
QUOTED_MODE = re.compile(r"`([A-Z][A-Z0-9_]*)`")

#: U+2014. `VIRTUAL_LEAD`'s and `REAL`'s Level cells hold this and nothing else.
EM_DASH = "—"

#: Headings this test keys on. Written out rather than matched loosely, so a
#: restructured document fails with "the heading moved" instead of silently
#: reading a different table.
CHARTER_LEVELS = "## 2. Twin maturity model"
CHARTER_SCOPE = "### 3.1 In scope"
CHARTER_MODES = "### L5 — Twin synchronization"
CHARTER_PHASE_2 = "### Phase 2 — Physical integration and twin synchronization (L1 → L2)"
MODE_TABLE = "### Operating modes"
GLOSSARY_MODES = "## Operating modes"
INTERFACES_ENUMS = "## Enumerations are constants, not strings"


def _read(path: Path) -> str:
    assert path.is_file(), f"{path} does not exist"
    return path.read_text(encoding="utf-8")


def declared_modes() -> tuple[str, ...]:
    """The mode set, in value order, as `TwinMode.msg` declares it."""
    found = [(int(value), name) for name, value in MODE_CONSTANT.findall(_read(TWIN_MODE))]
    assert found, (
        f"{TWIN_MODE} declares no `uint8 MODE_* = N` constants. Either it stopped being the "
        "definition of the twin mode set, or its syntax changed - resolve which before "
        "touching anything this test guards."
    )
    return tuple(name for _, name in sorted(found))


def _section(text: str, heading: str) -> list[str]:
    """The lines under `heading`, up to the next heading. Fenced blocks are opaque."""
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if line.strip() == heading]
    assert len(starts) == 1, (
        f"expected exactly one heading {heading!r}, found {len(starts)}. The document was "
        "restructured; this test keys on the heading and has to be re-pointed."
    )
    body: list[str] = []
    fenced = False
    for line in lines[starts[0] + 1 :]:
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("#"):
            break
        body.append(line)
    return body


def _first_table(lines: list[str], where: str) -> tuple[list[str], list[list[str]]]:
    """The header cells and the body rows of the first Markdown table in `lines`."""
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            rows.append([cell.strip() for cell in stripped.strip("|").split("|")])
        elif rows:
            break
    assert len(rows) >= 3, (
        f"{where} no longer contains a Markdown table with at least one body row. Either "
        "restore it or delete the assertion that guards it - a check pointed at a table "
        "that is not there proves nothing."
    )
    header, separator, *body = rows
    assert all(set(cell) <= set("-: ") and "-" in cell for cell in separator), (
        f"{where}: the second row of the table is not a separator, so the first row is not a "
        "header and the rows below are being read with an offset"
    )
    return header, body


def _plain(cell: str) -> str:
    """A table cell with Markdown emphasis and code marks removed."""
    return cell.replace("`", "").replace("*", "").strip()


def _table(path: Path, heading: str) -> tuple[list[str], list[list[str]]]:
    return _first_table(_section(_read(path), heading), f"{path.name} under {heading!r}")


def _row_for(path: Path, heading: str, key: str) -> list[str]:
    """The one body row whose first cell names `key`."""
    _header, body = _table(path, heading)
    matches = [row for row in body if _plain(row[0]) == key]
    assert len(matches) == 1, (
        f"{path.name}: the table under {heading!r} has {len(matches)} rows whose first cell "
        f"is {key!r}, expected exactly 1"
    )
    return matches[0]


# --------------------------------------------------------------------------- #
# The sites: every place that enumerates the whole set.
# --------------------------------------------------------------------------- #


def _table_keys(path: Path, heading: str) -> list[str]:
    """Mode names read from the first cell of each row - never from section prose.

    Both `L5-twin-synchronization.md` and `glossary.md` have paragraphs *below*
    their mode tables that name several modes in running text, including the
    paragraphs explaining why `VIRTUAL_LEAD` is not a level. A scan over the
    section would read those as members and fail on the check's own explanation.
    """
    _header, body = _table(path, heading)
    return [_plain(row[0]) for row in body]


def _charter_scope_cell() -> list[str]:
    """Charter §3.1's `Twin synchronization` row, which lists the set inline.

    This is the location charter v1.9 records as *"a third charter location that
    two reviews missed and a grep found"*.
    """
    row = _row_for(CHARTER, CHARTER_SCOPE, "Twin synchronization")
    return QUOTED_MODE.findall(" ".join(row[1:]))


def _quoted_constant_block(path: Path, heading: str) -> list[str]:
    """Mode names from a fenced block that quotes the declaration verbatim."""
    section = "\n".join(_section(_read(path), heading))
    return [name for name, _value in MODE_CONSTANT.findall(section)]


def _baseline_block() -> list[str]:
    """`interfaces.baseline`'s `TwinMode` stanza, which is indented under its key.

    The baseline is regenerated from `ros2 interface show` and compared inside the
    container, so it cannot drift undetected there. Checking it here gives the same
    signal on a host with no ROS and no build, which is where the message is edited.
    """
    key = "msg/TwinMode.msg"
    lines = _read(BASELINE).splitlines()
    starts = [index for index, line in enumerate(lines) if line.rstrip() == key]
    assert len(starts) == 1, f"{BASELINE} has {len(starts)} stanzas keyed {key!r}, expected 1"
    stanza: list[str] = []
    for line in lines[starts[0] + 1 :]:
        if line and not line.startswith(" "):
            break
        stanza.append(line.strip())
    return [name for name, _value in MODE_CONSTANT.findall("\n".join(stanza))]


@dataclass(frozen=True)
class Site:
    """One place that re-types the whole mode set, and how to read it back."""

    path: Path
    where: str
    modes: Callable[[], list[str]]


SITES = (
    Site(
        L5_DOCUMENT,
        f"the mode table under {MODE_TABLE!r}",
        lambda: _table_keys(L5_DOCUMENT, MODE_TABLE),
    ),
    Site(
        GLOSSARY,
        f"the mode table under {GLOSSARY_MODES!r}",
        lambda: _table_keys(GLOSSARY, GLOSSARY_MODES),
    ),
    Site(
        INTERFACES_README,
        f"the quoted constant block under {INTERFACES_ENUMS!r}",
        lambda: _quoted_constant_block(INTERFACES_README, INTERFACES_ENUMS),
    ),
    Site(BASELINE, "the 'msg/TwinMode.msg' stanza", _baseline_block),
    Site(CHARTER, "3.1's 'Twin synchronization' scope row", _charter_scope_cell),
    Site(
        CHARTER,
        f"5's mode table under {CHARTER_MODES!r}",
        lambda: _table_keys(CHARTER, CHARTER_MODES),
    ),
)


@pytest.mark.parametrize("site", SITES, ids=lambda site: f"{site.path.name}:{site.where}")
def test_every_enumeration_names_exactly_the_declared_modes(site: Site) -> None:
    declared = declared_modes()
    stated = site.modes()

    duplicates = sorted({name for name in stated if stated.count(name) > 1})
    assert not duplicates, f"{site.path.name}: {site.where} names {duplicates} more than once"

    missing = sorted(set(declared) - set(stated))
    extra = sorted(set(stated) - set(declared))
    assert not missing and not extra, (
        f"{site.path.name}: {site.where} disagrees with {TWIN_MODE.name}. "
        f"Missing from the document: {missing or 'none'}. "
        f"In the document and not in the message: {extra or 'none'}. "
        f"The message declares {list(declared)}."
    )


def test_the_declared_values_are_contiguous_and_unique() -> None:
    """A duplicated value would make every membership check above meaningless."""
    values = sorted(int(value) for _name, value in MODE_CONSTANT.findall(_read(TWIN_MODE)))
    assert values == list(range(len(values))), (
        f"{TWIN_MODE} declares mode values {values}, which are not 0..{len(values) - 1} "
        "without repetition - two names sharing a value are one mode on the wire"
    )


# --------------------------------------------------------------------------- #
# The two sentences ADR-0011's amendment rests on, and the empty cell that is a
# claim. A membership check passes every mutation below.
# --------------------------------------------------------------------------- #


def test_virtual_leads_level_cell_is_empty() -> None:
    """The em-dash **is** the claim: this mode sits at no maturity level."""
    header, _body = _table(L5_DOCUMENT, MODE_TABLE)
    assert _plain(header[-1]) == "Level", (
        f"{L5_DOCUMENT.name}: the last column of the mode table is "
        f"{_plain(header[-1])!r}, not 'Level' - the cell this test reads is not the one it means"
    )
    cell = _row_for(L5_DOCUMENT, MODE_TABLE, "VIRTUAL_LEAD")[-1]
    assert cell == EM_DASH, (
        f"{L5_DOCUMENT.name}: VIRTUAL_LEAD's Level cell reads {cell!r} and must be exactly "
        f"{EM_DASH!r}. The empty cell is the claim, not an omission: the mode carries L3's "
        "direction without L3's validation gate, and ADR-0011's 2026-08-29 amendment states "
        "that a level written here makes the amendment claim a level while denying it. "
        "If a level genuinely belongs here, the mode has to be re-argued first."
    )


def test_closed_loops_row_still_carries_the_level_and_the_gate() -> None:
    """One of the two documents ADR-0011's amendment closes on."""
    row = _row_for(L5_DOCUMENT, MODE_TABLE, "CLOSED_LOOP")
    assert (
        row[-1] == "L3"
    ), f"{L5_DOCUMENT.name}: CLOSED_LOOP's Level cell reads {row[-1]!r}, expected 'L3'"
    assert "validation gates it" in " ".join(row), (
        f"{L5_DOCUMENT.name}: CLOSED_LOOP's row no longer says its physical side is "
        "'commanded after virtual validation gates it'. This row is one of exactly two "
        "places that distinguish L3 the level from virtual-to-real the direction - "
        "ADR-0011's own level table gives the direction alone and says so. Stating the "
        "direction without the gate here retires the distinction VIRTUAL_LEAD depends on."
    )


def test_the_charters_l3_row_still_carries_the_validation_gate() -> None:
    """The other one. Charter §2 is protected; this reads it and never writes it."""
    row = _row_for(CHARTER, CHARTER_LEVELS, "L3")
    assert "validated in simulation and then commands" in " ".join(row), (
        f"{CHARTER.name}: §2's L3 row no longer reads 'Behaviour is validated in simulation "
        "and then commands the physical system'. That sentence is quoted by §2's own "
        "mode-is-not-a-level paragraph, by ADR-0011's amendment, by ADR-0041 Decision 2 and "
        "by the glossary's L3 row, and it is where the whole maturity argument for "
        "VIRTUAL_LEAD closes. Changing it is a charter change under §12, not an edit."
    )


def test_the_charter_sites_are_a_deliberate_pair() -> None:
    """Charter §8's Phase 2 sentence enumerates a *subset*, and must keep being able to.

    Item 3 of the task that produced this test asked for a judgement on the
    charter's three mode sites, made deliberately rather than by default. Two of
    the three are in `SITES` above: §3.1's scope row and §5's mode table are
    exhaustive enumerations by construction, and enforcing them is aligned with a
    written decision rather than merely convenient - ADR-0011's amendment requires
    the charter change naming a new mode to land *with* the constant *"rather than
    after it"*, which is precisely the window a red build would cover.

    §8's Phase 2 scope sentence is excluded because it is **not** an enumeration of
    the set, and this test states that in a form that fails if it ever becomes one
    by accident. It names the modes Phase 2 delivers and deliberately omits
    `CLOSED_LOOP`, because §8 places L3 - and therefore the validation gate - in
    Phase 5. Putting it in `SITES` would demand the charter assert something false
    about its own roadmap, and it is protected under §12 besides.
    """
    phase_2 = "\n".join(_section(_read(CHARTER), CHARTER_PHASE_2))
    declared = set(declared_modes())
    # Intersected with the declared set rather than taken raw: the same section
    # backticks `CITE_ALLOW_HARDWARE`, which this pattern cannot tell from a mode
    # name and which has nothing to do with the question being asked.
    named = set(QUOTED_MODE.findall(phase_2)) & declared
    assert named < declared, (
        f"{CHARTER.name}: the Phase 2 section now names every declared mode, {sorted(named)}. "
        "This test excludes it from the membership check on the grounds that it names a "
        "subset on purpose. If that stopped being true, re-take the judgement in this "
        "docstring - do not edit the charter to satisfy a test."
    )
    assert "CLOSED_LOOP" not in named, (
        f"{CHARTER.name}: the Phase 2 section now names CLOSED_LOOP. Phase 5 owns the L3 "
        "validation gate and CLOSED_LOOP is the mode defined by it, so either the roadmap "
        "moved or the sentence is wrong. Neither is this test's to decide."
    )
