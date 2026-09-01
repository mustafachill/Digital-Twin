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

#: Published measurement evidence. A campaign that used the fixture as an
#: instrument records that it did, in a `harness/` and a `raw/` that
#: `docs/measurements/README.md` freezes once the first trial has run.
PUBLISHED_CAMPAIGNS = 'docs/measurements/'


def _may_name_it(relative: str) -> bool:
    """Whether this file is allowed to contain the token.

    THE RULE IS ABOUT CONTEXT, NOT ABOUT A LIST OF PATHS, because the list was the
    first thing to go stale: correcting a comment in `cite_skills`' unit test and a
    section of `cite_bringup`'s README to point at the new fixture — both of which
    are exactly what a reader needs — failed a path allow-list within an hour of
    it being written. A guard nobody can satisfy honestly gets widened until it
    guards nothing.

    Four contexts may name it, and each is a place from which nothing can be
    loaded:

      * the fixture's own package;
      * PROSE — any markdown file, anywhere. A decision record and a README have
        to be able to say what exists;
      * a TEST — any file under a `test/` or `tests/` directory, at any depth;
      * PUBLISHED EVIDENCE — anything under `docs/measurements/`. A campaign that
        used the fixture as an instrument has to be able to say so in the code that
        produced its numbers and in the logs that recorded them, and a campaign's
        `harness/` and `raw/` are frozen by `docs/measurements/README.md` once its
        first trial has run — so this is a context that CANNOT be edited afterwards
        without the campaign ceasing to be the thing that produced its results. It
        is reachable from no launch path: nothing in `scripts/`, `workspace/` or
        `.github/` invokes anything under that directory. And it is none of the
        three locations ADR-0040 decision 2 actually names — `model/`,
        `workspace/src/cite_generated/` and a `launch/` directory — so refusing it
        made this guard broader than the claim it exists to enforce, which is how
        publishing a campaign came to turn `main` red.

    Plus the two build files that declare it as a test dependency of the one test
    that uses it.

    What is therefore still forbidden is every context a running system reads: a
    description, a world, a controller configuration, a launch file, a bring-up
    plan, the L0 model, and any non-test source file in any package.
    """
    if relative.startswith(OWN_PACKAGE) or relative in BUILD_WIRING:
        return True
    if relative.startswith(PUBLISHED_CAMPAIGNS):
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
    """Nothing outside a test, a build file for that test, a document or a campaign.

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


def _is_a_launch_file(relative: str) -> bool:
    """Whether this path is a launch file, by directory component or by shape.

    Deliberately NOT expressed in terms of `_may_name_it`, and read by nothing
    else. See `test_no_launch_file_names_it` for why the independence is the
    point; the two clauses are here so that neither form can be added later
    without both being considered.
    """
    return 'launch' in Path(relative).parts[:-1] or relative.endswith('.launch.py')


def test_no_launch_file_names_it():
    """Asserted by name too, and this is now the ONLY thing refusing some of them.

    A launch file is the one thing that starts processes, and the whole claim is
    that no production launch path can reach the fixture.

    **`_may_name_it` no longer refuses every launch file, so this test is not a
    restatement of it.** Since `docs/measurements/` became a permitted context, the
    sweep above PERMITS a `launch/` directory inside a published campaign — a
    `harness/launch/rig.launch.py` and a `raw/launch/run.log` alike — and this test
    is the only thing that refuses either. It is also the only thing that refuses a
    launch file identified by its SHAPE rather than by a directory component: a
    `harness/rig.launch.py` has no `launch` component at all, so the sweep permits
    it under the campaign context and the directory clause alone missed it.

    It must stay independent of `_may_name_it` rather than being deduplicated
    against it, because a future relaxation of that function cannot then take
    launch files with it. That independence has a price, recorded in ADR-0040's
    2026-09-01 amendment: a campaign that publishes a `launch/` directory naming
    the fixture takes `main` red, and a campaign is frozen once its first trial has
    run, so the fix would have to be here rather than in the campaign.
    """
    offenders = sorted(
        relative
        for relative, text in _searchable_files()
        if TOKEN in text and _is_a_launch_file(relative)
    )
    assert not offenders, (
        f'{TOKEN} is named in a launch file: {offenders}. A test fixture a real '
        f'bring-up can start is a hazard, not a fixture (ADR-0040).'
    )


#: The three files the 2026-09-01 grasp-discrimination campaign committed that name
#: the fixture — its harness, its reproduction command, and one run log in which the
#: controller manager reports loading the plugin. Written out here rather than
#: discovered, so that this test says what it means even after the campaign is
#: archived, moved or deleted.
PUBLISHED_EVIDENCE_THAT_NAMES_IT = (
    'docs/measurements/2026-09-01-grasp-discrimination/harness/measure_fp.py',
    'docs/measurements/2026-09-01-grasp-discrimination/harness/run_fp.sh',
    'docs/measurements/2026-09-01-grasp-discrimination/raw/shakedown/logs/'
    'FP_SHAKEDOWN_002_47.15.log',
)

#: One path per context a running system reads: a launch file, the L0 model, the
#: generated bring-up plan, and an ordinary source file in an ordinary package.
#: Synthetic on purpose — a real path would make this test a statement about what
#: happens to be committed today rather than about the rule.
CONTEXTS_A_RUNNING_SYSTEM_READS = (
    'workspace/src/cite_simulation/launch/anything.launch.py',
    'model/assets/types/robots/x.yaml',
    'workspace/src/cite_generated/bringup/cell_a_plan.yaml',
    'workspace/src/cite_skills/src/skill_server.cpp',
)


def test_published_evidence_may_name_the_fixture():
    """Asserted against strings, so the sweep above cannot be the only thing saying so.

    The sweep is silent whenever the repository happens to contain no campaign that
    used the fixture — which is most of this project's history and was the state on
    the day the rule was written. Naming the paths here makes the permission a
    property of `_may_name_it` rather than of what is on disk, so that narrowing the
    rule back fails immediately instead of waiting for the next campaign to be
    published and take `main` red with it.
    """
    refused = [
        relative
        for relative in PUBLISHED_EVIDENCE_THAT_NAMES_IT
        if not _may_name_it(relative)
    ]
    assert not refused, (
        f'published campaign evidence is refused the fixture name: {refused}. A '
        f'campaign is frozen once its first trial has run '
        f'(docs/measurements/README.md), so this guard cannot be satisfied by '
        f'editing it, and it is reachable from no launch path (ADR-0040).'
    )


#: Launch files inside a published campaign, which `_may_name_it` PERMITS — the
#: first by the campaign context, the second by it too, because it carries no
#: `launch` directory component for the shape clause to have keyed on either. Both
#: must still be refused by `test_no_launch_file_names_it`, which is the only thing
#: left that refuses them. Literal paths, none of them committed: a real one would
#: make this a statement about today's tree rather than about the rule.
LAUNCH_FILES_A_CAMPAIGN_COULD_PUBLISH = (
    'docs/measurements/2026-09-01-a-campaign/harness/launch/rig.launch.py',
    'docs/measurements/2026-09-01-a-campaign/harness/rig.launch.py',
)

#: One directory outside the permitted root, and one directory whose name merely
#: starts with it. Both must be refused, and each fails a different way of widening
#: `PUBLISHED_CAMPAIGNS`: the first if it is relaxed to a parent directory, the
#: second if its trailing slash is dropped. Neither is caught by the contexts above,
#: because neither is a context a running system reads.
JUST_OUTSIDE_THE_PERMITTED_ROOT = (
    'docs/architecture/anything.py',
    'docs/measurements2/harness/x.py',
)


def test_a_launch_file_in_a_published_campaign_is_still_refused():
    """The by-name test is strictly stricter than the sweep, and this pins both halves.

    `_may_name_it` permits everything under `docs/measurements/`, launch files
    included, so `test_no_launch_file_names_it` is what stands between a campaign
    and a launch file naming the fixture. It has to catch the shape as well as the
    directory: `harness/rig.launch.py` names no `launch` directory, and until
    2026-09-01 nothing in this file refused it at all.
    """
    permitted_by_the_sweep = [
        relative
        for relative in LAUNCH_FILES_A_CAMPAIGN_COULD_PUBLISH
        if not _may_name_it(relative)
    ]
    assert not permitted_by_the_sweep, (
        f'these paths are refused by the sweep, so this test no longer pins what it '
        f'says it pins: {permitted_by_the_sweep}. Rewrite it against paths the sweep '
        f'permits, or delete it.'
    )
    missed = [
        relative
        for relative in LAUNCH_FILES_A_CAMPAIGN_COULD_PUBLISH
        if not _is_a_launch_file(relative)
    ]
    assert not missed, (
        f'a launch file naming {TOKEN} would be refused by nothing: {missed}. The '
        f'sweep permits a published campaign; this test is the only thing that '
        f'refuses a launch file inside one (ADR-0040).'
    )


def test_the_permitted_root_is_no_wider_than_it_says():
    """A path one directory out, and a directory whose name merely starts with it.

    The negative control above is satisfied by a rule far looser than the one
    written: widening `PUBLISHED_CAMPAIGNS` to `docs/` leaves every context a
    running system reads refused, so nothing failed. These two paths are what make
    the root itself the thing under test.
    """
    permitted = [
        relative
        for relative in JUST_OUTSIDE_THE_PERMITTED_ROOT
        if _may_name_it(relative)
    ]
    assert not permitted, (
        f'{TOKEN} would be permitted outside the published-campaign root: {permitted}. '
        f'The permission is for `{PUBLISHED_CAMPAIGNS}` and nothing above it or beside '
        f'it (ADR-0040).'
    )


def test_the_contexts_a_running_system_reads_are_still_refused():
    """The other direction of the same rule, and the reason it is safe to widen.

    Adding a fourth permitted context is only defensible if the contexts the guard
    exists for are demonstrably untouched by it. The sweeps above assert that
    over the tree; this asserts it over the rule, so that a fifth context added
    later cannot pass by being written loosely enough to swallow one of these.
    """
    permitted = [
        relative
        for relative in CONTEXTS_A_RUNNING_SYSTEM_READS
        if _may_name_it(relative)
    ]
    assert not permitted, (
        f'{TOKEN} would be permitted somewhere a running system reads: {permitted}. '
        f'A production launch path that can reach the fixture is a hazard, not a '
        f'fixture (ADR-0040).'
    )
