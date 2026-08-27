"""Enforce P10 — everything in this repository is written in English.

`CLAUDE.md` §3 makes it a hard rule and §4 lists non-English content among the standing
prohibitions "rejected in review, without discussion". Until this module existed, nothing
checked it. ADR-0015 predicted the gap in its own consequences: a lint rule is "what makes
this a rule rather than an aspiration", and none was written. Review alone did not hold the
line last time — `docs/reference/v1-lessons.md` records the requirement written on
2025-11-25 and violated seven days later.

**The instrument is not "no non-ASCII".** That check fires on every Markdown file in this
repository, because the prose is full of em dashes, box-drawing diagrams and `°`. What is
looked for instead is characters specific to one natural language, which cannot be
typography or mathematics. ADR-0035 records the four candidates that were measured, what
each fired on, and why this one was chosen — **cite it rather than copying its figures
here**, which is `CLAUDE.md` §2's "cite a campaign; do not copy its numbers around" and the
rule ADR-0027's own correction was written to establish. `.english-only.yaml` holds the
signal itself, because a list of what exists is configuration and this module is mechanism
(P5).

Which files are ours to check lives in `tree.py`, shared with `doclinks.py` rather than
copied (P1). `git ls-files` was tried there first and rejected on evidence: it fails
outright inside the container when the checkout is a `git worktree`, which is how this
project runs its agents. That module records the failure.
"""

from __future__ import annotations

import codecs
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from cite_tools.tree import our_files

#: Repository-root-relative location of the signal and exemption data.
CONFIG_NAME = ".english-only.yaml"

#: Read in one go, then whole-text-rejected before any line is examined. The naive form of
#: this check — a Python loop over every character — was measured two orders of magnitude
#: slower than the compiled pattern, and a gate nobody minds running is part of the design.
#: ADR-0035 holds both timings.
_CHUNK_IS_BINARY = b"\x00"

#: How many 16-bit units of a byte-order-mark-less file to test for the UTF-16 pattern.
#: Enough to be conclusive — the alternating-NUL run has to hold across all of them — and
#: bounded so the test costs the same on a 4 KB file and a 40 MB one.
_UTF16_SAMPLE_UNITS = 64


def _utf16_encoding(raw: bytes) -> str | None:
    """The UTF-16 flavour `raw` is written in, or `None` if it is not UTF-16.

    This exists because the NUL-byte binary test cannot tell UTF-16 text from a mesh: every
    ASCII character in UTF-16 is a byte and a NUL, so `_CHUNK_IS_BINARY` matches on the
    first letter. A UTF-16 file was therefore dropped without a word — with or without a
    byte-order mark — which is exactly the silence this module's docstring says it does not
    do, and a suppression route needing no configuration change at all. It is not exotic:
    Windows PowerShell and several editors write UTF-16 by default.

    A byte-order mark settles it outright. Without one the test is structural, then
    confirmed by decoding.

    *Structural*: in UTF-16 text drawn from any Latin script every NUL byte falls at the
    same parity — second of each pair in LE, first in BE — and no NUL falls at the other.
    Note what this does **not** assume: that the companion byte is NUL. It is not, for
    precisely the letters this module hunts. A dotless i is U+0131, so UTF-16-LE writes it
    `31 01` with a non-NUL high byte, and a test demanding alternating NULs would miss the
    Turkish file it exists to catch while matching the pure-ASCII one that carries no
    signal at all.

    *Confirmed by decoding*: the parity test alone can match binary that happens to hold
    NULs at one parity, so the candidate is decoded and the result required to be printable
    text. The order matters — `bytes.decode("utf-16-le")` succeeds on almost any
    even-length input, so decoding *first* would report every mesh and PNG in `assets/` as
    UTF-16. The parity test is what makes the decode meaningful.
    """
    if raw.startswith(codecs.BOM_UTF16_LE):
        return "utf-16-le"
    if raw.startswith(codecs.BOM_UTF16_BE):
        return "utf-16-be"

    sample = raw[: 2 * _UTF16_SAMPLE_UNITS]
    if len(sample) < 4 or len(sample) % 2 or _CHUNK_IS_BINARY not in sample:
        return None

    # `(nul_offset, encoding)`: UTF-16-LE puts the NUL of a Latin character second, BE first.
    for nul_offset, encoding in ((1, "utf-16-le"), (0, "utf-16-be")):
        if any(byte == 0 for byte in sample[1 - nul_offset :: 2]):
            continue  # a NUL at the wrong parity — not this flavour
        if not any(byte == 0 for byte in sample[nul_offset::2]):
            continue  # no NUL at the right parity either — nothing to go on
        try:
            decoded = sample.decode(encoding)
        except UnicodeDecodeError:
            continue
        if all(character.isprintable() or character in "\t\n\r" for character in decoded):
            return encoding
    return None


@dataclass(frozen=True)
class Exemption:
    """One file the check is allowed not to report, and why."""

    path: str
    reason: str


@dataclass(frozen=True)
class Config:
    """The signal to look for and the files exempt from it."""

    pattern: re.Pattern[str]
    #: Signal name by character, for the signals declared as an explicit character set.
    names: dict[str, str]
    #: Signal name by inclusive code-point range, for the signals declared as a range.
    ranges: dict[str, tuple[int, int]]
    exemptions: tuple[Exemption, ...]

    def signal_for(self, character: str) -> str:
        """Which declared signal a matched character belongs to."""
        if character in self.names:
            return self.names[character]
        for name, (low, high) in self.ranges.items():
            if low <= ord(character) <= high:
                return name
        return "unknown"  # pragma: no cover - unreachable while the pattern is built here


class ConfigError(Exception):
    """The configuration file is missing, malformed, or names nothing to look for."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(f"{CONFIG_NAME}: {message}")


def _code_point(signal: str, value: object) -> int:
    """One hexadecimal code point from the configuration.

    The signal is written as code points rather than as the letters themselves. Partly
    because a dotless i and an i are hard to tell apart by eye and a specification should
    not depend on the reader distinguishing them — but mainly so that this checker's own
    configuration, ADR and tests stay clear of the characters they exist to forbid, and
    therefore need no exemption. The escape hatch keeps its single entry.
    """
    try:
        return int(str(value), 16)
    except ValueError as exc:
        raise ConfigError(f"{CONFIG_NAME}: signal {signal!r}: bad code point {value!r}") from exc


def load_config(root: Path) -> Config:
    """Read and validate `.english-only.yaml`.

    Validated rather than trusted: a signal file that silently parses to an empty pattern
    is a gate that reports "clean" while looking for nothing, which is the exact failure
    `scripts/lint` documents for its ROS linter block.
    """
    source = root / CONFIG_NAME
    try:
        document = yaml.safe_load(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"{CONFIG_NAME}: cannot read ({exc})") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"{CONFIG_NAME}: cannot parse ({exc})") from exc

    _require(isinstance(document, dict), "top level must be a mapping")
    assert isinstance(document, dict)

    signals = document.get("signals")
    _require(isinstance(signals, dict) and bool(signals), "`signals` must be a non-empty mapping")
    assert isinstance(signals, dict)

    names: dict[str, str] = {}
    ranges: dict[str, tuple[int, int]] = {}
    classes: list[str] = []

    for name, spec in signals.items():
        _require(isinstance(spec, dict), f"signal {name!r} must be a mapping")
        assert isinstance(spec, dict)
        points, bounds = spec.get("code_points"), spec.get("range")
        _require(
            (points is None) != (bounds is None),
            f"signal {name!r} needs exactly one of `code_points` or `range`",
        )

        if points is not None:
            _require(
                isinstance(points, list) and bool(points),
                f"signal {name!r}: `code_points` must be a non-empty list of hex strings",
            )
            assert isinstance(points, list)
            for point in points:
                character = chr(_code_point(str(name), point))
                names[character] = str(name)
                classes.append(re.escape(character))
            continue

        _require(
            isinstance(bounds, list) and len(bounds) == 2,
            f"signal {name!r}: `range` must be a two-element list of hex code points",
        )
        assert isinstance(bounds, list)
        low, high = (_code_point(str(name), bound) for bound in bounds)
        _require(low <= high, f"signal {name!r}: range is inverted")
        ranges[str(name)] = (low, high)
        classes.append(f"{re.escape(chr(low))}-{re.escape(chr(high))}")

    declared = document.get("exemptions") or []
    _require(isinstance(declared, list), "`exemptions` must be a list")
    assert isinstance(declared, list)

    exemptions: list[Exemption] = []
    for entry in declared:
        _require(isinstance(entry, dict), "each exemption must be a mapping")
        assert isinstance(entry, dict)
        path, reason = entry.get("path"), entry.get("reason")
        _require(isinstance(path, str) and bool(path), "each exemption needs a `path`")
        # Not optional, and not allowed to be a placeholder. An exemption whose reason is
        # blank is an exemption nobody has to justify, and the list stops being reviewable.
        _require(
            isinstance(reason, str) and bool(reason.strip()),
            f"exemption {path!r} needs a non-empty `reason`",
        )
        assert isinstance(path, str) and isinstance(reason, str)
        _require(
            "*" not in path and "?" not in path,
            f"exemption {path!r} must be one exact path — globs are not accepted",
        )
        exemptions.append(Exemption(path=path, reason=" ".join(reason.split())))

    return Config(
        pattern=re.compile(f"[{''.join(classes)}]"),
        names=names,
        ranges=ranges,
        exemptions=tuple(exemptions),
    )


def files_to_check(root: Path) -> list[str]:
    """Every file in this checker's remit, as repository-relative POSIX paths."""
    return [path.relative_to(root).as_posix() for path in our_files(root)]


def scan(text: str, config: Config) -> list[tuple[int, set[str]]]:
    """Line numbers carrying a signal, with the signal names found on each.

    Whole text rejected first: almost every file has nothing, and splitting a 20 000-line
    CSV into lines to discover that is most of the runtime.
    """
    if not config.pattern.search(text):
        return []
    return [
        (number, {config.signal_for(character) for character in found})
        for number, line in enumerate(text.splitlines(), 1)
        if (found := config.pattern.findall(line))
    ]


def check(
    root: Path, config: Config | None = None, files: list[str] | None = None
) -> tuple[list[str], list[str]]:
    """Report non-English content across the tree.

    Returns `(problems, notes)`. `notes` carries the exemptions that were exercised, so
    every run shows the escape hatch being used rather than hiding it until review.

    `files` lets a caller that already has the remit pass it in rather than have it walked
    again. `main()` needs the count for its summary line, and walking a second time to
    produce one integer measured at 12% of the gate's runtime.
    """
    config = config or load_config(root)
    exempt = {exemption.path: exemption for exemption in config.exemptions}
    used: set[str] = set()

    problems: list[str] = []
    notes: list[str] = []

    for relative in files_to_check(root) if files is None else files:
        path = root / relative
        try:
            raw = path.read_bytes()
        except OSError as exc:
            # Reported for the same reason an undecodable file is. The walk listed this
            # path a moment ago, so failing to read it now means a dangling symlink or a
            # permission problem — not a file that is absent. (The comment here used to
            # describe uninitialised submodules and sparse checkouts, which belonged to the
            # `git ls-files` implementation this replaced: a manifest can name a path that
            # is not on disk, a filesystem walk cannot.) Staying quiet would claim a
            # coverage this run does not have.
            problems.append(f"{relative}: cannot be read ({exc.strerror or exc})")
            continue
        # Before the binary test, which cannot tell the two apart: a UTF-16 file is text
        # that is not valid UTF-8, so it is reported like any other undecodable file rather
        # than dropped as though it were a mesh.
        if (encoding := _utf16_encoding(raw)) is not None:
            problems.append(f"{relative}: not valid UTF-8 (this file is {encoding})")
            continue
        if _CHUNK_IS_BINARY in raw:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            # Reported, never silently skipped. A checker that cannot read a file and says
            # nothing is claiming a coverage it does not have.
            problems.append(f"{relative}: not valid UTF-8 ({exc.reason} at byte {exc.start})")
            continue

        findings = scan(text, config)
        if not findings:
            continue

        if relative in exempt:
            used.add(relative)
            notes.append(f"{relative}: {len(findings)} exempt line(s) — {exempt[relative].reason}")
            continue

        for number, signals in findings:
            found = ", ".join(sorted(signals))
            problems.append(f"{relative}:{number}: not English ({found})")

    # A stale entry is a standing permission nobody is using, and an exemption list that
    # only ever grows is how an escape hatch becomes a blanket. Deleting it is the point.
    for exemption in config.exemptions:
        if exemption.path not in used:
            problems.append(
                f"{CONFIG_NAME}: stale exemption for {exemption.path} — "
                "nothing there needs exempting now, so remove the entry"
            )

    return problems, notes


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()

    try:
        config = load_config(root)
        files = files_to_check(root)
        problems, notes = check(root, config, files)
    except ConfigError as exc:
        print(f"  {exc}")
        return 1

    for note in notes:
        print(f"  exempt: {note}")

    if problems:
        for problem in problems:
            print(f"  {problem}")
        # Says what the rule is and what the one legitimate escape looks like. A gate that
        # prints only a line number teaches the reader to silence it however they can.
        print(f"\n  {len(problems)} finding(s). Everything here is written in English")
        print("  (CLAUDE.md §3 P10, ADR-0015). If a finding is a citation or a proper noun")
        print(f"  that has to stay, add its exact path and a reason to {CONFIG_NAME} —")
        print("  and expect a reviewer to read it. The instrument is ADR-0035.")
        return 1

    print(f"  {len(files)} files checked, no non-English content outside {len(notes)} exemption(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
