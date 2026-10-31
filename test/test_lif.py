"""cocotb tests for the LIF neuron.
Every test drives inputs on the falling edge and checks the DUT against the
Python golden model right after the rising edge, every cycle."""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge

from lif_model import LifModel


async def setup(dut):
    """Start a 10 ns clock and hold reset for 3 cycles."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.ena.value = 1
    dut.uio_in.value = 0
    dut.ui_in.value = 0
    dut.rst_n.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1
    return LifModel()


def read_v(dut):
    """Return (v, mask) for comparing V against the model.
    RTL sim can see the internal register dut.v, so all 8 bits are checked.
    The gate-level netlist has no dut.v, so rebuild bits 7:1 from uo_out and
    mask out bit 0, which is not wired to any output pin."""
    try:
        return int(dut.v.value), 0xFF
    except AttributeError:
        return (int(dut.uo_out.value) >> 1) << 1, 0xFE


async def pulse_reset(dut, model):
    """Assert reset for one cycle, then release it with input 0.
    The release edge is stepped in the model too, so DUT and model never drift."""
    await FallingEdge(dut.clk)
    dut.rst_n.value = 0
    dut.ui_in.value = 0
    model.reset()
    await RisingEdge(dut.clk)
    await ReadOnly()
    v, mask = read_v(dut)
    assert v & mask == 0 and (int(dut.uo_out.value) & 1) == 0, "reset did not clear state"
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1
    model.step(0)
    await RisingEdge(dut.clk)
    await ReadOnly()
    v, mask = read_v(dut)
    assert v & mask == model.v & mask


async def drive(dut, model, i):
    """Apply input i for one cycle, step the model, and compare."""
    await FallingEdge(dut.clk)
    dut.ui_in.value = i
    model.step(i)
    await RisingEdge(dut.clk)
    await ReadOnly()
    dut_v, mask = read_v(dut)
    dut_spike = int(dut.uo_out.value) & 1
    assert dut_v & mask == model.v & mask, f"V mismatch: DUT {dut_v}, model {model.v} (input {i})"
    assert dut_spike == model.spike, f"spike mismatch: DUT {dut_spike}, model {model.spike}"
    assert (int(dut.uo_out.value) >> 1) == (model.v >> 1), "uo_out[7:1] must show V[7:1]"
    # model.v equals the DUT's V in RTL sim, and also covers bit 0 in gate-level sim
    return model.v, dut_spike


@cocotb.test()
async def test_decay_to_rest(dut):
    """Charge up, then remove input. V should leak back to 0 and never spike."""
    model = await setup(dut)
    for _ in range(2):
        await drive(dut, model, 50)
    history = []
    for _ in range(100):
        v, s = await drive(dut, model, 0)
        assert s == 0, "spiked with no input"
        history.append(v)
    assert all(b <= a for a, b in zip(history, history[1:])), "V must never rise with no input"
    assert history[-1] == 0, f"V should decay to 0 at rest, but it settled at {history[-1]}"


@cocotb.test()
async def test_constant_input_periodic(dut):
    """Constant input should produce spikes at a fixed, repeatable interval."""
    model = await setup(dut)
    spike_cycles = []
    for cyc in range(200):
        _, s = await drive(dut, model, 30)
        if s:
            spike_cycles.append(cyc)
    assert len(spike_cycles) >= 3, "expected several spikes"
    gaps = {b - a for a, b in zip(spike_cycles, spike_cycles[1:])}
    assert len(gaps) == 1, f"spike interval not constant: {sorted(gaps)}"
    dut._log.info(f"input 30 -> one spike every {gaps.pop()} cycles")


@cocotb.test()
async def test_saturation(dut):
    """Input 100 for three cycles: 100, 194, then 182+100=282.
    With saturation that clamps to 255 and spikes. If the add wrapped, it would be 26 and miss the spike."""
    model = await setup(dut)
    v, s = await drive(dut, model, 100)
    assert (v, s) == (100, 0)
    v, s = await drive(dut, model, 100)
    assert (v, s) == (194, 0)
    v, s = await drive(dut, model, 100)
    assert s == 1, "overflow wrapped instead of saturating, spike missed"


@cocotb.test()
async def test_refractory(dut):
    """After a spike, max input is ignored for exactly 4 cycles, then it fires again."""
    model = await setup(dut)
    _, s = await drive(dut, model, 255)
    assert s == 1, "max input from rest should spike immediately"
    for n in range(4):
        v, s = await drive(dut, model, 255)
        assert (v, s) == (0, 0), f"refractory cycle {n + 1}: input should be ignored"
    _, s = await drive(dut, model, 255)
    assert s == 1, "should fire again once refractory ends"


@cocotb.test()
async def test_reset_mid_integration(dut):
    """Reset while V is partly charged must clear V, spike, and refractory state."""
    model = await setup(dut)
    for _ in range(3):
        await drive(dut, model, 60)
    await pulse_reset(dut, model)
    v, _ = await drive(dut, model, 10)
    assert v == 10, "after reset, integration should start again from 0"


@cocotb.test()
async def test_random_vs_model(dut):
    """5,000 cycles of random input with occasional resets, checked every cycle."""
    model = await setup(dut)
    rng = random.Random(12345)  # fixed seed so any failure is reproducible
    spikes = 0
    for _ in range(5000):
        if rng.random() < 0.005:
            await pulse_reset(dut, model)
            continue
        # bias toward small inputs so the neuron spends time integrating, not just firing
        i = rng.choice([rng.randint(0, 20), rng.randint(0, 80), rng.randint(0, 255)])
        _, s = await drive(dut, model, i)
        spikes += s
    dut._log.info(f"random run: {spikes} spikes, all cycles matched the model")
