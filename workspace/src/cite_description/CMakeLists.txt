cmake_minimum_required(VERSION 3.16)
project(cite_description NONE)

find_package(ament_cmake REQUIRED)

# The assets live at the repository root, not inside this package.
#
# That is not laziness about layout, it is ADR-0012's storage policy: `assets/`
# is the tier boundary between what git holds and what the manifest only records,
# and `assets/manifest.yaml` beside it carries the provenance of everything
# derived. Moving the meshes in here would put the files in one place and their
# provenance in another, and would leave `assets/README.md` describing a
# directory that no longer holds what it says it holds.
#
# So this package installs from there. It is the ONLY package that may, which is
# what keeps "where an asset lives" and "how an asset is reached at runtime" from
# becoming two answers.
get_filename_component(CITE_REPO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../.." ABSOLUTE)
set(CITE_ASSET_MESHES "${CITE_REPO_ROOT}/assets/meshes")

# Fail at configure time rather than installing nothing. An empty install is a
# description whose collision meshes resolve to a missing file, which Gazebo
# reports as a warning buried in a launch log and then simulates without them.
if(NOT IS_DIRECTORY "${CITE_ASSET_MESHES}")
  message(FATAL_ERROR
    "expected the project's asset meshes at ${CITE_ASSET_MESHES}. "
    "This package installs assets/meshes from the repository root; see ADR-0012.")
endif()

install(DIRECTORY "${CITE_ASSET_MESHES}" DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)

  # Two linters registered by hand rather than through ament_lint_auto, for the
  # reason `cite_bringup` and `cite_facility` already give and with the same
  # settlement, so that a Python file does not have to be written differently
  # depending on which package it happens to live in.
  #
  # pep257: the "ament" convention ignores D212 and therefore enforces D213,
  # "summary should start at the second line". The two are mutually exclusive by
  # construction and every docstring in this repository puts the summary on the
  # first line.
  #
  # flake8: ament's default prefers single quotes; this repository formats Python
  # with ruff, which prefers double. `.flake8` at the repository root is the one
  # place that is settled.
  list(APPEND AMENT_LINT_AUTO_EXCLUDE ament_cmake_flake8 ament_cmake_pep257)
  ament_lint_auto_find_test_dependencies()

  find_package(ament_cmake_flake8 REQUIRED)
  ament_flake8(CONFIG_FILE "${CMAKE_CURRENT_SOURCE_DIR}/../../../.flake8")
  find_package(ament_cmake_pep257 REQUIRED)
  ament_pep257(--add-ignore D213)

  # An installed asset that no description references is dead weight; a
  # referenced asset that is not installed is a missing collision shape. This
  # asserts the half that can be checked without a simulator: every mesh the L0
  # model declares for a derived collision set is present in the source tree that
  # this package installs, under the relative path the binding depends on.
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_declared_collision_meshes_are_installable
    test/test_declared_collision_meshes_are_installable.py)
endif()

ament_package()
