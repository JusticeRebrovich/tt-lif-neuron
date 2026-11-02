![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# LIF Neuron: a digital leaky integrate-and-fire neuron in silicon

A small digital leaky integrate-and-fire (LIF) neuron written in Verilog and taken through the open-source
[Tiny Tapeout](https://tinytapeout.com) flow (SkyWater 130 nm, LibreLane) to a hardened GDS layout.

- **Top module:** `tt_um_justice_lif` (1x1 tile, 10 MHz target clock)
- **Source:** [`src/tt_um_justice_lif.v`](src/tt_um_justice_lif.v)
- **Datasheet and pin list:** [`docs/info.md`](docs/info.md)

## What it does

An 8-bit membrane voltage `V` updates every clock:

```
V_next = V - leak + I        leak = V >> 4, forced to at least 1 while V > 0
```

| Behavior | Implementation |
| --- | --- |
| Integrate | 8-bit input current on `ui[7:0]` is added to `V` each cycle |
| Leak | `V >> 4` (a shift, so no multiplier), never less than 1, so `V` always decays to 0 |
| Saturate | The add clamps at 255 instead of wrapping |
| Fire | One-cycle spike on `uo[0]` when `V` reaches the threshold (200), then `V` resets to 0 |
| Refractory | Input is ignored for 4 cycles after a spike |

Threshold, leak shift and refractory length are Verilog parameters (`THRESHOLD`, `LEAK_SHIFT`, `REFRAC`).

## Pinout

| Pins | Function |
| --- | --- |
| `ui[7:0]` | Input current `I` |
| `uo[0]` | Spike |
| `uo[7:1]` | Membrane voltage `V[7:1]` |
| `uio[7:0]` | Unused |

## Verification

The design is checked cycle by cycle against a Python golden model ([`test/lif_model.py`](test/lif_model.py))
with [cocotb](https://www.cocotb.org). The same tests run on the RTL and on the gate-level netlist after
synthesis. To run the RTL simulation locally:

```bash
cd test
make -B
```

## Implementation results

From the GitHub Actions build (`gds` workflow):

- 149 standard cells, about 8.3% utilization of the 1x1 tile
- Gate-level simulation passes
- 15/15 Tiny Tapeout precheck items pass

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
