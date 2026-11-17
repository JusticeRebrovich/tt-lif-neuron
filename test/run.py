"""Build the RTL with Icarus Verilog and run all cocotb tests."""
import xml.etree.ElementTree as ET
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
FAULT_BUILDS = {"threshold": {"THRESHOLD": 201}}
for bit in range(16):     # one wrong bit in the expected signature, for every bit of the comparator
    FAULT_BUILDS[f"golden_bit{bit}"] = {"BIST_GOLDEN": BIST_GOLDEN ^ (1 << bit)}
for name, parameters in FAULT_BUILDS.items():
    build_dir = HERE / "sim_build_fault" / name
    fault = get_runner("icarus")
    fault.build(sources=[SRC], hdl_toplevel=TOP, build_dir=build_dir, always=True, parameters=parameters)
    fault.test(hdl_toplevel=TOP, test_module="test_bist_fault", test_dir=HERE, build_dir=build_dir,
               results_xml=f"results_fault_{name}.xml", extra_env={"LIF_FAULT": name})


def tally(xml_file):
    """(tests, failures) in a cocotb results file."""
    cases = ET.parse(HERE / xml_file).getroot().iter("testcase")
    results = [any(child.tag in ("failure", "error") for child in case) for case in cases]
    return len(results), sum(results)


total, failed = tally("results.xml")
altered = [tally(f"results_fault_{name}.xml") for name in FAULT_BUILDS]
altered_ok = sum(1 for n, f in altered if n == 1 and f == 0)
print(f"\nSUMMARY: normal build {total - failed}/{total} tests passed; "
      f"self-test reported FAIL on {altered_ok}/{len(FAULT_BUILDS)} altered builds")
