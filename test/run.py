"""Build the RTL with Icarus Verilog and run all cocotb tests."""
from pathlib import Path

from cocotb_tools.runner import get_runner

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src" / "tt_um_justice_lif.v"
TOP = "tt_um_justice_lif"

runner = get_runner("icarus")
runner.build(sources=[SRC], hdl_toplevel=TOP, build_dir=HERE / "sim_build", always=True)
runner.test(hdl_toplevel=TOP, test_module=["test_lif", "test_ring", "test_bist"], test_dir=HERE,
            build_dir=HERE / "sim_build")

# Second build with a deliberate fault (threshold 201 instead of 200): the self-test must report FAIL.
fault = get_runner("icarus")
fault.build(sources=[SRC], hdl_toplevel=TOP, build_dir=HERE / "sim_build_fault", always=True,
            parameters={"THRESHOLD": 201})
fault.test(hdl_toplevel=TOP, test_module="test_bist_fault", test_dir=HERE, build_dir=HERE / "sim_build_fault",
           results_xml="results_fault.xml")
