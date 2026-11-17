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

## Pinout

| Pins | Function |
| --- | --- |
| `ui[7:0]` | Input current `I` to neuron 0 |
| `uo[0]` | Neuron 0 spike |
| `uo[7:1]` | Neuron 0 membrane voltage `V[7:1]` |
| `uio[1:0]` | Input: ring weight select |
| `uio[2]` | Input: refractory mode (0 = 4 cycles, 1 = 3 cycles) |
| `uio[4:3]` | Unused |
| `uio[7:5]` | Output: spikes of neurons 3, 2, 1 |

## Verification

The design is checked cycle by cycle against Python golden models ([`test/lif_model.py`](test/lif_model.py) for one
neuron, [`test/ring_model.py`](test/ring_model.py) for the ring) with [cocotb](https://www.cocotb.org). The same
tests run on the RTL and on the gate-level netlist after synthesis. To run the RTL simulation locally:

```bash
cd test
make -B
```

## Implementation results

From the GitHub Actions build (`gds` workflow) of the original single-neuron design:

- 149 standard cells, about 8.3% utilization of the 1x1 tile
- Gate-level simulation passes
- 15/15 Tiny Tapeout precheck items pass

Figures for the four-neuron ring will replace these once its build is measured. Development notes are in
[`docs/devlog`](docs/devlog).

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
