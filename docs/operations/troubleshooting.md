# Troubleshooting

- **Status:** `PARTIAL` — the "Start here" and "Environment" sections describe tooling that
  exists today and can be run now. The "Build" and "Runtime" sections describe a system
  that is not built yet. No section is covered by an automated test.

## Start here, always

```bash
./scripts/doctor
```

It distinguishes **failed** from **skipped**. Skipped items do not exist at the current
phase and are expected; failures are not. Most "nothing works" reports are a failed row in
`doctor` that nobody ran.

Second, before anything clever:

```bash
./scripts/clean && ./scripts/bootstrap && ./scripts/build
```

A stale build explains a genuinely surprising share of inexplicable failures. Rule it out
early rather than after two hours.

## Environment

### `./scripts/build` seems to hang on macOS

It is building the container image, which takes minutes on a first run. `_lib.sh` warns
before this, but the warning scrolls. Run `./scripts/bootstrap` explicitly to do it as a
visible step.

### `No suitable Python found`

The pinned dependencies have wheels for Python 3.10–3.13 only. Bootstrap prefers 3.12 to
match the container.

```bash
brew install python@3.12          # macOS
sudo apt install python3.12 python3.12-venv   # Ubuntu
```

### `cite_tools` not importable

```bash
./scripts/bootstrap --host-only
```

### Docker daemon not running

Start Docker Desktop, or `sudo systemctl start docker`.

## Build

### `c++: fatal error: Killed signal terminated program cc1plus`

The OOM killer, not a compiler bug and not a code error. A translation unit that includes
generated ROS message headers routinely needs 2-3 GB, and the default one-worker-per-core
parallelism multiplies that by the core count.

`./scripts/build` derives its job count from **available memory** rather than from core
count and reports the number it chose, so this should be rare. When it still happens:

```bash
CITE_BUILD_JOBS=1 ./scripts/build
```

and give Docker Desktop more memory (Settings → Resources). Building the full vendor
`xarm_ros2` stack peaks near 6 GB in a single job, so a Docker VM below about 8 GB will be
tight regardless of the job count.

### `ModuleNotFoundError: No module named 'catkin_pkg'`

An ament build is running under the host-agnostic tooling virtualenv instead of the system
Python. The two environments are deliberately separate (`requirements/README.md`): ROS
Python comes from apt, the tooling venv comes from pip, and the venv is kept **off** the
`PATH` for exactly this reason.

Check which interpreter is in front:

```bash
./scripts/enter dev
command -v python3          # must be /usr/bin/python3, not /opt/cite-venv/bin/python3
```

If a previous build already cached the wrong interpreter, CMake will keep using it from
`CMakeCache.txt` even after the `PATH` is fixed — so clean before retrying:

```bash
./scripts/clean && ./scripts/build
```

### The build fails on an apt package that bootstrap just installed

Containers are ephemeral. `./scripts/build` and CI each run a fresh `docker run --rm`, so
anything `rosdep install` puts in a container at run time is gone when that container
exits. The image resolves `external/cite.repos`'s system dependencies at **image build**
time for this reason.

If you changed the manifest, rebuild the image:

```bash
./scripts/bootstrap
```

### A change to a script or the environment appears to have no effect

`compose` mounts named volumes over `workspace/{build,install,log}`, so the copies of those
directories you can see on the host are empty and deleting them changes nothing.
`./scripts/clean` empties the volumes themselves; plain `rm -rf workspace/build` does not.

### Package not found after building

The overlay is not sourced. Inside the container the entrypoint does it; outside:

```bash
source workspace/install/setup.bash
```

### Changes not taking effect

`--symlink-install` means Python changes take effect without rebuilding, and C++ changes do
not. When in doubt about which copy is loaded, `./scripts/clean && ./scripts/build`.

### `rosdep` reports unresolved dependencies

A dependency is used but not declared in `package.xml`. Declare it. It works on your
machine because you installed it once, and fails everywhere else.

## Runtime

### A topic exists but no data arrives

**Suspect QoS first.** This is the most-misdiagnosed failure in ROS 2.

```bash
ros2 topic info /cite/... --verbose
```

Compare reliability, durability, and history on both sides. A best-effort publisher and a
reliable subscriber never connect, and nothing reports it. See
[`../interfaces/qos-profiles.md`](../interfaces/qos-profiles.md).

### Nodes cannot see each other

- `ROS_DOMAIN_ID` differs between shells, or collides with somebody else's session in the
  lab. A collision makes another person's nodes appear in your graph, producing behaviour
  no code in the repository explains.
- `RMW_IMPLEMENTATION` differs between processes.
- Container networking: DDS discovery does not cross Docker's default bridge reliably.

### A controller will not activate

Almost always joint names in the controller config not matching the description. The
spawner error names the spawner, not the mismatch.

```bash
./scripts/validate-model      # checks this statically
```

Otherwise the controller manager was not ready — which under lifecycle sequencing should
be impossible, so if you see it, that is a defect in bring-up.

### Timeouts, TF extrapolation errors, "random" failures

Suspect `use_sim_time`. One node on the wall clock and another on the simulation clock
produces exactly this family of symptoms, all of them pointing away from the cause.

### The simulation is slow

```bash
gz sim --versions      # confirm Harmonic
```

Then suspect collision geometry. A dense visual mesh reused as collision geometry is the
most common cause of a collapsed real-time factor by a wide margin. `model-validator`
catches it; `performance-engineer` measures it.

### Bring-up fails on the second attempt

Orphaned processes from the first.

```bash
pgrep -fl "gz sim|controller_manager"
```

Kill them. An orphan holds ports and names, and the resulting failure points nowhere near
the cause.

## When none of this helps

Delegate to the `debugger` agent. It carries the full trap list for this stack, isolates
the noisy trial-and-error loop from the main conversation, and is required to **prove** a
root cause rather than report a plausible hypothesis.

Give it: the full error, what you were doing, what you expected, what you already ruled
out.
