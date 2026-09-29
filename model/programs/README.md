# Programs

Programs the cell runs, as the real robot's own programming tool wrote them. The
twin reads them; nothing here is written by hand (ADR-0067).

## `xarm5_real_demo.blockly.xml`

The UFACTORY Studio Blockly program that drives the real xArm 5 on its linear
track. It is **read-only**: `tools/tests/test_real_program_is_pinned.py` pins its
sha256, so an edit fails the host test suite. To change the program, change it on
the real robot, export it again, and replace this file byte for byte.

Provenance, recorded when it was copied on 2026-09-29:

| What | Value |
|---|---|
| Source archive | `blockly-xArm5-RealDemo.tar.gz` (UFACTORY Studio project export) |
| Archive sha256 | `68982e4ffa7f56506517264243037f28a48cb0ede6122d75812345bf725cffd9` |
| Member copied | `./app.xml`, byte for byte |
| `app.xml` sha256 | `998e3d2eec6d32f56e08e86ce1f28ea4c5261632c9bfe2c9070c9c2860e79887` |

A second export, `xArm5-RealDemo.gz` (sha256
`28a96a9a28976fdabec87150e6e6a94c596fb4f38566f7d86df645341d6eea4c`), carries a
byte-identical `app.xml`. Both archives also carry `app_bak.xml`, an older version
of the program, which is not used. The archives themselves stay outside git.

`cite_tools.model.blockly` is the reader. It accepts only the block types this
program uses and refuses anything else, so a program edited on the robot to use a
block the twin does not model fails `./scripts/validate-model` instead of being
approximated.
