"""cocotb tests for the four-neuron ring.
Every cycle, all four spikes (and every membrane voltage the simulator can
see) are compared with the RingModel golden model."""

import random

import cocotb
from cocotb.triggers import FallingEdge

from ring_model import N, RingModel
from test_lif import read_v, sample_after_edge, setup


def read_spikes(dut):
    """Spikes come off the pins: uo_out[0] is neuron 0, uio_out[7:5] are neurons 3, 2, 1."""
    uio = int(dut.uio_out.value)
    return [int(dut.uo_out.value) & 1, (uio >> 5) & 1, (uio >> 6) & 1, (uio >> 7) & 1]


def read_internal_v(dut, k):
    """V of neuron k if the simulator can see it (RTL only), else None."""
    for scope in (dut, getattr(dut, "user_project", None)):
        try:
            return int(getattr(scope, f"v{k}").value)
        except AttributeError:
            pass
    return None


def check(dut, model, note=""):
    spikes = read_spikes(dut)
    assert spikes == model.spikes, f"spike mismatch: DUT {spikes}, model {model.spikes} {note}"
    v0, mask = read_v(dut)
    assert v0 & mask == model.v[0] & mask, f"V0 mismatch: DUT {v0}, model {model.v[0]} {note}"
    for k in range(1, N):
        vk = read_internal_v(dut, k)
        if vk is not None:
            assert vk == model.v[k], f"V{k} mismatch: DUT {vk}, model {model.v[k]} {note}"
    return spikes


async def ring_setup(dut):
    await setup(dut)          # clock, reset, uio_in = 0
    return RingModel()


async def step(dut, model, i, w_sel, extra_uio=0):
    """Apply input i and weight select w_sel for one cycle, step the model, and compare."""
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1
    dut.ui_in.value = i
    dut.uio_in.value = w_sel | extra_uio
    model.step(i, w_sel)
    await sample_after_edge(dut)
    return check(dut, model, f"(input {i}, w_sel {w_sel})")


async def reset_cycle(dut, model):
    await FallingEdge(dut.clk)
    dut.rst_n.value = 0
    model.reset()
    await sample_after_edge(dut)
    check(dut, model, "(in reset)")


@cocotb.test()
async def test_travelling_wave(dut):
    """Weight 255: every spike of neuron 0 is followed by 1, 2, 3 on the next three clocks."""
    model = await ring_setup(dut)
    history = [await step(dut, model, 30, 3) for _ in range(120)]
    starts = [t for t, s in enumerate(history[:-3]) if s[0]]
    assert len(starts) >= 3, "expected several spikes from neuron 0"
    for t in starts:
        for k in range(1, N):
            assert history[t + k][k] == 1, f"neuron {k} did not fire {k} clocks after neuron 0 (t={t})"
    counts = [sum(s[k] for s in history) for k in range(N)]
    dut._log.info(f"weight 255, input 30 -> spikes per neuron {counts}")


@cocotb.test()
async def test_rate_division(dut):
    """Weight 128: one kick is not enough, so neuron 1 fires less often than neuron 0."""
    model = await ring_setup(dut)
    history = [await step(dut, model, 30, 2) for _ in range(400)]
    counts = [sum(s[k] for s in history) for k in range(N)]
    dut._log.info(f"weight 128, input 30 -> spikes per neuron {counts}")
    assert 0 < counts[1] < counts[0], f"expected neuron 1 to divide neuron 0's rate, got {counts}"


@cocotb.test()
async def test_ring_off(dut):
    """Weight select 0: only neuron 0 fires, however hard it is driven."""
    model = await ring_setup(dut)
    history = [await step(dut, model, 60, 0) for _ in range(100)]
    counts = [sum(s[k] for s in history) for k in range(N)]
    assert counts[0] > 0 and counts[1:] == [0, 0, 0], f"ring should be off, got {counts}"


@cocotb.test()
async def test_quiet_without_input(dut):
    """No input: the ring must not start firing by itself, at any weight."""
    model = await ring_setup(dut)
    for w_sel in range(4):
        for _ in range(40):
            spikes = await step(dut, model, 0, w_sel)
            assert spikes == [0, 0, 0, 0], f"spontaneous spike at w_sel {w_sel}"


@cocotb.test()
async def test_random_ring_vs_model(dut):
    """5,000 cycles of random input, random weight changes and occasional resets."""
    rng = random.Random(2026)
    model = await ring_setup(dut)
    w_sel, total = 3, [0] * N
    for _ in range(5000):
        r = rng.random()
        if r < 0.01:
            await reset_cycle(dut, model)
            continue
        if r < 0.05:
            w_sel = rng.randrange(4)
        i = rng.choice([0, 0, rng.randrange(256), rng.randrange(64)])
        extra = rng.randrange(8) << 2          # unused uio_in[4:2] must be ignored
        spikes = await step(dut, model, i, w_sel, extra)
        total = [a + b for a, b in zip(total, spikes)]
    dut._log.info(f"random ring run: spikes per neuron {total}, all cycles matched the model")
    assert all(t > 0 for t in total), f"every neuron should have fired at least once, got {total}"
