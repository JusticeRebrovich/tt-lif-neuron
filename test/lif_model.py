"""Golden reference model: the same fixed-point LIF math as the RTL, in Python.
The testbench steps this alongside the DUT and compares every cycle."""


class LifModel:
    def __init__(self, threshold=200, leak_shift=4, refrac=4):
        self.threshold = threshold
        self.leak_shift = leak_shift
        self.refrac = refrac
        self.reset()

    def reset(self):
        self.v = 0
        self.spike = 0
        self.refr_cnt = 0

    def step(self, i):
        """Advance one clock with input current i (0..255 from the pins; the ring
        can sum up to 510, and later stages may make it negative)."""
        if self.refr_cnt != 0:
            self.v, self.spike = 0, 0
            self.refr_cnt -= 1
            return
        leak = self.v >> self.leak_shift
        if leak == 0 and self.v > 0:
            leak = 1                          # minimum leak so V decays to 0
        leaked = self.v - leak
        v_sat = max(0, min(leaked + i, 255))  # clamp to 8 bits: floor at 0, saturate at 255
        if v_sat >= self.threshold:
            self.v, self.spike = 0, 1
            self.refr_cnt = self.refrac
        else:
            self.v, self.spike = v_sat, 0
