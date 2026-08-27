# ADR-0025: Ship the QoS profiles as a library inside `cite_interfaces`

- **Status:** Accepted
- **Date:** 2026-08-24
- **Related:** ADR-0010, [qos-profiles.md](../interfaces/qos-profiles.md), charter §7

## Context

[`qos-profiles.md`](../interfaces/qos-profiles.md) defines five named QoS profiles —
`SENSOR`, `STATE`, `COMMAND`, `LATCHED`, `EVENT` — with exact reliability, durability,
history and depth values, and makes them binding: "Never rely on the default profile.
Declare a profile, from this table, every time."

The reason it is binding is that an incompatible publisher/subscriber QoS pair **connects
silently and delivers nothing**. The topic exists, both endpoints appear in
`ros2 topic info`, and no error is raised anywhere. It is the most-misdiagnosed failure in
ROS 2, and v1's handoff protocol died of exactly it.

A table in a document is not enforcement. If each node constructs its own `rclcpp::QoS`
from the table by hand, the table exists in as many places as there are publishers, and P1
is violated in the one area where the consequence is silent. So the profiles need to be
code — and that code needs a home.

The constraint is that charter §7 fixes the workspace package list at twelve `cite_*`
packages. Adding a thirteenth is a change to the charter, which is protected. And
[ADR-0010](0010-typed-ros-interfaces.md) says interface packages "depend on nothing else in
this project and sit at the bottom of the dependency graph" — anything every node needs
must sit at least as low.

**[Note 2026-08-27 — the `cite_*` package count, above and in Option B below, is no longer
twelve. Charter v1.5 added `cite_generated` and v1.7 added `cite_runtime`, so §7 now lists
fourteen. This is a note and
not a `## Correction`, deliberately: the corrections convention in
[README.md](README.md#corrections) is for a supporting claim that turns out to have been
*false*, and nothing here was. The sentence was true of the charter it named, the charter
was then amended twice by the route the sentence itself describes, and the constraint — a
new package costs a charter amendment — is unchanged and still binding. Take the count from
charter §7 or from `./scripts/doctor`, never from this record.]**

## Options considered

### Option A — A new `cite_common` package
The conventional ROS answer: a small utility package everyone depends on. Rejected on two
grounds. It requires amending a protected charter document for a utility library, and
"common" packages are a well-known sink — once one exists, everything that does not
obviously belong elsewhere lands in it, and within a year it is a dependency of everything
with no coherent responsibility.

### Option B — Each package defines its own profile constants
No new package, no charter change. Rejected outright: this is the table existing in twelve
places, which is a P1 violation whose failure mode is silent non-delivery. This is the
option that must not be chosen, and it is recorded so that nobody proposes it later as the
simple thing.

### Option C — Inside `cite_interfaces`, as an installed header and a Python module
`cite_interfaces` already sits at the bottom of the dependency graph, already depends on
nothing in-project, and is already a dependency of every node that publishes anything.
A `rosidl` package can carry an installed C++ header and a Python module alongside its
generated interfaces. Chosen.

## Decision

The five QoS profiles are implemented once, in `cite_interfaces`:

- `include/cite_interfaces/qos.hpp` — `cite::qos::sensor()`, `state()`, `command()`,
  `latched()`, `event()`, each returning an `rclcpp::QoS`.
- `cite_interfaces/qos.py` — the same five, returning `rclpy.qos.QoSProfile`.

The values in those two files and the table in
[`qos-profiles.md`](../interfaces/qos-profiles.md) are checked against each other by a test
in `cite_interfaces`, so the document cannot drift from the code.

**No node constructs a `QoS` object any other way.** A `rclcpp::QoS` or `QoSProfile`
literal outside these two files is a review finding, and `reviewer` treats it as such.

This is a deliberate widening of what an interface package contains: `cite_interfaces` now
holds the *shape* of every interface and the *delivery contract* for it. Both are parts of
the same contract, and separating them would put the two halves in different packages with
nothing keeping them consistent.

## Consequences

### What this gets us
- The profile table exists once, in code, and the document is tested against it.
- Every node that publishes already depends on `cite_interfaces`, so no new dependency edge
  is introduced anywhere and the layer graph is unchanged.
- No charter amendment, and no `cite_common` to become a dumping ground.
- A QoS mismatch becomes possible only by deliberately bypassing the library, which is
  reviewable — rather than by improvising a profile, which is invisible.

### What this costs us
- `cite_interfaces` is no longer purely declarative. It now has a compiled artifact and a
  Python module, so it has a build and a test of its own, and ADR-0010's description of an
  interface package as containing only `.msg`/`.srv`/`.action` becomes slightly narrower
  than reality. That document should note the exception.
- Two implementations — C++ and Python — of the same five profiles, kept honest by a test
  rather than by construction. That is a real duplication; it is unavoidable, because ROS 2
  has two client libraries, and a test is the strongest available mitigation.
- **The Python half needs an unusual install.** This ADR said a `rosidl` package "can carry
  an installed C++ header and a Python module alongside its generated interfaces". The C++
  half is ordinary. The Python half is not: `rosidl_generate_interfaces` already creates a
  Python package of this name for the generated bindings, so `ament_python_install_package`
  fails with a duplicate-target error. The module is therefore installed directly into that
  generated package's directory. It works and `cite_interfaces.qos` imports exactly as a
  consumer expects, but it is a non-obvious line in `CMakeLists.txt` and it is recorded here
  rather than left to be rediscovered. Found on 2026-08-24, during the first build.
- If a sixth profile is ever genuinely needed, it must be added to the document, both
  libraries and the consistency test together.

### What we will have to revisit
If `cite_interfaces` ever accumulates anything beyond interfaces and their delivery
contract — a helper, a converter, a base class — that is the signal that Option A was
right after all, and it should be reopened with a charter amendment rather than allowed
to happen gradually.

**[Note 2026-08-27 — this clause fired, and it worked as written. A `rclpy` shutdown helper
needed a home, and `cite_interfaces` was the obvious place for exactly the reasons Option C
gives. This clause is what turned that into a decision rather than a drift: it was reopened
by charter amendment (v1.7) and the helper went into a new `cite_runtime` instead of growing
a `runtime.py` here. See [ADR-0034](0034-process-lifecycle-mechanism-in-cite-runtime.md),
whose Option A exists specifically to refuse the option this clause anticipated.
`cite_interfaces` still holds interfaces and their delivery contract and nothing else —
checked on 2026-08-27 by listing the package: definitions, `qos.hpp`, `qos.py` and their
tests, and nothing further.]**
