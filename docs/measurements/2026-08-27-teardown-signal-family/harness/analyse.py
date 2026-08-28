"""Count per-process bad exits across a set of scenario logs."""
import collections
import glob
import os
import re
import sys

DIED = re.compile(r"\[ERROR\] \[([^\]]+)\]: process has died \[pid \d+, exit code (-?\d+)")

def main(arm: str) -> None:
    root = os.path.dirname(os.path.abspath(__file__))
    logs = sorted(
        glob.glob(os.path.join(root, arm, "run*.log")),
        key=lambda p: int(re.search(r"run(\d+)", p).group(1)),
    )
    per_proc = collections.Counter()
    runs_with = collections.Counter()
    teardowns = collections.Counter()
    n = 0
    for path in logs:
        n += 1
        text = open(path, errors="replace").read()
        seen = set()
        for name, code in DIED.findall(text):
            base = name.rsplit("-", 1)[0]
            per_proc[(base, int(code))] += 1
            seen.add((base, int(code)))
        for key in seen:
            runs_with[key] += 1
        # how many teardown samples of each process this run contributed
        for base in ("skill_server", "move_group", "parameter_bridge", "gz"):
            teardowns[base] += len(
                set(re.findall(r"\[(%s-\d+)\]: process started" % base, text))
            )
    print(f"arm={arm}  runs={n}")
    leaks = 0
    for path in logs:
        leaks += open(path, errors="replace").read().count("SEVERE WARNING")
    print(f"class_loader leak warnings (expect 3/run pre-fix, 0 post-fix): {leaks}")
    print(f"{'process':22} {'code':>5} {'events':>7} {'runs':>6} {'teardowns':>10}")
    for (base, code), count in sorted(per_proc.items(), key=lambda kv: -kv[1]):
        print(f"{base:22} {code:>5} {count:>7} {runs_with[(base,code)]:>6} {teardowns[base]:>10}")
    print("\nteardown samples observed per process:")
    for base, count in sorted(teardowns.items()):
        print(f"  {base:22} {count}")

if __name__ == "__main__":
    main(sys.argv[1])
