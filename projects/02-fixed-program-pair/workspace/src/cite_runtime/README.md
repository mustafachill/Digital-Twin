# cite_runtime

Process lifecycle for this repository's Python nodes: start rclpy, spin until the
context is shut down, release it. Nothing else lives here.

```python
from cite_runtime import runtime


def main() -> None:
    runtime.init()
    node = MyNode()
    try:
        runtime.spin(node)
    finally:
        runtime.shutdown(node)
```

## Admission test

Something belongs in this package only if all three hold:

1. it is process lifecycle **mechanism** — start-up, shutdown, signals;
2. it carries **no domain knowledge** — no facility, asset, topic or layer of the
   L0-L7 stack is nameable from inside it;
3. it **depends on nothing in-project** — rclpy and the standard library only, so
   that every other package may depend on it without creating a direction.

Test dependencies obey rule 3 as well. The tests here drive a probe node this
package owns rather than a node borrowed from a package that has one, because a
test edge is still an edge.

`ADR-0034` records the decision and what was weighed against it.

## Constraint on adoption

This pattern absorbs SIGINT rather than letting it raise. For a graceful stop
that is the safer design — it is what lets a teardown finish instead of being
torn apart by an asynchronous exception. The cost is that **a callback which does
not return is no longer interruptible by Ctrl-C at all**, and the only backstop
is `launch`'s SIGKILL at `sigterm_timeout + sigkill_timeout`.

So: this is for a process that commands no actuator. A process that commands one
must additionally guarantee that no callback can block unbounded, or install its
own hard-stop path that does not depend on this module's shutdown. The module
docstring carries the measurements behind that sentence.

## Tests

`test/test_shutdown_under_signal.py` spawns a probe under `sigint_tripwire.py`,
which places SIGINT inside the generated `Clock` conversion — the one instant
that used to decide the exit code. It asserts both directions: the `runtime`
idiom exits 0, and the idiom it replaced still fails there. It runs on a DDS
domain private to the test process, because it publishes `/clock` and the ambient
domain may have a cell on it.
