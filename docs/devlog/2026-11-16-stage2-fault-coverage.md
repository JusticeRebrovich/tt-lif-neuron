# Dev log: stage 2 fault coverage (2026-11-16)

Branch: `pattern-generator`. Follows [stage 2](2026-11-16-stage2-bist.md).

## Results for the first self-test (commit a400fb2)

GitHub Actions: `test`, `docs`, hardening and the real gate-level test passed.

| Design | Cells | Flip-flops | Wire length | Utilization |
|---|---|---|---|---|
| Single neuron (`main`) | 149 | 12 | 2,676 µm | 8.3% |
| Four-neuron ring | 431 | 48 | 7,727 µm | 27.7% |
| Ring plus first self-test | 671 | 83 | 12,843 µm | 42.6% |

## The verifier's review: FAIL on fault coverage

The RTL matched the spec everywhere: about 245,000 cycles on each of 3 seeds with 0 mismatches, and `chip_model.py` matched an independent model over 1,200,000 cycles.

The failure was in what the self-test could detect. The verifier built 193 copies of the design with one fault each and ran the self-test on every one.

| Outcome | Count |
|---|---|
| Self-test reports FAIL | 130 |
| Undetectable by any test (redundant logic, or not visible on pins) | 22 |
| Real faults that still read PASS | 41 |

Coverage: 130 of 171 testable faults, 76%.

### Why 41 faults escaped

Only neuron 0 was driven by the LFSR. Neurons 1 to 3 received nothing but kicks, and the signature saw only spikes and V0[7:4].

- Neurons 1 to 3 fired almost only from one full-strength kick landing on V = 0. Their voltage registers, leak and thresholds were barely exercised.
- Neuron 3 never fired by accumulating charge, so even a stuck top bit in its voltage register passed.
- A shortened refractory period on neurons 1 to 3 was never exercised, because neuron 0's own refractory period spaced the kicks.

A correction to the stage 2 log: "a threshold that is off by one changes the signature" was true only when all four neurons were off together. Single-neuron off-by-one faults were missed on every neuron.

## The fix

1. **Drive every neuron.** During the self-test each neuron gets its own current from a different view of the LFSR: as is, nibbles swapped, bits reversed, inverted.
2. **Four amplitude levels,** rotating every 32 clocks, one step out of phase between neighbours:
   - quiet: V decays, which tests the leak down to rest
   - creep (12 to 19): V hovers near the threshold, which tests the threshold exactly
   - small (0 to 31)
   - full (0 to 255): tests saturation and the refractory period
3. **Observe every neuron.** The signature register now folds in all 32 voltage bits and the 4 spikes each clock.

The stimulus was tuned with a small Python fault simulator before any RTL changed. It reproduced the verifier's misses for the old stimulus, then measured each candidate:

| Stimulus | Faults detected (my fault list) |
|---|---|
| Old: neuron 0 only, spikes and V0[7:4] observed | 108 of 151 |
| All neurons driven, tiny level 0 to 7 | 149 of 154 |
| Creep level 8 to 15 | 152 of 154 |
| **Creep level 12 to 19** | **154 of 154** |

My fault list is not the verifier's, so these numbers are a guide. The verifier's re-measurement is the result that counts.

New golden signature: `0x53DF`. Spikes per neuron during the self-test went from 115, 50, 40, 37 to 110, 109, 109, 111.

## Other fixes from the review

- **PASS comparator width.** Two extra builds change one bit of the expected signature (bit 15, and bit 6, which no page shows). The self-test must report FAIL on both.
- `run_gl.py` now runs `test_bist` too.
- Docs: the reserved page, the exact 1025-clock timing, that the ring keeps running during the test, and that signature bits 7:6 are not readable.

## Results after the fix

RTL simulation: 20 of 20 on the normal build, and 3 of 3 altered builds report FAIL as required. Icarus `-Wall` lint is clean.

## Verifier re-measurement (commit e0a20d1): PASS

Same 193-fault list as before, so the numbers compare directly.

| | First self-test | Improved self-test |
|---|---|---|
| Detected | 130 | 174 |
| Redundant (no stimulus can expose them) | 18 | 18 |
| Unobservable at the pins | 3 | 0 |
| Real faults that still read PASS | 41 (42 after the correction below) | 1 |
| Coverage of testable faults | 76% | 174 of 175, 99.4% |

- All 41 earlier holes are closed, and the three previously unobservable faults are detected, because the signature now sees every voltage bit.
- On the verifier's extended list of 533 single faults, including faults in the new stimulus logic, 506 are detected.
- No aliasing was found. All 200 random double faults were detected.
- Negative current, and a sum of 512 or more, are still never produced during the self-test.

Corrections to the numbers above in this log: one fault the verifier first classed as redundant was a real corner-case hole (a clamp term on neuron 0, reachable only by leaving the self-test mid-run without a reset). So the first table's "22 undetectable" should read 21, and its "41 real" should read 42.

The verifier also pointed out that my 154 of 154 could not be reproduced, because the fault simulator was not in the repo. It is now: `test/bist_faultsim.py` prints 108 of 151 for the first stimulus and 154 of 154 for the final one, and asserts that its healthy signature equals the golden model's.

## GitHub Actions on e0a20d1

`test`, `docs`, hardening, the real gate-level test and 15 of 15 prechecks passed.

| Design | Cells | Flip-flops | Wire length | Utilization |
|---|---|---|---|---|
| Ring plus first self-test | 671 | 83 | 12,843 µm | 42.6% |
| Ring plus improved self-test | 936 | 83 | 22,785 µm | 61.2% |

Better fault coverage cost about 19 points of utilization: four amplitude selectors, three more adders for the direct currents, and a wider signature input. At 61% the design is above the flow's 60% placement-density setting, so no more logic is planned.

## Cleanup after the re-measurement

- **Neurons are reset when the self-test is switched off.** This removes the route to the last real hole. Not re-measured by the verifier.
- **The PASS comparator is now checked bit by bit.** The verifier showed that two altered builds (bits 15 and 6) left a comparator that ignored the other 14 bits undetected. There are now 16 builds, one per signature bit.
- `run.py` prints a one-line summary.

RTL simulation after the cleanup: 20 of 20 on the normal build, and the self-test reports FAIL on 17 of 17 altered builds.

## Open

- Hardening and gate-level results for the cleanup commit.
- Timing: no slack figures have been read yet.
- A self-test cannot see its own normal/test input selectors stuck on the test side. Normal-mode pin tests cover that on silicon.
