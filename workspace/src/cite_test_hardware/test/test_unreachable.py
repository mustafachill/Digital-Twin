# Copyright 2026 Sam Houston State University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""ADR-0040: that no production launch path can reach the test fixture.

Two of the three guarantees in ADR-0040 decision 2 are structural and are not
tested here, because a test is the weaker statement in both cases:

  * the fixture refuses to initialise without a `stop_joint` parameter, and the
    L0 model has no way to express one, so a generated description cannot carry
    it — that is enforced by `JointStopSystem::on_init` returning ERROR;
  * the library, its install rule and its pluginlib export all sit inside
    `if(BUILD_TESTING)`, so a build with testing off contains no loadable class.

The third is a claim about where a NAME appears, and a name can be typed
anywhere. It is already covered twice over — a hand edit to the generated tree is
a Critical finding under ADR-0021, and `./scripts/validate-model` catches it by
byte-diffing that tree against a fresh generator run — but "covered by another
gate" is not the same as tested, and the cost of testing it directly is this
file.

**What this file is NOT.** It does not check that the fixture behaves; that is
`cite_bringup/test/test_abort_classification_launch.py`, which runs it. It checks
only that nothing outside a test can name it.
"""

from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ElementTree

#: The package's own name is the token to hunt for. The pluginlib class name
#: contains it, the CMake target links it, and a `package.xml` dependency spells
#: it — so one token catches every route by which something could come to load
#: the fixture, rather than only the one that was thought of.
TOKEN = 'cite_test_hardware'

REPO = Path(__file__).resolve().parents[4]

#: The fixture's own package. Everything in it may name it.
OWN_PACKAGE = 'workspace/src/cite_test_hardware/'

#: Build files that wire the fixture into the one test that uses it. Named
#: individually rather than by pattern, so that a third one cannot appear without
#: this list being edited — and `package.xml` is guarded again, by element, in the
#: second test below.
BUILD_WIRING = (
    'workspace/src/cite_bringup/package.xml',
    'workspace/src/cite_bringup/CMakeLists.txt',
)


def _may_name_it(relative: str) -> bool:
    """Whether this file is allowed to contain the token.

    THE RULE IS ABOUT CONTEXT, NOT ABOUT A LIST OF PATHS, because the list was the
    first thing to go stale: correcting a comment in `cite_skills`' unit test and a
    section of `cite_bringup`'s README to point at the new fixture — both of which
    are exactly what a reader needs — failed a path allow-list within an hour of
    it being written. A guard nobody can satisfy honestly gets widened until it
    guards nothing.

    Three contexts may name it, and each is a place from which nothing can be
    loaded:

      * the fixture's own package;
      * PROSE — any markdown file, anywhere. A decision record and a README have
        to be able to say what exists;
      * a TEST — any file under a `test/` or `tests/` directory, at any depth.

    Plus the two build files that declare it as a test dependency of the one test
    that uses it.

    What is therefore still forbidden is every context a running system reads: a
    description, a world, a controller configuration, a launch file, a bring-up
    plan, the L0 model, and any non-test source file in any package.
    """
    if relative.startswith(OWN_PACKAGE) or relative in BUILD_WIRING:
        return True
    if relative.endswith('.md'):
        return True
    return any(part in ('test', 'tests') for part in Path(relative).parts[:-1])


#: Directories that are not this repository's to answer for: build products, the
#: superseded v1 tree (CLAUDE.md §2), and third-party source imported by vcstool.
SKIPPED = (
    '.git',
    'legacy',
    'workspace/build',
    'workspace/install',
    'workspace/log',
    'workspace/src/external',
)


def _searchable_files():
    """Every text file in the repository that this rule applies to."""
    for path in REPO.rglob('*'):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(REPO).as_posix()
        if any(relative == skip or relative.startswith(skip + '/') for skip in SKIPPED):
            continue
        # A hidden directory at any depth: caches, editor state, local agent
        # tooling that a fresh clone does not contain at all.
        if any(part.startswith('.') for part in path.relative_to(REPO).parts[:-1]):
            continue
        try:
            yield relative, path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue


def test_the_fixture_is_named_only_where_a_test_may_name_it():
    """Nothing outside a test, a build file for that test, or a document.

    The failure this catches is a description, a launch file or a bring-up plan
    that names the fixture — which would put a component that exists to stop an
    arm mid-trajectory on a path that could be started by `./scripts/sim`.
    """
    offenders = sorted(
        relative
        for relative, text in _searchable_files()
        if TOKEN in text and not _may_name_it(relative)
    )
    assert not offenders, (
        f'{TOKEN} is named somewhere a running system could read it: {offenders}. '
        f'It is a test fixture; a production launch path that can reach it is a '
        f'hazard, not a fixture (ADR-0040).'
    )


def test_no_package_depends_on_the_fixture_outside_its_tests():
    """A `<test_depend>` and nothing stronger.

    `<depend>`, `<build_depend>` or `<exec_depend>` would put the fixture into a
    production install's dependency closure, which is the state in which somebody
    later concludes it is fair game to load.
    """
    stronger = (
        'depend', 'build_depend', 'exec_depend', 'build_export_depend',
        'buildtool_depend',
    )
    offenders = []
    for manifest in REPO.glob('workspace/src/*/package.xml'):
        if manifest.parent.name == TOKEN:
            continue
        root = ElementTree.parse(manifest).getroot()
        for element in root:
            if element.tag in stronger and (element.text or '').strip() == TOKEN:
                offenders.append(f'{manifest.parent.name}: <{element.tag}>')
    assert not offenders, (
        f'{TOKEN} is a test fixture and may only ever be a <test_depend>: {offenders}'
    )


def test_the_generated_tree_and_the_model_never_name_it():
    """Stated separately from the sweep above, because it is the load-bearing one.

    The sweep would already catch this. It is asserted again, against the two
    directories by name, so that a future relaxation of `_may_name_it` cannot
    quietly take the L0 model or the generated descriptions with it.
    """
    watched = ('model/', 'workspace/src/cite_generated/')
    offenders = sorted(
        relative
        for relative, text in _searchable_files()
        if TOKEN in text and relative.startswith(watched)
    )
    assert not offenders, (
        f'{TOKEN} appears in the facility model or the generated tree: {offenders}. '
        f'A generated artifact is never hand edited (ADR-0021), and the model has no '
        f'way to declare what this fixture requires (ADR-0040).'
    )


def test_no_launch_file_names_it():
    """Asserted by name too, for the same reason as the test above it.

    A launch file is the one thing that starts processes, and the whole claim is
    that no production launch path can reach the fixture. `_may_name_it` would
    already refuse a `launch/` directory, because it is neither markdown nor a
    test; this says so directly so that a future relaxation of that function
    cannot take launch files with it.
    """
    offenders = sorted(
        relative
        for relative, text in _searchable_files()
        if TOKEN in text and 'launch' in Path(relative).parts[:-1]
    )
    assert not offenders, (
        f'{TOKEN} is named in a launch file: {offenders}. A test fixture a real '
        f'bring-up can start is a hazard, not a fixture (ADR-0040).'
    )
