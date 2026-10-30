"""Build the RTL with Icarus Verilog and run all cocotb tests."""
from pathlib import Path

from cocotb_tools.runner import get_runner

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src" / "tt_um_justice_lif.v"

runner = get_runner("icarus")
runner.build(sources=[SRC], hdl_toplevel="tt_um_justice_lif", build_dir=HERE / "sim_build", always=True)
runner.test(hdl_toplevel="tt_um_justice_lif", test_module="test_lif", test_dir=HERE, build_dir=HERE / "sim_build")
