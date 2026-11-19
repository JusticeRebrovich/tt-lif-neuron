# Dev log: final checks on the merged design (2026-11-18)

`main` and `pattern-generator` now point at the same history. The design is the four-neuron ring with the reworked self-test and the neuron reset on self-test exit (source last changed in 611d810).

## GitHub Actions results

| Commit | What changed | Result |
|---|---|---|
| 611d810 | Neuron reset on self-test exit, 16 comparator-bit builds | `test`, `docs`, `gds` passed |
| 53eaabe | README rewrite, merged into `main` | `gds` first failed after 2 m 47 s: the PDK download in `ciel.fetch` hit `httpx.ReadError: Connection reset by peer`. Re-run passed |

Implementation figures from the `gds` summary (identical for 611d810 and the re-run on 53eaabe):

| Metric | Value |
|---|---|
| Standard cells, excluding fill and tap | 930 |
| Flip-flops | 83 |
| Utilization | 61.03% |
| Routed wire length | 21,874 µm |
| Prechecks | 15 of 15 |
| Gate-level test | Passed |

These replace the 936 cells, 61.2% and 22,785 µm measured on e0a20d1, before the exit reset.

## Independent review of the final design (commit c580f61): PASS

- The exit reset matches its spec: about 247,000 BIST-heavy cycles and 99,000 ring cycles with 0 pin and 0 internal mismatches. The same vectors give over 6,700 pin mismatches against a model without the exit reset, so they exercise the change.
- **The last coverage hole is closed.** Neuron 0's upper-clamp fault no longer has any pin-visible effect in a reachable state. In normal mode a kick from neuron 3 always lands on neuron 0 at V = 0, so its current is at most 510.
- **Final self-test coverage: 174 of 174 testable faults (100%)** on the original 193-fault list, with 19 redundant faults. On the reviewer's extended list, 506 of 533 single faults are detected. The misses are logic no stimulus reaches, plus the four input selectors stuck on the self-test side, which normal-mode pin tests cover.
- All comparator mutants that survived before are now caught by the 16 signature-bit builds. All six exit-reset mutants are caught.
- `python run.py`: 20 of 20 tests, and FAIL reported on 17 of 17 altered builds. Gate-level emulation: 20 of 20. Lint clean.
- `test/bist_faultsim.py` reproduces 108 of 151 and 154 of 154. `images/make_figures.py` regenerates the committed SVGs byte for byte.

The review also audited the README, and these statements were corrected:

- The first self-test missed 42 real faults, not 41 (130 of 172 testable).
- The coverage table and figure now include the final 100% row.
- The GTKWave screenshot is from the original single-neuron RTL (9-bit sum). The current sum is 11 bits signed.
- Timing comes from the e0a20d1 build, not "one commit earlier".
- The utilization and coverage charts plot measured numbers; only the waveform, ring and self-test figures come from the golden models.
- Only the ring and chip tests check `uio_oe`.

## Still open

- Max-slew warning at the slow corners ([timing log](2026-11-16-timing-and-slew.md)): accepted for now.
- Submission on app.tinytapeout.com.
- The fabricated chip has not been tested.
