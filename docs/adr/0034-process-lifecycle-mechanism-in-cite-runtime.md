# ADR-0034: Compensate two rclpy shutdown races, in a new `cite_runtime` package

- **Status:** Accepted. **Written after the shutdown fix landed**, and while the move into
  `cite_runtime` was being implemented — charter §12 requires the record first, and this
  did not get it. Two independent reviewers raised the missing ADR; that is why it exists.
  Stated rather than smoothed over (P7), and this is the fourth record on this branch to
  have to say it — see [ADR-0030](0030-facility-model-describes-the-workpiece.md),
  [ADR-0031](0031-refuse-direct-handoff-without-orientation-certainty.md) and
  [ADR-0033](0033-derive-the-index-standoff-from-the-workpiece.md).
- **Date:** 2026-08-27
- **Deciders:** Project owner (where the module lives); implementing and reviewing agents
  (the mechanism it contains)
- **Related:** [ADR-0010](0010-typed-ros-interfaces.md),
  [ADR-0019](0019-language-split-cpp-python.md),
  [ADR-0025](0025-qos-profiles-in-cite-interfaces.md) (whose closing clause this record
  answers), [cross-cutting-lifecycle.md](../architecture/cross-cutting-lifecycle.md),
  charter §4 (P1, P4, P7), §6, §7

## Context

Four `cite_facility` Python nodes — `frame_server`, `model_info`, `topology_server` and
`planning_scene_loader` — exited with status 1 at teardown, roughly **3 times in 30** when
the process was under `/clock` load. Each has the same `main()`: `rclpy.init()`,
`rclpy.spin(node)`, `except KeyboardInterrupt: pass`, then `destroy_node()` and
`rclpy.shutdown()`. The exception that reached the top was not a `KeyboardInterrupt`, so
nothing caught it:

```
RuntimeError: Unable to convert call argument '0' to Python object
```

### Why that message, and not a `KeyboardInterrupt`

The chain was traced to upstream source and every link below was read in the released code
rather than inferred (see **How this was verified**):

1. **`rclpy.init()` chains its SIGINT handler to the one it replaced.**
   `rclpy/src/rclpy/signal_handler.cpp` defines `rclpy_sigint_handler` to
   `call_signal_handler(g_original_sigint_handler, …)` *before* notifying rclpy's own guard
   conditions. In an ordinary Python process the handler it replaced is CPython's, which
   schedules `signal.default_int_handler` — so a `KeyboardInterrupt` is raised
   **asynchronously**, at whatever bytecode boundary comes next.
2. **A `/clock` message being converted is such a boundary.** The generated `convert_to_py`
   for a message executes Python code, so a pending `KeyboardInterrupt` can be raised
   inside it. It then returns `NULL`, the C-API convention for "an error is set".
3. **rclpy does not check for that `NULL`.** `rclpy/src/rclpy/utils.cpp:139` is
   `return py::reinterpret_steal<py::object>(convert(message));` — no test, so pybind11
   receives an object holding a null pointer. Twenty-one lines above it, at lines
   118-120, `convert_from_py` *does* check its converter's result and raises
   `py::error_already_set()` — which is exactly the handling this path lacks.
4. **The null object is packed into a tuple.** `Subscription::take_message` returns
   `py::make_tuple(pytaken_msg, …)` (`subscription.cpp:181`). pybind11's `make_tuple`
   tests each element and throws `cast_error_unable_to_convert_call_arg("0")` — element
   zero being the message — which is where the `'0'` in the message comes from.
5. **Reporting that error destroys the original one.** `cast_error` is declared
   `PYBIND11_RUNTIME_EXCEPTION(cast_error, PyExc_RuntimeError)`, whose `set_error()` is
   `PyErr_SetString(type, what())`. `PyErr_SetString` **replaces** the pending exception.
   The `KeyboardInterrupt` is discarded and a `RuntimeError` is substituted for it.

So the failure is not random: it is a window, and `/clock` traffic is what makes the window
wide enough to hit. **Idle, the same nodes did not fail.**

### Closing that race exposed a second one

Removing the asynchronous raise let shutdowns land further into the executor, where Jazzy's
`rclpy/rclpy/executors.py` has a use-before-check. In rclpy **7.1.11** (the version in
`ros:jazzy-ros-base-noble`), inside `_wait_for_ready_callbacks`:

| Line | Code |
|---|---|
| 755 | `context_stack.enter_context(self._context.handle)` |
| 757 | `wait_set = _rclpy.WaitSet(…, self._context.handle)` |
| 781 | `wait_set.wait(timeout_nsec)` |
| 785 | `raise ExternalShutdownException()` — guarded by `if not self._context.ok():` at 784 |

The context is **used** at 755 and 757 and its validity is **tested** at 784, twenty-seven
lines later. A shutdown that lands in that window invalidates the handle before the test is
reached, so the failure surfaces as a raw `RCLError` rather than the
`ExternalShutdownException` the executor is designed to raise for it.

### What was measured

Reported by the implementing agent, on one machine, on 2026-08-27:

| Condition | Bad exits |
|---|---|
| Under `/clock` load, before the fix | **3 of 30** |
| Idle, before the fix | **0 of 30** |
| Under `/clock` load, after the fix | **0 of 40** |

An independent reviewer reproduced the **mechanism** deterministically with a tripwire —
**5 of 5** pre-fix, **5 of 5** post-fix — and separately got **0 of 30** under external
SIGINT at its own load level. **That negative belongs here.** It does not contradict the
rate above; it confirms that the rate is a function of load, which is precisely why the
defect was survivable for as long as it was.

**None of this is a campaign.** No thresholds were registered before the first trial, the
runs are one agent's on one machine, and there is no directory for this in
[`../measurements/`](../measurements/README.md). Treat the numbers as the size of the
evidence, not as a measurement of the defect.

### Where the module had to live

The fix is a small Python module. Charter §7 fixes the workspace package list, so putting
it in a new package is a charter amendment, and putting it in an existing one is a change
to what that package claims to be. Neither is free.

## Options considered

### Option A — `cite_interfaces`
Where [ADR-0025](0025-qos-profiles-in-cite-interfaces.md) put `qos.py`: bottom of the
dependency graph, depends on nothing in-project, already a dependency of every node.

**Rejected, and this is the option the record exists to refuse.** ADR-0025's closing clause
is a tripwire written for exactly this moment: "If `cite_interfaces` ever accumulates
anything beyond interfaces and their delivery contract — a helper, a converter, a base
class — that is the signal that Option A was right after all, and it should be reopened
with a charter amendment rather than allowed to happen gradually." A shutdown helper is
that helper.

The substantive distinction, which is why the QoS precedent does not reach this module:

- **`qos.py` is a contract *between* two nodes.** A publisher and a subscriber must agree
  or delivery fails silently. It must therefore exist exactly once, or not at all.
- **`runtime.py` is a convention *inside* one process.** Two nodes with different shutdown
  code do not fail against each other; each is merely right or wrong on its own.

The argument that forced QoS into the interface package is an argument about silent
cross-node failure. It does not apply here, so it cannot be borrowed here.

### Option B — Keep it in `cite_facility`
No new package, no charter amendment, and the four affected nodes are already there.

Rejected on two grounds.

- **It is not what the package says it is.** `cite_facility/package.xml` describes the
  package as *"runtime access to the artifacts generated from the L0 facility model"*. A
  signal-handling shim is neither an artifact nor a runtime fact about the facility.
- **It would make the dependency edge invisible.** `cite_facility` installs its Python via
  `ament_python_install_package`, so `from cite_facility import runtime` resolves from any
  sourced workspace **with no manifest edit**. A future Python node importing it would
  create a dependency that `rosdep` cannot see, CMake does not record, and a reviewer has
  no artifact to notice. Charter §7 still lists `cite_twin` (L5, Phase 2), `cite_telemetry`
  and `cite_safety` as packages to come, and charter §6 assigns Python to exactly that kind
  of node — so those consumers are not hypothetical.

### Option C — A new `cite_common`
The conventional ROS answer. **Rejected, and already rejected once**: ADR-0025 Option A
refused it partly because "common" packages are a well-known sink — once one exists,
everything that does not obviously belong elsewhere lands in it, and within a year it is a
dependency of everything with no coherent responsibility. Nothing about this module changes
that. Naming a package for what it *does* is what answers the objection.

### Option D — No shared module; each node carries its own handler
No new package and no new dependency anywhere. The failure mode is not silent, so P1's
usual argument — a value in two places whose copies diverge invisibly — is weaker here than
it was for QoS.

Rejected anyway, on the strength of the **removal condition** below. This code exists only
to compensate for two upstream defects and must be **deleted** when they are fixed. A
compensation with four deletion sites is a compensation that will be deleted from three of
them.

### Option E — A new `cite_runtime`. Chosen.

## Decision

**1. A new first-party package, `cite_runtime`, holds process-lifecycle mechanism.** It is
added to charter §7 by explicit decision of the project owner (charter v1.7), which is what
ADR-0025's closing clause asked for.

**2. Admission to it is decided by one sentence, and the sentence is testable:**

> A module belongs in `cite_runtime` only if all three hold: it is **process-lifecycle
> mechanism** — signals, shutdown, spin-and-exit; it carries **no domain knowledge** — no
> facility, asset, station, skill, zone or interface concept appears in it; and it
> **depends on nothing else in this project**.

A module that fails any clause does not go in, and the package is **not widened to admit
it**. That is the difference between this package and the `cite_common` that was rejected
twice: `cite_common` has no sentence that can turn a contribution away.

**3. The shutdown convention itself**, which the package implements once:

- A SIGINT handler is installed that **returns without raising**, so no asynchronous raise
  can occur and step 2 of the chain above cannot happen. rclpy's own handler still runs and
  still notifies its guard conditions, so shutdown is still an *event* (P4) — what is
  removed is only the exception that rode alongside it.
- Shutdown is observed through `rclpy.ok()` and `ExternalShutdownException`, never through
  `KeyboardInterrupt`.
- An `RCLError` out of the executor is tolerated **only while `rclpy.ok()` is already
  false**. Under any other condition it propagates.

The convention is written up, scoped to `rclpy`, in
[cross-cutting-lifecycle.md](../architecture/cross-cutting-lifecycle.md).

## Removal conditions

**Both items in point 3 are compensations for upstream defects. They are to be deleted when
upstream is fixed, not maintained.** This section is the most important thing in this
record, because a future contributor who finds a no-op SIGINT handler in a robotics
codebase will reasonably read it as a mistake — and removing it silently reintroduces a
teardown failure at roughly one run in ten under load, a rate low enough to be written off
as flake and high enough to poison a scenario gate.

**Do not remove either one on the grounds that it looks wrong. Check the condition.**

### Compensation 1 — the non-raising SIGINT handler

**Upstream defect.** `convert_to_py` in `rclpy/src/rclpy/utils.cpp` does not test the
generated converter's return value for `NULL` before `py::reinterpret_steal`, so a Python
error raised *during* conversion — including an asynchronous `KeyboardInterrupt` — becomes
a pybind11 `cast_error` and then, via `PyErr_SetString`, a `RuntimeError` that has replaced
it.

**What to check.** Read that function in the rclpy you are running. If the result of
`convert(message)` is `NULL`-checked and the pending error propagated with
`throw py::error_already_set()` — the way `convert_from_py` already does in the same file —
this race is closed and the handler is dead weight. Delete it.

**Not filed upstream by this project.** A search of the `ros2/rclpy` issue tracker on
2026-08-27 for `convert_to_py`, `Unable to convert call argument` and `KeyboardInterrupt`
surfaced no issue describing this chain; that is a survey, not a proof that none exists.
Filing it is an open action and is not a condition of this decision.

### Compensation 2 — tolerating `RCLError` while `rclpy.ok()` is false

**Upstream defect.** `rclpy/rclpy/executors.py` uses `self._context` to enter a context
manager and to construct the wait set before it tests `self._context.ok()`, so a shutdown
landing between the two produces an `RCLError` where the executor's own design says
`ExternalShutdownException`.

**What to check.** In the rclpy you are running, find the wait-set construction in
`_wait_for_ready_callbacks` and the `if not self._context.ok(): raise
ExternalShutdownException()` that follows it. If the validity test now **precedes** the
construction, or the construction itself raises `ExternalShutdownException`, delete the
tolerance. Search for the code, not for line 757 and line 784 — those numbers are true of
rclpy 7.1.11 and will drift.

## Consequences

### What this gets us
- **One deletion site** for each compensation, so the removal conditions above are
  executable rather than aspirational.
- **The dependency edge is visible.** A future Python node that wants this must add
  `<depend>cite_runtime</depend>`, which `rosdep`, the build and a reviewer can all see.
- **`cite_facility` still is what its manifest says it is**, and `cite_interfaces` still
  holds interfaces and their delivery contract and nothing else.
- **ADR-0025's tripwire was honoured rather than tripped** — the case it predicted arrived,
  and it was reopened by amendment instead of by drift.

### What this costs us
- **A charter amendment and a fourteenth `cite_*` package for a small library.** That is a
  real cost and it is the reason Option B is tempting.
- **`Ctrl-C` no longer raises `KeyboardInterrupt` anywhere in the process.** Under
  [PEP 475](https://peps.python.org/pep-0475/) (*Retry system calls failing with EINTR*),
  a signal handler that returns without raising causes the interrupted system call to be
  **retried**. Verified first-hand on
  CPython 3.12.12: with such a handler installed, a `time.sleep(2.0)` interrupted by SIGINT
  at t = 0.5 s ran the handler and then **slept the full two seconds**. So any blocking
  Python call outside rclpy's control becomes uninterruptible by SIGINT in a process that
  installs this. Every exit path must go through the rclpy shutdown event.
- **This is compensation code, and compensation code rots.** It is pinned to the behaviour
  of one upstream version. If rclpy changes the mechanism without fixing it, the handler
  may stop helping without anything saying so.
- **A tolerated exception is a narrowed assertion.** `RCLError` while `rclpy.ok()` is false
  is now silence. If a genuine `RCLError` ever occurs in that window for an unrelated
  reason, this hides it.
- **Nothing in CI proves the absence of the failure**, because the failure was 3 in 30. The
  post-fix figure is 0 of 40 on one machine — enough to say the rate went down, not enough
  to say it is zero.

### What is explicitly not decided here
- **There is no C++ equivalent and none is claimed.** `rclcpp`'s `SignalHandler` chains to
  the previous OS handler and explicitly refuses to call `SIG_DFL`; no Python exception
  machinery is involved, there is no `KeyboardInterrupt`, and there is no `convert_to_py`.
  **Neither race can port**, because both require Python exception machinery that is not
  there — which is a conclusion from what was read, not a claim that C++ teardown is sound.
  This decision binds `rclpy` nodes only, and inventing a C++
  convention for a race nobody has demonstrated would be the same error in the other
  direction.
- **A separate signal-family teardown failure exists and is out of scope.** `skill_server`
  has been seen to exit on SIGSEGV; a `MoveGroupInterface` reference cycle is *suspected*
  and **not demonstrated**. It is named here so that nobody reads this record as having
  explained it. It has not been explained, and folding it in would let this record take
  credit for a fix it did not make.
- **Lifecycle callbacks still do not run on SIGINT.** Three of the four nodes are
  `LifecycleNode`s and `destroy_node()` is called directly; `on_cleanup` never runs. That
  was already true of the code being replaced, so this change does not introduce it — but
  it does canonize it. It is recorded as a **gap**, with the condition under which it stops
  being harmless, in
  [cross-cutting-lifecycle.md](../architecture/cross-cutting-lifecycle.md).

### What we will have to revisit
- **When either upstream defect is fixed** — delete the compensation, per the conditions
  above. This is the expected end state, not a contingency.
- **When the first Python lifecycle node holds something whose release matters** — a file,
  a hardware handle, a latched safety output. Abrupt teardown is harmless today only
  because the four nodes hold publishers and services and nothing else.
- **If a module is proposed for `cite_runtime` that fails the admission sentence.** That is
  a new ADR about widening the package, not a judgement call at review time. The sentence
  exists so that the widening cannot happen quietly.
- **If a C++ teardown race is ever demonstrated** rather than assumed, the C++ side needs
  its own decision, and it will not be this one copied across.

## How this was verified

Recorded in the style of [`../reference/toolchain.md`](../reference/toolchain.md), because
every claim above about third-party behaviour is checkable and was checked on 2026-08-27.

| Claim | How verified | Result |
|---|---|---|
| rclpy's SIGINT handler calls the handler it replaced, first | Read `signal_handler.cpp` on the `ros2/rclpy` `jazzy` branch (head `4806323`) | `rclpy_sigint_handler` calls `call_signal_handler(g_original_sigint_handler, …)` before `notify_signal_handler()` |
| `convert_to_py` steals its result unchecked | Read `rclpy/src/rclpy/utils.cpp`, same branch | Line 139: `return py::reinterpret_steal<py::object>(convert(message));`, no `NULL` test. `convert_from_py` at lines 118-120 does test |
| The null object reaches `make_tuple` as element 0 | Read `rclpy/src/rclpy/subscription.cpp`, same branch | `convert_to_py` at line 171, `py::make_tuple(pytaken_msg, …)` at line 181 |
| pybind11 produces exactly that message | Read `include/pybind11/cast.h` | `make_tuple` throws `cast_error_unable_to_convert_call_arg(std::to_string(i))`, whose text is `Unable to convert call argument '<i>' to Python object` |
| Reporting it discards the pending exception | Read `include/pybind11/detail/common.h` | `PYBIND11_RUNTIME_EXCEPTION(cast_error, PyExc_RuntimeError)`; the macro's `set_error()` is `PyErr_SetString(type, what())`, which replaces any pending exception |
| The executor's use-before-check, in the version we run | `docker run --rm ros:jazzy-ros-base-noble` — `dpkg-query` for the version, then `sed -n '755p;757p;784p'` on the installed `rclpy/executors.py` | `ros-jazzy-rclpy 7.1.11-1noble.20260612.095634`; the three lines are `context_stack.enter_context(self._context.handle)`, `wait_set = _rclpy.WaitSet(`, `if not self._context.ok():` — matching the `jazzy` branch exactly |
| A non-raising handler makes a blocking call uninterruptible | Ran a script on CPython 3.12.12: install a handler that returns, raise SIGINT at t = 0.5 s into a `time.sleep(2.0)` | Handler ran; the sleep completed at 2.00 s. No `KeyboardInterrupt` |
| Neither race ports to C++ | Read `rclcpp/src/rclcpp/signal_handler.cpp` on the `ros2/rclcpp` `jazzy` branch | Chains to the previous OS handler and skips `SIG_DFL`/`SIG_IGN`; no Python C-API call anywhere in it |
| No upstream issue describes this | Searched the `ros2/rclpy` issue tracker for `convert_to_py`, `Unable to convert call argument`, `KeyboardInterrupt` | Nothing matching the chain was found. **A survey on 2026-08-27, not a proof that none exists** |

**Not verified here:** the pass counts in *What was measured*. They are reported by the
agents who took them and are not reproduced in this record.
