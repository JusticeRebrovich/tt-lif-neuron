"""Fault-detection check for the built-in self-test.
run.py builds the design a second time with THRESHOLD = 201 instead of 200,
standing in for a manufacturing defect. The self-test must finish and report FAIL.
This module only makes sense against that faulty build, so it is not in the Makefile."""

import cocotb

from chip_model import BIST_GOLDEN, ChipModel
from test_bist import chip_setup, run_bist

FAULTY_THRESHOLD = 201


@cocotb.test()
async def test_bist_catches_wrong_threshold(dut):
    model = ChipModel()
    for n in model.ring.neurons:
        n.threshold = FAULTY_THRESHOLD
    await chip_setup(dut, model)
    uo = await run_bist(dut, model)          # every pin still matches the (faulty) model
    assert uo & 0b11 == 0b01, f"expected DONE without PASS, got status {uo:#04x}"
    assert model.misr != BIST_GOLDEN
    dut._log.info(f"fault caught: signature {model.misr:#06x} instead of {BIST_GOLDEN:#06x}")
