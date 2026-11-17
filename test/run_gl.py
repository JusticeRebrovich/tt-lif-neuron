"""Gate-level sim: run the same cocotb tests on a Yosys netlist instead of the RTL.
The netlist is not kept in the repo. Synthesize one to synth/tt_um_justice_lif_netlist.v first;
the GitHub gds workflow runs its own gate-level test and does not use this script."""
from pathlib import Path
from cocotb_tools.runner import get_runner

HERE = Path(__file__).resolve().parent
NETLIST = HERE.parent / "synth" / "tt_um_justice_lif_netlist.v"
runner = get_runner("icarus")
runner.build(sources=[NETLIST], hdl_toplevel="tt_um_justice_lif", build_dir=HERE / "sim_build_gl",
             timescale=("1ns", "1ps"), always=True)
runner.test(hdl_toplevel="tt_um_justice_lif", test_module=["test_lif", "test_ring"], test_dir=HERE, build_dir=HERE / "sim_build_gl")
