"""cocotb tests for the built-in self-test (BIST) and the uo_out pages.
Every cycle, every output pin is compared with the pin-accurate ChipModel.
These tests use pins only, so they run unchanged on the gate-level netlist."""

import random

import cocotb
from cocotb.triggers import FallingEdge

from chip_model import BIST_GOLDEN, BIST_LEN, ChipModel, compute_golden
from test_lif import sample_after_edge, setup

UIO_OE = 0b1110_0000
BIST = 0b01000       # uio_in[3]: run the self-test, uo_out shows {signature[5:0], PASS, DONE}
SIG_HI = 0b11000     # uio_in[4:3] = 3: uo_out shows signature[15:8]


def check(dut, model, uio, note=""):
    uo, exp = int(dut.uo_out.value), model.uo_out(uio)
    assert uo == exp, f"uo_out mismatch: DUT {uo:#04x}, model {exp:#04x} (uio_in {uio:#07b}) {note}"
    uio_out = int(dut.uio_out.value)
    assert uio_out == model.uio_out(), f"uio_out mismatch: DUT {uio_out:#04x}, model {model.uio_out():#04x} {note}"
    assert int(dut.uio_oe.value) == UIO_OE, f"uio_oe must be {UIO_OE:#010b} {note}"
    return uo


async def chip_setup(dut, model=None):
    await setup(dut)          # clock, reset, uio_in = 0
    return model or ChipModel()


async def step(dut, model, ui, uio, ena=1):
    """One clock with ui_in = ui and uio_in = uio. Returns uo_out."""
    await FallingEdge(dut.clk)
    dut.rst_n.value = 1
    dut.ena.value = ena
    dut.ui_in.value = ui
    dut.uio_in.value = uio
    model.step(ui, uio)
    await sample_after_edge(dut)
    return check(dut, model, uio)


async def reset_cycle(dut, model, uio):
    await FallingEdge(dut.clk)
    dut.rst_n.value = 0
    dut.uio_in.value = uio
    model.reset()
    await sample_after_edge(dut)
    check(dut, model, uio, "(in reset)")


async def run_bist(dut, model, noisy=None):
    """Hold the BIST page until DONE. Returns the final status byte.
    With noisy set, every pin the self-test should ignore is driven randomly."""
    for n in range(BIST_LEN + 1):
        ui, uio, ena = 0, BIST, 1
        if noisy:
            ui, ena = noisy.randrange(256), noisy.randrange(2)
            uio = BIST | noisy.randrange(8) | (noisy.randrange(8) << 5)
        uo = await step(dut, model, ui, uio, ena)
        if n < BIST_LEN:
            assert uo & 1 == 0, f"DONE set too early, after {n + 1} clocks"
    assert uo & 1 == 1, "DONE not set after BIST_LEN + 1 clocks"
    return uo


@cocotb.test()
async def test_golden_constant_matches_model(dut):
    """The signature constant must be what the golden model actually produces."""
    assert compute_golden() == BIST_GOLDEN, f"model gives {compute_golden():#06x}, constant is {BIST_GOLDEN:#06x}"


@cocotb.test()
async def test_bist_passes(dut):
    """A healthy design: DONE after exactly BIST_LEN + 1 clocks, PASS set, signature as predicted."""
    model = await chip_setup(dut)
    uo = await run_bist(dut, model)
    assert uo & 0b11 == 0b11, f"expected DONE and PASS, got status {uo:#04x}"
    assert uo >> 2 == BIST_GOLDEN & 0x3F
    for _ in range(20):                                   # the result must hold
        assert await step(dut, model, 0, BIST) == uo
    hi = await step(dut, model, 0, SIG_HI)                # other page, same run
    assert hi == BIST_GOLDEN >> 8
    dut._log.info(f"BIST passed: signature {model.misr:#06x}, {BIST_LEN} clocks of stimulus")


@cocotb.test()
async def test_bist_ignores_other_pins(dut):
    """ui_in, the weight and mode pins, ena and the unused pins must not affect the self-test."""
    model = await chip_setup(dut)
    uo = await run_bist(dut, model, noisy=random.Random(7))
    assert uo & 0b11 == 0b11, f"self-test was disturbed by other pins, status {uo:#04x}"


@cocotb.test()
async def test_bist_restarts_cleanly(dut):
    """Leaving the self-test early, or a reset in the middle, must not spoil the next run."""
    model = await chip_setup(dut)
    for _ in range(300):
        await step(dut, model, 0, BIST)
    uo = await step(dut, model, 255, 0b00011)             # leaving the self-test resets the neurons,
    assert uo == 0 and int(dut.uio_out.value) == 0, "ring should be at rest after leaving the self-test"
    for _ in range(60):                                   # and the ring then works as normal
        await step(dut, model, 40, 0b00011)
    for _ in range(500):
        await step(dut, model, 0, BIST)
    await reset_cycle(dut, model, BIST)                   # reset in the middle of a run
    uo = await run_bist(dut, model)
    assert uo & 0b11 == 0b11, f"expected DONE and PASS after a restart, got {uo:#04x}"


@cocotb.test()
async def test_reserved_page_reads_zero(dut):
    """Page 2 (uio_in[4:3] = 2) is reserved: uo_out is 0 and the ring keeps running."""
    model = await chip_setup(dut)
    for _ in range(60):
        assert await step(dut, model, 60, 0b10011) == 0


@cocotb.test()
async def test_random_chip_vs_model(dut):
    """8,000 clocks of random pins, page changes, self-test runs of random length and resets."""
    rng = random.Random(1116)
    model = await chip_setup(dut)
    uio, bist_left, completed = 0, 0, 0
    for _ in range(8000):
        r = rng.random()
        if r < 0.0008:
            await reset_cycle(dut, model, uio)
            continue
        if bist_left:
            bist_left -= 1
            uio = (uio & ~0b11000) | rng.choice([BIST, BIST, BIST, SIG_HI])
            if not bist_left:
                uio &= ~0b11000
        elif r < 0.012:
            bist_left = rng.choice([3, 150, BIST_LEN + 30])
        elif r < 0.06:
            uio = rng.randrange(8) | (rng.choice([0, 0, 0, 2]) << 3) | (rng.randrange(8) << 5)
        ui = rng.choice([0, 0, rng.randrange(256), rng.randrange(64)])
        await step(dut, model, ui, uio, ena=rng.randrange(2))
        if model.done and model.passed and bist_left == 1:
            completed += 1
    dut._log.info(f"random chip run matched the model on every clock; {completed} self-test runs completed")
    assert completed >= 1, "the random run should complete at least one self-test"
