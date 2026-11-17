"""Build the RTL with Icarus Verilog and run all cocotb tests."""
from pathlib import Path

from cocotb_tools.runner import get_runner

from chip_model import BIST_GOLDEN

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src" / "tt_um_justice_lif.v"
TOP = "tt_um_justice_lif"

runner = get_runner("icarus")
runner.build(sources=[SRC], hdl_toplevel=TOP, build_dir=HERE / "sim_build", always=True)
runner.test(hdl_toplevel=TOP, test_module=["test_lif", "test_ring", "test_bist"], test_dir=HERE,
            build_dir=HERE / "sim_build")

# Builds with one deliberate change each: the self-test must report FAIL on all of them.
FAULT_BUILDS = {
    "threshold": {"THRESHOLD": 201},
    "golden_hi": {"BIST_GOLDEN": BIST_GOLDEN ^ 0x8000},
    "golden_lo": {"BIST_GOLDEN": BIST_GOLDEN ^ 0x0040},
}
for name, parameters in FAULT_BUILDS.items():
    build_dir = HERE / "sim_build_fault" / name
    fault = get_runner("icarus")
    fault.build(sources=[SRC], hdl_toplevel=TOP, build_dir=build_dir, always=True, parameters=parameters)
    fault.test(hdl_toplevel=TOP, test_module="test_bist_fault", test_dir=HERE, build_dir=build_dir,
               results_xml=f"results_fault_{name}.xml", extra_env={"LIF_FAULT": name})
