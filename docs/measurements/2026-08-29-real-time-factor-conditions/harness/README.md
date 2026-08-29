# Harness — how `raw/` was produced

Everything here ran on the host in `../ANALYSIS.md`'s conditions block, against commit
`f1f914f` with the workspace built in that checkout immediately beforehand. The
data-collection scripts and `criteria.md` were hashed before the first trial;
[`../raw/FREEZE.txt`](../raw/FREEZE.txt) is that record.

| File | What it is |
|---|---|
| `rtf_probe.py` | The instrument. Runs **inside** the container. Launches one cell (or one scenario), streams `WorldStatistics` continuously from launch to teardown, waits on an **observed** readiness state, measures `joint_states` two ways, and writes `<label>.json` plus the whole `<label>.series.json` |
| `count_hz.py` | The second rate instrument: a keep-last-1000 subscriber counting arrivals over wall time, beside `ros2 topic hz` |
| `run_trial.sh` | One trial, from the host: records `docker stats` and `uptime` before and after, runs the probe, checks for and clears survivors |
| `cpu_limit_trial.sh` | Candidate C3 at 12 / 4 / 2 CPUs, applied with `docker update --cpus` to a running cell |
| `cpu_limit_trial_low.sh` | The follow-up C3 forced by the above: 2 / 1 / 0.5 CPUs. A separate file because `cpu_limit_trial.sh` had already produced data |
| `cpu_limit_rates.sh` | The second follow-up: `joint_states` measured **under** the 1-CPU limit, which needed the limit applied before the probe's window opened |
| `analyse.py` | Cuts every window from `raw/` and prints the tables. Host-side; needs no ROS |

Windows are cut in `analyse.py`, never at collection time, because the probe keeps the whole
series. That is what let the bring-up condition and the whole CPU curve come out of runs that
were happening anyway.

## Reproducing it

From the repository root, with the workspace built:

```
docs/measurements/2026-08-29-real-time-factor-conditions/harness/run_trial.sh IDLE_1 sim
docs/measurements/2026-08-29-real-time-factor-conditions/harness/run_trial.sh CYCLE_1 scenario pick_and_place
docs/measurements/2026-08-29-real-time-factor-conditions/harness/run_trial.sh LINE_1 scenario continuous_line
docs/measurements/2026-08-29-real-time-factor-conditions/harness/cpu_limit_trial.sh CPULIMIT_1
docs/measurements/2026-08-29-real-time-factor-conditions/harness/cpu_limit_trial_low.sh CPULOW_1
docs/measurements/2026-08-29-real-time-factor-conditions/harness/cpu_limit_rates.sh CPURATE_1
python3 docs/measurements/2026-08-29-real-time-factor-conditions/harness/analyse.py
```

The EARLY condition has no wrapper; it is the probe with the warm-up turned off:

```
./scripts/enter dev python3 \
  /workspace/docs/measurements/2026-08-29-real-time-factor-conditions/harness/rtf_probe.py \
  --label EARLY_1 \
  --out /workspace/docs/measurements/2026-08-29-real-time-factor-conditions/raw \
  --mode sim --warmup-s 0 --window-s 120 --hz-seconds 20
```

## Two things a later reader needs to know

**The three CPU scripts hard-code this checkout's compose project name** in the
`docker ps --filter` that finds the container (`cite-digital-twin-3748020299-dev-run`). That
name is a pure function of the checkout's absolute path — `cite_project_name` in
`scripts/_lib.sh` — so **these scripts will find nothing from a different checkout.** Per the
campaign convention they are left as they ran; derive the name with
`scripts/_lib.sh`'s function rather than editing them.

**The probe's own instruments sit inside its measurement window**, and they cost about 14 %
of real-time factor. This is Deviation 1 in the write-up and it is the reason section 4's
recipe says to keep instruments out of the window. It is left in place because it is what
produced `raw/`.
