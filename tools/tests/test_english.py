"""What the English-only check must catch, and — the half that decides its survival — what
it must stay quiet about.

P10 is a hard rule and nothing checked it until now. ADR-0035 records why the obvious
instrument is unusable: a non-ASCII check fires on 89 of 89 Markdown files in this
repository, because the prose is full of em dashes, box-drawing diagrams and degree signs. A
gate that fires on legitimate content is a gate somebody switches off, so the false-positive
tests below are not decoration — they are the reason the chosen signal is narrow, and they
are what fails if a later change widens it back towards "no non-ASCII".

Two things about how this file is written, both deliberate.

The signal comes from the **real** `.english-only.yaml`, not from a fixture. A toy signal
would let the shipped configuration drift away from the behaviour these tests claim to pin,
and what is under test is the policy. Only the tests about malformed configuration build
their own.

The Turkish fixtures are written as `\\u` escapes, so this file is ASCII where it matters and
does not trip the check it is testing. That is the same reason the configuration declares
code points rather than letters, and it is what keeps the exemption list at the one entry
that genuinely earns it rather than at four.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from pathlib import Path

import pytest

from cite_tools.english import CONFIG_NAME, Config, ConfigError, check, load_config, scan

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The one file ADR-0035 exempts, and the reason the escape hatch exists at all.
QUOTING_DOCUMENT = "docs/reference/v1-lessons.md"

#: The three Turkish letters the fixtures below need, as escapes. Spelling them out here
#: rather than inline is what keeps this file ASCII and therefore outside its own check —
#: see the module docstring, and ADR-0035 for why that mattered enough to design for.
DOTLESS_I = "\u0131"
S_CEDILLA = "\u015f"
G_BREVE = "\u011f"

#: Renders as "# Kurulum / Bu dosya calisiyor ve robot baglanacak." with the diacritics —
#: "This file is working and the robot will connect". The shape of the v1 lapse: a Turkish
#: heading and a Turkish sentence in a document that should have been English.
TURKISH = (
    "# Kurulum\n\n"
    f"Bu dosya cal{DOTLESS_I}{S_CEDILLA}{DOTLESS_I}yor ve robot ba{G_BREVE}lanacak.\n"
)

#: Every one of these appears in this repository's own documentation, and every one must
#: pass: em dash, en dash, box drawing, section sign, degree, plus-minus, multiplication,
#: arrows, comparison operators, middle dot and ellipsis.
#:
#: The `noqa: RUF001` markers are the point rather than an annoyance. Ruff's own rule warns
#: that a multiplication sign could be an `x` and an en dash a hyphen — a *typing* mistake,
#: which is a different question from the *language* one this module asks. These lines carry
#: the confusable characters deliberately, because they are what the check must not report.
TYPOGRAPHY = (
    "# Layout — as built\n\n"
    "See CLAUDE.md §3. Real-time factor 0.14 ± 0.02, rotated 18.7°, 3 × 50 mm.\n"  # noqa: RUF001
    "`stalled=true` → holding · latency ≤ 5 ms, ≥ 1 Hz, 2013–2026 …\n"  # noqa: RUF001
    "┌──────────┐\n"
    "│ L0 model │ ←→ generated\n"
    "└──────────┘\n"
)

#: Greek used as mathematics. ADR-0033 writes yaw as theta, ADR-0029 a correlation as rho, a
#: measurement campaign a significance level as alpha, ADR-0031 a difference as delta.
#: Excluding Greek is the least obvious decision in ADR-0035, so it is pinned here.
MATHEMATICS = "\n".join(
    (
        "A part yawed by θ presents 25·(cos θ + sin θ).",
        "ρ = +0.10, α = 0.01, |Δ| ≤ 2.0°.",  # noqa: RUF001
    )
)

#: Cited authors in `docs/reference/literature.md`. Latin-1 diacritics and Latin Extended-A
#: are shared with German, French, Hungarian, Swedish and Polish, so they are not a signal.
PROPER_NOUNS = "Cao, H., Söderlund, H. (2025). Ghzouli, R., Wąsowski, A. (2023). Peña, J.\n"

#: A repository-relative path and a body; returns nothing the tests need.
Writer = Callable[..., None]


@pytest.fixture
def signals() -> Config:
    """The repository's real signal set, with its exemptions dropped.

    The shipped exemption names a path that does not exist inside a temporary tree, and an
    exemption pointing at nothing is deliberately a failure. Tests that are about the signal
    say so by carrying no exemptions.
    """
    return dataclasses.replace(load_config(REPO_ROOT), exemptions=())


@pytest.fixture
def write(tmp_path: Path) -> Writer:
    """Write a file into a throwaway tree."""

    def _write(relative: str, body: str | bytes = "") -> None:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(body, bytes):
            path.write_bytes(body)
        else:
            path.write_text(body, encoding="utf-8")

    return _write


def _exempting(path: str) -> Config:
    """The shipped configuration with its one exemption pointed at a temporary file."""
    shipped = load_config(REPO_ROOT)
    return dataclasses.replace(
        shipped, exemptions=(dataclasses.replace(shipped.exemptions[0], path=path),)
    )


# --------------------------------------------------------------------------------------
# The lapse is caught. Without these the check is decoration.
# --------------------------------------------------------------------------------------


def test_a_turkish_document_is_reported(write: Writer, tmp_path: Path, signals: Config) -> None:
    write("docs/HIZLITEST.md", TURKISH)

    problems, _ = check(tmp_path, signals)

    assert problems == ["docs/HIZLITEST.md:3: not English (turkish-specific letters)"]


def test_turkish_in_source_is_reported_too(write: Writer, tmp_path: Path, signals: Config) -> None:
    """The scope is every file in the remit, not only documentation. v1 leaked into launch
    files, world files and configuration too — 17 files across seven extensions."""
    write("launch/lab.launch.py", "# Robotu ba\u015flat ve ba\u011fl\u0131 m\u0131 diye bak\n")

    problems, _ = check(tmp_path, signals)

    assert problems == ["launch/lab.launch.py:1: not English (turkish-specific letters)"]


def test_a_non_latin_script_is_reported(write: Writer, tmp_path: Path, signals: Config) -> None:
    #: "Obzor" in Cyrillic — a script that is never used to write English, so unlike
    #: the Turkish letters no per-character judgement is involved.
    write("README.md", "# \u041e\u0431\u0437\u043e\u0440\n")

    problems, _ = check(tmp_path, signals)

    assert problems == ["README.md:1: not English (Cyrillic)"]


def test_every_offending_line_is_named(write: Writer, tmp_path: Path, signals: Config) -> None:
    """One finding per line, so a reviewer sees the extent rather than the first instance."""
    write(
        "docs/notes.md",
        "# Notes\n\nkontrol edildi \u0131\u015f\u0131k\n\nfine\n\nba\u015far\u0131l\u0131\n",
    )

    problems, _ = check(tmp_path, signals)

    assert [problem.split(":")[1] for problem in problems] == ["3", "7"]


# --------------------------------------------------------------------------------------
# Legitimate content is not reported. This is the half that decides whether the rule
# survives its first week.
# --------------------------------------------------------------------------------------


def test_typography_is_not_a_lapse(write: Writer, tmp_path: Path, signals: Config) -> None:
    write("docs/architecture/L0-facility-model.md", TYPOGRAPHY)

    problems, _ = check(tmp_path, signals)

    assert problems == []


def test_greek_mathematical_notation_is_not_a_lapse(
    write: Writer, tmp_path: Path, signals: Config
) -> None:
    write("docs/adr/0033-standoff.md", MATHEMATICS)

    problems, _ = check(tmp_path, signals)

    assert problems == []


def test_cited_proper_nouns_are_not_a_lapse(write: Writer, tmp_path: Path, signals: Config) -> None:
    """The shared Latin-1 diacritics belong to several European languages and to author
    names. Adding them was measured to catch nothing extra and to cost exactly this."""
    write("docs/reference/literature.md", PROPER_NOUNS)

    problems, _ = check(tmp_path, signals)

    assert problems == []


def test_the_repositorys_own_documentation_passes(signals: Config) -> None:
    """The strongest false-positive test available: the real tree, the real signal, no
    exemptions. Anything reported here is content that already survived review, so this is
    the test that fails first if the signal is ever widened."""
    problems, _ = check(REPO_ROOT, signals)

    assert problems == [
        f"{QUOTING_DOCUMENT}:79: not English (turkish-specific letters)",
        f"{QUOTING_DOCUMENT}:693: not English (turkish-specific letters)",
    ]


# --------------------------------------------------------------------------------------
# The escape hatch, from both sides.
# --------------------------------------------------------------------------------------


def test_an_exempt_file_is_not_reported_but_is_announced(write: Writer, tmp_path: Path) -> None:
    """Silence is not the same as invisibility. Every run prints the exemptions it used, so
    the list growing is visible on every invocation and not only at review time."""
    write("docs/quoted.md", TURKISH)

    problems, notes = check(tmp_path, _exempting("docs/quoted.md"))

    assert problems == []
    assert len(notes) == 1
    assert notes[0].startswith("docs/quoted.md: 1 exempt line(s) — ")


def test_a_stale_exemption_fails_the_gate(write: Writer, tmp_path: Path) -> None:
    """An exemption list that only ever grows is how an escape hatch becomes a blanket. An
    entry whose file no longer needs it must be deleted, not left standing."""
    write("docs/quoted.md", "# All English now\n")

    problems, _ = check(tmp_path, _exempting("docs/quoted.md"))

    assert len(problems) == 1
    assert "stale exemption for docs/quoted.md" in problems[0]


def test_an_exemption_covers_one_file_and_not_its_neighbours(write: Writer, tmp_path: Path) -> None:
    """Exact paths, so exempting one document does not quietly exempt a directory."""
    write("docs/quoted.md", TURKISH)
    write("docs/other.md", TURKISH)

    problems, _ = check(tmp_path, _exempting("docs/quoted.md"))

    assert problems == ["docs/other.md:3: not English (turkish-specific letters)"]


def test_the_shipped_exemption_is_doing_work(signals: Config) -> None:
    """Guards the real file the escape hatch was designed for. If those quotations are ever
    rewritten in English this fails, and the exemption should then be deleted — the
    stale-entry rule pointed at the one entry that exists."""
    text = (REPO_ROOT / QUOTING_DOCUMENT).read_text(encoding="utf-8")

    assert scan(text, signals), "the exempt document no longer contains anything to exempt"


def test_the_shipped_configuration_leaves_the_tree_clean() -> None:
    """The gate as it actually ships, against the tree as it actually stands."""
    problems, notes = check(REPO_ROOT)

    assert problems == []
    assert [note.split(":")[0] for note in notes] == [QUOTING_DOCUMENT]


def test_the_shipped_exemption_list_is_one_entry() -> None:
    """A ratchet rather than a constant test. ADR-0035 says a second entry is the point at
    which per-file granularity should be reconsidered, and the precedent it borrows from —
    the teardown exemption in `tests/scenarios/continuous_line.py` — is valuable precisely
    because it was never widened. Widening this should require deciding to."""
    assert len(load_config(REPO_ROOT).exemptions) == 1


# --------------------------------------------------------------------------------------
# The escape hatch cannot be made easy to reach.
# --------------------------------------------------------------------------------------

_SIGNAL = 'signals:\n  turkish:\n    code_points: ["0131"]\n'


def test_an_exemption_without_a_reason_is_refused(write: Writer, tmp_path: Path) -> None:
    write(CONFIG_NAME, f"{_SIGNAL}exemptions:\n  - path: a.md\n")

    with pytest.raises(ConfigError, match="needs a non-empty `reason`"):
        load_config(tmp_path)


def test_an_exemption_with_a_blank_reason_is_refused(write: Writer, tmp_path: Path) -> None:
    write(CONFIG_NAME, f'{_SIGNAL}exemptions:\n  - path: a.md\n    reason: "   "\n')

    with pytest.raises(ConfigError, match="needs a non-empty `reason`"):
        load_config(tmp_path)


def test_a_glob_exemption_is_refused(write: Writer, tmp_path: Path) -> None:
    """One exact path per entry. A directory glob silences files nobody decided about."""
    write(CONFIG_NAME, f"{_SIGNAL}exemptions:\n  - path: docs/*.md\n    reason: convenience\n")

    with pytest.raises(ConfigError, match="globs are not accepted"):
        load_config(tmp_path)


def test_a_configuration_that_looks_for_nothing_is_refused(write: Writer, tmp_path: Path) -> None:
    """A gate that cannot tell 'clean' from 'checked nothing' must not report success — the
    failure `scripts/lint` documents at length for its ROS linter block."""
    write(CONFIG_NAME, "signals: {}\nexemptions: []\n")

    with pytest.raises(ConfigError, match="non-empty mapping"):
        load_config(tmp_path)


def test_a_bad_code_point_is_refused(write: Writer, tmp_path: Path) -> None:
    write(CONFIG_NAME, 'signals:\n  turkish:\n    code_points: ["not-hex"]\n')

    with pytest.raises(ConfigError, match="bad code point"):
        load_config(tmp_path)


def test_a_missing_configuration_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="cannot read"):
        load_config(tmp_path)


# --------------------------------------------------------------------------------------
# What the checker walks, and what it must not.
# --------------------------------------------------------------------------------------


def test_the_vendor_tree_is_not_scanned(write: Writer, tmp_path: Path, signals: Config) -> None:
    """ADR-0008 pins and patches `xarm_ros2` rather than hand-correcting it, so a finding
    inside it is one no commit of ours may act on — and a gate that fails on something
    nobody can fix is one people learn to ignore."""
    write("workspace/src/external/xarm_ros2/ReadMe.md", TURKISH)

    problems, _ = check(tmp_path, signals)

    assert problems == []


def test_build_output_and_agent_worktrees_are_not_scanned(
    write: Writer, tmp_path: Path, signals: Config
) -> None:
    """`.claude/` holds agent worktrees, which are whole copies of this repository — walking
    them reports every finding many times over, against trees no commit can repair."""
    write("build/cite_skills/generated.hpp", TURKISH)
    write(".venv/lib/site-packages/thing.py", TURKISH)
    write(".claude/worktrees/agent-1/docs/notes.md", TURKISH)

    problems, _ = check(tmp_path, signals)

    assert problems == []


def test_our_own_external_directory_is_still_scanned(
    write: Writer, tmp_path: Path, signals: Config
) -> None:
    """The vendor skip is anchored to `workspace/src/external`, not to the name `external`.
    The top-level `external/` is ours and holds the patches we do maintain."""
    write("external/patches/01-gripper.patch", TURKISH)

    problems, _ = check(tmp_path, signals)

    assert problems == [
        "external/patches/01-gripper.patch:3: not English (turkish-specific letters)"
    ]


def test_a_file_that_is_written_but_not_staged_is_still_reported(
    write: Writer, tmp_path: Path, signals: Config
) -> None:
    """Walking the tree rather than asking git is what makes this true, and for a lint gate
    the moment a file is written is the more useful moment to hear about it."""
    write("docs/draft.md", TURKISH)

    problems, _ = check(tmp_path, signals)

    assert problems == ["docs/draft.md:3: not English (turkish-specific letters)"]


def test_a_binary_file_is_skipped(write: Writer, tmp_path: Path, signals: Config) -> None:
    write("assets/mesh.stl", b"solid\x00\xff\xfe binary payload")

    problems, _ = check(tmp_path, signals)

    assert problems == []


def test_a_file_that_is_not_utf8_is_reported_not_skipped(
    write: Writer, tmp_path: Path, signals: Config
) -> None:
    """The same Turkish sentence in cp1254. Silently skipping what cannot be decoded would
    let the one encoding most likely to carry Turkish pass unread, and a checker that says
    nothing about a file it could not read is claiming a coverage it does not have."""
    write("docs/legacy.md", TURKISH.encode("cp1254"))

    problems, _ = check(tmp_path, signals)

    assert len(problems) == 1
    assert problems[0].startswith("docs/legacy.md: not valid UTF-8")
