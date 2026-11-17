![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# LIF Spiking Pattern Generator: four leaky integrate-and-fire neurons in silicon

Four digital leaky integrate-and-fire (LIF) neurons wired in a ring, written in Verilog and taken through the
open-source [Tiny Tapeout](https://tinytapeout.com) flow (SkyWater 130 nm, LibreLane). Neuron 0 is driven by the
input pins and every spike kicks the next neuron, giving travelling or self-sustaining spike patterns.

- **Top module:** `tt_um_justice_lif` (1x1 tile, 10 MHz target clock)
- **Source:** [`src/tt_um_justice_lif.v`](src/tt_um_justice_lif.v)
- **Datasheet and pin list:** [`docs/info.md`](docs/info.md)

## What it does

Each neuron's 8-bit membrane voltage `V` updates every clock:

```
V_next = V - leak + I        leak = V >> 4, forced to at least 1 while V > 0
```

| Behavior | Implementation |
| --- | --- |
| Integrate | The input current is added to `V` each cycle: `ui[7:0]` for neuron 0, a kick from the previous neuron for the others |
| Leak | `V >> 4` (a shift, so no multiplier), never less than 1, so `V` always decays to 0 |
| Clamp | The result is clamped to 0..255 instead of wrapping |
| Fire | One-cycle spike when `V` reaches the threshold (200), then `V` resets to 0 |
| Refractory | Input is ignored for 4 or 3 cycles after a spike (`MODE` pin) |

The ring weight (`uio[1:0]`: 0, 64, 128 or 255) sets how hard one spike kicks the next neuron. At 255 a spike hops
around the ring one clock at a time. With `MODE = 1` it keeps circulating with no further input.

A built-in self-test (BIST) lets the chip check itself: an on-chip LFSR drives all four neurons for 1024 clocks, a
signature register compresses every voltage and spike, and one pin reports pass or fail. Details are in
[`docs/info.md`](docs/info.md).

## Pinout

| Pins | Function |
| --- | --- |
| `ui[7:0]` | Input current `I` to neuron 0 |
| `uo[0]` | Neuron 0 spike |
| `uo[7:1]` | Neuron 0 membrane voltage `V[7:1]` |
| `uio[1:0]` | Input: ring weight select |
| `uio[2]` | Input: refractory mode (0 = 4 cycles, 1 = 3 cycles) |
| `uio[3]` | Input: run the built-in self-test (`uo[0]` = DONE, `uo[1]` = PASS, `uo[7:2]` = signature bits) |
| `uio[4]` | Input: with the self-test on, show the signature high byte on `uo`. With it off, `uo` reads 0 (reserved page) |
| `uio[7:5]` | Output: spikes of neurons 3, 2, 1 |

## Verification

The design is checked cycle by cycle against Python golden models with [cocotb](https://www.cocotb.org):
[`test/lif_model.py`](test/lif_model.py) for one neuron, [`test/ring_model.py`](test/ring_model.py) for the ring and
[`test/chip_model.py`](test/chip_model.py) for every pin of the chip, including the self-test. The test files are
`test_lif.py`, `test_ring.py` and `test_bist.py`. They also run on the gate-level netlist after synthesis, where
only the pins are visible, so internal voltages are checked in RTL simulation only.

`python run.py` in `test/` runs everything, plus 17 deliberately altered builds on which the self-test must report
FAIL: one with a wrong threshold, and one for each bit of the expected signature. The template flow runs the three
test files:

```bash
cd test
make -B
```

## Implementation results

From the GitHub Actions builds (`gds` workflow). Gate-level simulation and all 15 Tiny Tapeout precheck items pass
for the rows with numbers.

| Design | Standard cells | Flip-flops | Utilization of the 1x1 tile |
| --- | --- | --- | --- |
| Single neuron (`main`) | 149 | 12 | 8.3% |
| Four-neuron ring with refractory mode | 431 | 48 | 27.7% |
| Ring plus first self-test | 671 | 83 | 42.6% |
| Ring plus improved self-test | 936 | 83 | 61.2% |

### Self-test fault coverage

An independent review injected single faults into the RTL and ran the self-test on each one.

| Self-test | Faults detected, of 193 | Real faults that still read PASS | Coverage of testable faults |
| --- | --- | --- | --- |
| First version: only neuron 0 driven | 130 | 41 | 76% |
| Improved: every neuron driven and observed | 174 | 1 | 99.4% |

The remaining faults are in logic that no stimulus can reach from the pins. The one real hole needed the ring to
keep its self-test state afterwards; the neurons are now reset when the self-test is switched off. That last change
has not been re-measured. [`test/bist_faultsim.py`](test/bist_faultsim.py) is the small fault simulator used to tune
the stimulus.

Development notes are in [`docs/devlog`](docs/devlog).

## Repository layout

```
src/        Verilog source and LibreLane config
test/       cocotb testbench, golden model, gate-level runner
docs/       Datasheet (info.md) used by the Tiny Tapeout project page
info.yaml   Tiny Tapeout project metadata and pinout
```

## About

Written by Justice Rebrovich (University of North Dakota, B.S. Electrical Engineering) as a hands-on
introduction to digital IC design and design verification. Built from the
[Tiny Tapeout Verilog template](https://github.com/TinyTapeout/ttsky-verilog-template). Licensed under Apache-2.0.
