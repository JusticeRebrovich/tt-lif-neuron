# Dev log: stage 1 verifier review and fixes (2026-11-16)

Branch: `pattern-generator`. Follows [stage 1](2026-11-16-stage1-ring.md).

## Independent review of commit 023e273

An independent verifier agent checked the stage 1 design against its written spec, using its own reference model and testbenches. Verdict: **FAIL**.

| Check | Result |
|---|---|
| RTL matches spec: all 262,144 neuron cases (every V, every signed input), about 82,000 top-level cycles on each of 5 seeds | Pass, 0 mismatches |
| Golden models match spec: 1,000,000 cycles | Pass, one latent gap |
| Existing tests sound | Partial fail |
| Gate-level flow | Pass in emulation only |
| Lint (Icarus `-Wall`) | Pass |
| Docs and pin metadata | Fail, stale |

### Defects found

1. **The ring never closed.** Neurons 1 to 3 fire 1, 2 and 3 clocks after neuron 0. The kick from neuron 3 therefore always reached neuron 0 on the last cycle of its 4-cycle refractory period and was ignored. The link from neuron 3 back to neuron 0, and the adder for it, were dead logic.
2. **`uio_oe` was never checked.** A mutant with `uio_oe = 0` passed all 11 tests. On silicon that would silence the spike pins.
3. **Other pin rules untested:** `uio_out[4:0] == 0`, and that `ena` and the unused `uio_in` bits are ignored. Mutants for each passed.
4. **`LifModel` had no floor at 0** for negative current. Unreachable today, but it would diverge once inhibition is added.
5. **Stale files:** `info.yaml`, `docs/info.md`, `README.md`, `test/run_gl.py`.

The mutation testing is the useful lesson: passing tests only prove what the tests look at.

## Fixes

- **Refractory mode pin, `uio_in[2]`.** 0 keeps the 4-cycle refractory period (one pass per wave, input sets the rhythm). 1 selects 3 cycles, so the kick from neuron 3 lands just after neuron 0 recovers, and at weight 255 one spike circulates forever. The ring-closing link is now live logic with a use.
- **Tests:** every cycle now also checks `uio_oe`, `uio_out[4:0]` and `uo_out[7:1]`. The random test drives random `ena`, random junk on `uio_in[7:3]` and random mode changes. Two new tests cover the two modes.
- **Model:** `LifModel` clamps to 0..255.
- **Docs:** `info.yaml`, `docs/info.md`, `README.md` and `run_gl.py` updated.

Prototype of the two modes, one kick at t = 0 and no input after:

```
mode 0 (refractory 4)
  n0 |...............................
  n1 .|..............................
  n2 ..|.............................
  n3 ...|............................
mode 1 (refractory 3)
  n0 |...|...|...|...|...|...|...|...
  n1 .|...|...|...|...|...|...|...|..
  n2 ..|...|...|...|...|...|...|...|.
  n3 ...|...|...|...|...|...|...|...|
```

## Results after the fixes

RTL simulation: `TESTS=13 PASS=13 FAIL=0`.

One of my new tests failed on its first run, because it wrote `ena` during the simulator's read-only phase. That was a test bug, fixed by removing the write.

GitHub Actions on 023e273 (before these fixes): `test` passed, and the `gds` run (hardening, precheck, gate-level test) finished with status Success.
