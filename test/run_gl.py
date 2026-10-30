"""Gate-level sim: run the same cocotb tests on the Yosys netlist instead of the RTL."""
from pathlib import Path
from cocotb_tools.runner import get_runner

HERE = Path(__file__).resolve().parent
NETLIST = HERE.parent / "synth" / "tt_um_justice_lif_netlist.v"
runner = get_runner("icarus")
runner.build(sources=[NETLIST], hdl_toplevel="tt_um_justice_lif", build_dir=HERE / "sim_build_gl",
             timescale=("1ns", "1ps"), always=True)
runner.test(hdl_toplevel="tt_um_justice_lif", test_module="test_lif", test_dir=HERE, build_dir=HERE / "sim_build_gl")
