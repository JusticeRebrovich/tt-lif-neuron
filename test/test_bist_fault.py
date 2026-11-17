"""Negative checks for the built-in self-test: it must be able to say FAIL.
run.py builds the design again with one deliberate change per build and sets
LIF_FAULT to say which. In every case the self-test must finish with DONE but not PASS.

  threshold   THRESHOLD = 201 instead of 200, standing in for a manufacturing defect
  golden_hi   healthy logic, but the expected signature differs in bit 15
  golden_lo   healthy logic, but the expected signature differs in bit 6

The two golden builds check that PASS compares all 16 signature bits, including
bits 7:6, which no uo_out page shows. This module only makes sense against
those builds, so it is not in the Makefile."""

import os

import cocotb

from chip_model import BIST_GOLDEN, ChipModel
from test_bist import chip_setup, run_bist

FAULT = os.environ.get("LIF_FAULT", "threshold")
FAULTY_THRESHOLD = 201
GOLDEN_FLIP = {"golden_hi": 0x8000, "golden_lo": 0x0040}


@cocotb.test()
async def test_bist_reports_fail(dut):
    if FAULT == "threshold":
        model = ChipModel()
        for n in model.ring.neurons:
            n.threshold = FAULTY_THRESHOLD
    else:
        model = ChipModel(golden=BIST_GOLDEN ^ GOLDEN_FLIP[FAULT])
    await chip_setup(dut, model)
    uo = await run_bist(dut, model)          # every pin still matches the model of this build
    assert uo & 0b11 == 0b01, f"{FAULT}: expected DONE without PASS, got status {uo:#04x}"
    assert model.misr != model.golden
    dut._log.info(f"{FAULT}: FAIL reported, signature {model.misr:#06x} against expected {model.golden:#06x}")
