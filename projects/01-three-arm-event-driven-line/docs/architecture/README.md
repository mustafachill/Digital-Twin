# Architecture

The system is a strict layer stack. **A layer may depend only on layers below it.** An
upward dependency is an architectural defect and an `ESCALATE`, not a code-review finding.

```
┌───────────────────────────────────────────────────────────────────────────┐
│  L7  PRESENTATION            Operator HMI · remote access · reporting     │
├───────────────────────────────────────────────────────────────────────────┤
│  L6  DATA & TELEMETRY        Telemetry schema · recording · historian ·   │
│                              replay · external protocol bridges           │
├───────────────────────────────────────────────────────────────────────────┤
│  L5  TWIN SYNCHRONIZATION    Mode control · state mirroring · command     │
│                              routing · divergence measurement · calib.    │
├───────────────────────────────────────────────────────────────────────────┤
│  L4  ORCHESTRATION           Line coordinator · behaviour trees · task    │
│                              scheduling · handoff protocol · recovery     │
├───────────────────────────────────────────────────────────────────────────┤
│  L3  CAPABILITY (SKILLS)     MoveTo · Pick · Place · Transfer · Grasp ·   │
│                              Detect  — robot-agnostic action interfaces   │
├───────────────────────────────────────────────────────────────────────────┤
│  L2  CONTROL & HAL           ros2_control · controllers · MoveIt 2 ·      │
│                              hardware interfaces (sim plugin | real arm)  │
├───────────────────────────────────────────────────────────────────────────┤
│  L1  DESCRIPTION & ASSETS    URDF/Xacro · SDF · meshes · materials ·      │
│                              scanned geometry · generated worlds          │
├───────────────────────────────────────────────────────────────────────────┤
│  L0  FACILITY MODEL          The single declarative source of truth:      │
│                              assets · layout · topology · capabilities    │
└───────────────────────────────────────────────────────────────────────────┘
```

## The layers

The `Status` column below is a copy of each document's own `**Status:**` marker and nothing
more. **The marker in the document is the source of truth**; if the two disagree, this table
is the one that is wrong.

| Layer | Document | Owns | Status |
|---|---|---|---|
| L0 | [Facility model](L0-facility-model.md) | The single source of truth, and generation from it | `BUILT` |
| L1 | [Description and assets](L1-description-and-assets.md) | Geometry, kinematics, meshes, generated worlds | `PARTIAL` |
| L2 | [Control and HAL](L2-control-and-hal.md) | `ros2_control`, controllers, MoveIt 2, hardware interfaces | `PARTIAL` |
| L3 | [Capabilities](L3-capabilities.md) | Robot-agnostic skills as actions | `PARTIAL` |
| L4 | [Orchestration](L4-orchestration.md) | Behaviour trees, line coordination, handoff | `PARTIAL` |
| L5 | [Twin synchronization](L5-twin-synchronization.md) | Modes, mirroring, divergence, calibration | `DESIGNED` |
| L6 | [Data and telemetry](L6-data-and-telemetry.md) | Telemetry schema, recording, historian, replay | `DESIGNED` |
| L7 | [Presentation](L7-presentation.md) | Operator HMI, remote access | `DESIGNED` |

`DESIGNED` means the contract the code must satisfy, with nothing built. `PARTIAL` says
which part is real; read the document's status block, which names it. `BUILT` means tested.

## Cross-cutting

| Concern | Document |
|---|---|
| Naming and namespaces | [naming-and-namespaces.md](naming-and-namespaces.md) |
| Safety and interlocks | [cross-cutting-safety.md](cross-cutting-safety.md) |
| Lifecycle and bring-up | [cross-cutting-lifecycle.md](cross-cutting-lifecycle.md) |
| Testing strategy | [cross-cutting-testing.md](cross-cutting-testing.md) |
| Standards alignment | [standards-alignment.md](standards-alignment.md) |

## The dependency rule, concretely

An upward dependency usually appears as an import or a `package.xml` entry, so those are
where reviewers look first. Some real examples of violations:

- An orchestration package (L4) importing a hardware interface (L2) to "just check whether
  the arm is connected". It must ask through a skill (L3) or read published state.
- A skill (L3) reading a controller's internal parameters instead of using its interface.
- A description package (L1) importing the facility model loader (L0) at runtime.
  Descriptions are *generated from* L0 ahead of time; they do not consult it while running.
- A layer reaching around its neighbour — L4 talking directly to L2 — which is not upward
  but is still a boundary violation, and hides a missing skill at L3.

If a layer needs something from above, the design is wrong: either the responsibility is
in the wrong layer, or an interface is missing at the boundary.

## How to read a layer document

Each one has the same shape:

1. **Status** — `DESIGNED`, `PARTIAL`, or `BUILT`. See [`../README.md`](../README.md).
2. **Responsibility** — one paragraph. What this layer is *for*.
3. **Owns / does not own** — the boundary, stated explicitly. The second list matters more
   than the first.
4. **Interfaces** — what it consumes from below, what it exposes upward.
5. **Design** — how it works, and the decisions behind it, with ADR links.
6. **Failure modes** — what goes wrong here, and how it is detected. Written from the v1
   post-mortem and from what each layer's agent is configured to catch.
7. **Open questions** — what is genuinely undecided. Honesty here is worth more than the
   appearance of completeness.
