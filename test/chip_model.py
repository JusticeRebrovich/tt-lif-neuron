"""Pin-accurate golden model of the whole chip: the four-neuron ring plus the
built-in self-test (BIST). Given the input pins each clock, it predicts every output pin.

BIST (uio_in[3] = 1):
  - the first clock resets the neurons
  - for BIST_LEN clocks an 8-bit LFSR drives all four neurons directly, each
    with its own bit pattern and amplitude, while a counter steps through
    every weight and both refractory modes
  - a 16-bit signature register (MISR) folds in all four voltages and spikes each clock
  - afterwards DONE is set, and PASS is set if the signature equals BIST_GOLDEN

Driving and observing every neuron is what gives the self-test its fault
coverage: an earlier version drove only neuron 0 and missed 41 of 171 faults.
"""

from ring_model import RingModel

BIST_LEN = 1024
LFSR_SEED = 0x01
MISR_POLY = 0x1021          # x^16 + x^12 + x^5 + 1
BIST_GOLDEN = 0x53DF        # what compute_golden() returns; the RTL holds the same constant


def lfsr_next(lfsr):
    """8-bit Fibonacci LFSR, taps x^8 + x^6 + x^5 + x^4 + 1 (period 255)."""
    fb = ((lfsr >> 7) ^ (lfsr >> 5) ^ (lfsr >> 4) ^ (lfsr >> 3)) & 1
    return ((lfsr << 1) & 0xFF) | fb


def misr_next(misr, data):
    """Shift left, apply the polynomial if the top bit falls out, fold in 16 bits of data."""
    out = (misr << 1) & 0xFFFF
    if misr & 0x8000:
        out ^= MISR_POLY
    return out ^ (data & 0xFFFF)


def swap_nibbles(x):
    return ((x << 4) & 0xF0) | (x >> 4)


def reverse_bits(x):
    return int(f"{x:08b}"[::-1], 2)


def bist_amp(pattern, level):
    """Amplitude levels: 0 = quiet (V decays), 1 = creep (12..19, hovers near the threshold),
    2 = small (0..31), 3 = full (0..255)."""
    return (0, 12 + (pattern & 0x07), pattern & 0x1F, pattern)[level]


def bist_stimulus(cnt, lfsr):
    """What the BIST controller feeds the ring: (four currents, weight select, refractory mode).
    Each neuron sees a different view of the LFSR, and its amplitude level changes every
    32 clocks, one step out of phase with its neighbours."""
    patterns = (lfsr, swap_nibbles(lfsr), reverse_bits(lfsr), lfsr ^ 0xFF)
    seg = (cnt >> 5) & 3
    currents = [bist_amp(patterns[k], (seg + k) & 3) for k in range(4)]
    return currents, (cnt >> 8) & 3, (cnt >> 7) & 1


def misr_data(v, spikes):
    """All four voltages and spikes, folded into 16 bits."""
    hi = v[0] ^ swap_nibbles(v[2])
    lo = v[1] ^ swap_nibbles(v[3])
    return ((hi << 8) | lo) ^ sum(s << k for k, s in enumerate(spikes))


class ChipModel:
    def __init__(self, golden=None):
        self.ring = RingModel()
        self.golden = BIST_GOLDEN if golden is None else golden
        self.reset()

    def reset(self):
        self.ring.reset()
        self.cnt, self.lfsr, self.misr = 0, LFSR_SEED, 0

    @property
    def done(self):
        return int(self.cnt == BIST_LEN + 1)

    @property
    def passed(self):
        return int(self.done and self.misr == self.golden)

    def step(self, ui, uio):
        """Advance one clock with rst_n high. ui = ui_in, uio = uio_in."""
        if not (uio >> 3) & 1:                       # normal operation
            self.ring.step(ui, uio & 3, (uio >> 2) & 1)
            self.cnt, self.lfsr, self.misr = 0, LFSR_SEED, 0
        elif self.cnt == 0:                          # first BIST clock: reset the neurons
            self.ring.reset()
            self.cnt = 1
        else:
            data = misr_data(self.ring.v, self.ring.spikes)
            currents, w_sel, mode = bist_stimulus(self.cnt, self.lfsr)
            self.ring.step(currents[0], w_sel, mode, direct=currents[1:])
            if not self.done:
                self.misr = misr_next(self.misr, data)
                self.lfsr = lfsr_next(self.lfsr)
                self.cnt += 1

    def uo_out(self, uio):
        """uo_out for the page selected by uio_in[4:3]."""
        bist, alt = (uio >> 3) & 1, (uio >> 4) & 1
        if bist and alt:
            return self.misr >> 8                                    # signature high byte
        if bist:
            return ((self.misr & 0x3F) << 2) | (self.passed << 1) | self.done
        if alt:
            return 0                                                 # reserved page
        return (self.ring.v[0] & 0xFE) | self.ring.spikes[0]         # neuron 0: V[7:1], spike

    def uio_out(self):
        s = self.ring.spikes
        return (s[3] << 7) | (s[2] << 6) | (s[1] << 5)


def run_bist(model):
    """Hold the BIST pin until DONE and return the signature."""
    for _ in range(BIST_LEN + 1):
        model.step(0, 0b01000)
    assert model.done
    return model.misr


def compute_golden():
    """Run the BIST on the model and return the signature a healthy chip produces."""
    return run_bist(ChipModel(golden=0))


if __name__ == "__main__":
    period, x = 0, LFSR_SEED
    while True:
        x, period = lfsr_next(x), period + 1
        if x == LFSR_SEED:
            break
    m = ChipModel(golden=0)
    spikes = [0, 0, 0, 0]
    for _ in range(BIST_LEN + 1):
        m.step(0, 0b01000)
        spikes = [a + b for a, b in zip(spikes, m.ring.spikes)]
    print(f"LFSR period {period}, spikes per neuron during BIST {spikes}, golden signature {m.misr:#06x}")
    for k in range(4):
        for thr in (199, 201):
            f = ChipModel(golden=0)
            f.ring.neurons[k].threshold = thr
            print(f"  neuron {k} threshold {thr}: signature {run_bist(f):#06x}"
                  f" ({'MISSED' if f.misr == m.misr else 'caught'})")
