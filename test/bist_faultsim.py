"""Fault simulator used to tune the self-test stimulus. Run it with: python bist_faultsim.py

It models the self-test at the same level as the RTL, injects one fault at a
time, and reports how many faults change the signature (and so would make the
chip report FAIL). It compares the first stimulus, which drove only neuron 0,
with the final one, which drives and observes every neuron.

It is a design aid, not a proof: the fault list is a hand-picked set of
RTL-level faults, and an independent review used its own, larger list.
The healthy signature it prints for the final stimulus must equal
chip_model.BIST_GOLDEN, which ties this file to the golden model."""

from chip_model import (BIST_GOLDEN, BIST_LEN, LFSR_SEED, bist_stimulus, lfsr_next, misr_data, misr_next)

WEIGHTS = [0, 64, 128, 255]


def old_stimulus(cnt, lfsr):
    """The first self-test: only neuron 0 is driven."""
    i0 = lfsr if (cnt >> 6) & 1 else lfsr & 0x1F
    return [i0, 0, 0, 0], (cnt >> 8) & 3, (cnt >> 7) & 1


def old_misr_data(v, spikes):
    """The first self-test observed the spikes and V0[7:4] only."""
    return (v[0] & 0xF0) | sum(s << k for k, s in enumerate(spikes))


class Neuron:
    def __init__(self):
        self.v = self.spike = self.refr = 0


def step_neuron(n, cur, refrac, f):
    """One clock of a LIF neuron with the faults in dict f applied."""
    if n.refr != 0 and not f.get("refr_none"):
        n.v, n.spike = 0, 0
        n.refr -= 1
    else:
        leak = n.v >> f.get("shift", 4)
        if leak == 0 and n.v > 0 and not f.get("no_min1"):
            leak = 1
        s = n.v - leak + cur
        if f.get("clamp_removed"):
            vs = s & 0xFF
        elif f.get("clamp_ignores_sum8"):
            vs = 255 if s >= 512 else (0 if s < 0 else s & 0xFF)
        else:
            vs = max(0, min(s, 255))
        if vs >= f.get("thr", 200):
            n.v = vs if f.get("fire_keeps_v") else 0
            n.spike = 1
            n.refr = 0 if f.get("refr_none") else f.get("refr_const", refrac + f.get("refr_delta", 0))
        else:
            n.v, n.spike = vs, 0
    n.v = (n.v & f.get("v_and", 0xFF)) | f.get("v_or", 0)
    n.spike = f.get("spike_const", n.spike)


def run(stimulus, observe, fault=None):
    """Signature after one self-test run. fault = (neuron index or 'top', dict of faults)."""
    where, f = fault or (None, {})
    neurons = [Neuron() for _ in range(4)]
    lfsr, misr = LFSR_SEED, 0
    weights = list(WEIGHTS)
    if where == "top" and "weight" in f:
        weights[f["weight"][0]] = f["weight"][1]
    for cnt in range(1, BIST_LEN + 1):
        v, s = [n.v for n in neurons], [n.spike for n in neurons]
        data = observe(v, s)
        cur, w_sel, mode = stimulus(cnt, lfsr)
        for k, n in enumerate(neurons):
            kick = weights[w_sel] if s[(k - 1) % 4] else 0
            top = f if where == "top" else {}
            if top.get("kick_broken") == k:
                kick = 0
            if top.get("kick_stuck") == k:
                kick = weights[w_sel]
            if k == 0 and top.get("adder_or"):
                total = cur[0] | kick
            elif top.get("drive_missing") == k or (k == 0 and top.get("adder_drops_ext")):
                total = kick
            else:
                total = cur[k] + kick
            step_neuron(n, total, 3 if mode else 4, f if where == k else {})
        misr = misr_next(misr, data)
        lfsr = lfsr_next(lfsr)
    return misr


def fault_list():
    faults = []
    for k in range(4):
        for t in (199, 201, 208, 192):
            faults.append((f"n{k}.thr_{t}", (k, {"thr": t})))
        for name, f in (("leak_no_min1", {"no_min1": 1}), ("leak_shift3", {"shift": 3}),
                        ("leak_shift5", {"shift": 5}), ("refr_none", {"refr_none": 1}),
                        ("refr_minus1", {"refr_delta": -1}), ("refr_plus1", {"refr_delta": 1}),
                        ("refr_const3", {"refr_const": 3}), ("refr_const4", {"refr_const": 4}),
                        ("clamp_removed", {"clamp_removed": 1}), ("clamp_ignores_sum8", {"clamp_ignores_sum8": 1}),
                        ("fire_keeps_v", {"fire_keeps_v": 1}), ("spike_stuck0", {"spike_const": 0}),
                        ("spike_stuck1", {"spike_const": 1})):
            faults.append((f"n{k}.{name}", (k, f)))
        for b in range(8):
            faults.append((f"n{k}.v{b}_stuck0", (k, {"v_and": 0xFF ^ (1 << b)})))
            faults.append((f"n{k}.v{b}_stuck1", (k, {"v_or": 1 << b})))
        for name in ("kick_broken", "kick_stuck", "drive_missing"):
            faults.append((f"top.{name}{k}", ("top", {name: k})))
    for idx, val in ((1, 0), (1, 63), (1, 65), (1, 128), (2, 127), (2, 129), (2, 64), (3, 128)):
        faults.append((f"top.w{WEIGHTS[idx]}_becomes_{val}", ("top", {"weight": (idx, val)})))
    faults += [("top.adder_or", ("top", {"adder_or": 1})), ("top.adder_drops_ext", ("top", {"adder_drops_ext": 1}))]
    return faults


if __name__ == "__main__":
    final = run(bist_stimulus, misr_data)
    assert final == BIST_GOLDEN, f"simulator gives {final:#06x}, golden model says {BIST_GOLDEN:#06x}"
    for label, stimulus, observe in (("first stimulus (neuron 0 only)", old_stimulus, old_misr_data),
                                     ("final stimulus (all neurons)", bist_stimulus, misr_data)):
        good = run(stimulus, observe)
        faults = fault_list()
        if stimulus is old_stimulus:      # the first stimulus had no direct drive on neurons 1..3
            faults = [x for x in faults if "drive_missing" not in x[0] or x[0].endswith("0")]
        missed = [name for name, fault in faults if run(stimulus, observe, fault) == good]
        print(f"{label}: signature {good:#06x}, detected {len(faults) - len(missed)}/{len(faults)}")
        print("   missed:", ", ".join(missed) if missed else "none")
