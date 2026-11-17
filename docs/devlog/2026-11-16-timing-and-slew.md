# Dev log: timing and the max-slew warning (2026-11-16)

Branch: `pattern-generator`. Numbers are from the GitHub Actions build of commit e0a20d1 (ring plus improved self-test, 61.2% utilization), read from the `GDS_logs` artifact: `final/metrics.json` and `55-openroad-stapostpnr/max_ss_100C_1v60/checks.rpt`.

## Sign-off timing

The flow constrains the clock to 20 ns (50 MHz). The design's intended clock is 100 ns (10 MHz).

| Check | Typical corner (tt, 25 °C, 1.80 V) | Slowest corner (ss, 100 °C, 1.60 V) |
|---|---|---|
| Setup, worst slack | 7.97 ns | 0.023 ns |
| Setup, worst register-to-register slack | not reported | 9.61 ns |
| Hold, worst slack | 0.317 ns | 0.906 ns |
| Max slew violations | 0 | 194 |
| Max capacitance violations | 0 | 0 |

- No setup or hold violations in any of the nine corners. The smallest hold slack across all corners is 0.112 ns.
- The 0.023 ns worst setup slack at the slowest corner is on a path through the I/O pins, which the flow constrains with a generic fallback (20% of the clock period as I/O delay). Register-to-register paths have 9.6 ns to spare there. At the intended 100 ns clock every path has a large margin.
- Antenna, LVS and DRC passed. One antenna diode was inserted.

## The max-slew warning

Slew is how long a signal edge takes to rise or fall. The library limit is 0.75 ns.

- 194 pins exceed it, only at the three slow corners (ss, 100 °C, 1.60 V). The typical and fast corners have none.
- The worst slew is 1.159 ns, 54% over the limit.
- The warning first appeared when the self-test was added. The four-neuron ring alone (27.7%) had none.

### Which nets

The violating pins are loads on high-fanout nets, all in the self-test logic:

- LFSR bits (for example `lfsr[5]`, `lfsr[2]`). Each bit feeds four stimulus patterns and their amplitude selectors.
- The selectors between the pins and the self-test: `bist_cnt[7]` (mode) and `bist_cnt[9]` (weight) against the pin values.

The tool split these nets with fanout buffers, and the buffers it picked are `clkdlybuf4s25_1`, a size-1 delay buffer with a weak output. Weak drivers on many loads are what make the slow edges.

### How much it matters

- The timing analysis already includes these slow edges, and setup and hold still pass, so this is not a functional failure in simulation or sign-off timing.
- Slow edges cost some power and noise margin, at the hot, low-voltage corner only.
- Tiny Tapeout's flow configuration sets `MAX_SLEW_VIOLATION_CORNERS` to an empty list, so slew violations are reported as a warning and never fail the build. The 15 prechecks passed.

### Other warnings checked

- **"2 floating nets"**: present in every build, including the ring alone. The log names `VGND` straight after the warning, so these appear to be the power nets as seen by the resizer, not signal nets. The final metrics report 0 floating pins.
- **Max fanout, 1 violation**: the clock root buffer drives 16 loads against a limit of 10.
- **Placement density**: the placer reported the 0.60 target as too low for this design and raised it to 0.62. The tile is full enough that no more logic should be added.

## Decision

Open. The options are to accept the warning as documented here, or to try reducing fanout on the LFSR nets (in the RTL, or with a flow setting) on a separate branch and compare.
