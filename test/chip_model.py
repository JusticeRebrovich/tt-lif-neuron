"""Pin-accurate golden model of the whole chip: the four-neuron ring plus the
built-in self-test (BIST). Given the input pins each clock, it predicts every output pin.

BIST (uio_in[3] = 1):
  - the first clock resets the neurons
  - for BIST_LEN clocks an 8-bit LFSR drives neuron 0, while a counter steps
    through every weight and both refractory modes
  - a 16-bit signature register (MISR) folds in the four spikes and V0[7:4] each clock
  - afterwards DONE is set, and PASS is set if the signature equals BIST_GOLDEN
"""

from ring_model import RingModel

BIST_LEN = 1024
LFSR_SEED = 0x01
MISR_POLY = 0x1021          # x^16 + x^12 + x^5 + 1
BIST_GOLDEN = 0x55C4        # what compute_golden() returns; the RTL holds the same constant


def lfsr_next(lfsr):
    """8-bit Fibonacci LFSR, taps x^8 + x^6 + x^5 + x^4 + 1 (period 255)."""
    fb = ((lfsr >> 7) ^ (lfsr >> 5) ^ (lfsr >> 4) ^ (lfsr >> 3)) & 1
    return ((lfsr << 1) & 0xFF) | fb


def misr_next(misr, data):
    """Shift left, apply the polynomial if the top bit falls out, fold in 8 bits of data."""
    out = (misr << 1) & 0xFFFF
    if misr & 0x8000:
        out ^= MISR_POLY
    return out ^ (data & 0xFF)


def bist_stimulus(cnt, lfsr):
    """What the BIST controller feeds the ring: (input current, weight select, refractory mode)."""
    i = lfsr if (cnt >> 6) & 1 else lfsr & 0x1F     # alternate small and large currents
    return i, (cnt >> 8) & 3, (cnt >> 7) & 1


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
            data = (self.ring.v[0] & 0xF0) | sum(s << k for k, s in enumerate(self.ring.spikes))
            self.ring.step(*bist_stimulus(self.cnt, self.lfsr))
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


def compute_golden():
    """Run the BIST on the model and return the signature a healthy chip produces."""
    m = ChipModel(golden=0)
    for _ in range(BIST_LEN + 2):
        m.step(0, 0b01000)
    assert m.done
    return m.misr


if __name__ == "__main__":
    period, x = 0, LFSR_SEED
    while True:
        x, period = lfsr_next(x), period + 1
        if x == LFSR_SEED:
            break
    m = ChipModel(golden=0)
    spikes = [0, 0, 0, 0]
    for _ in range(BIST_LEN + 2):
        m.step(0, 0b01000)
        spikes = [a + b for a, b in zip(spikes, m.ring.spikes)]
    print(f"LFSR period {period}, spikes per neuron during BIST {spikes}, golden signature {m.misr:#06x}")
    for thr in (199, 201):
        f = ChipModel(golden=0)
        for n in f.ring.neurons:
            n.threshold = thr
        for _ in range(BIST_LEN + 2):
            f.step(0, 0b01000)
        print(f"  faulty threshold {thr}: signature {f.misr:#06x}")
