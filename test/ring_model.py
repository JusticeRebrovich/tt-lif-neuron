"""Golden reference model of the four-neuron ring, built from LifModel.
Neuron 0 gets the external input; each spike kicks the next neuron with
weight W one clock later (spikes are registered in the RTL)."""

from lif_model import LifModel

WEIGHTS = (0, 64, 128, 255)   # selected by uio_in[1:0]; 0 turns the ring off
REFRAC = (4, 3)               # selected by uio_in[2]: 0 = paced by the input, 1 = self-sustaining
N = 4


class RingModel:
    def __init__(self):
        self.neurons = [LifModel() for _ in range(N)]

    def reset(self):
        for m in self.neurons:
            m.reset()

    @property
    def spikes(self):
        return [m.spike for m in self.neurons]

    @property
    def v(self):
        return [m.v for m in self.neurons]

    def step(self, i, w_sel, mode=0, direct=(0, 0, 0)):
        """Advance one clock with external input i (0..255), weight select w_sel (0..3)
        and refractory mode (0 or 1). The refractory length is latched when a neuron fires.
        direct is extra current into neurons 1..3; only the self-test uses it."""
        w = WEIGHTS[w_sel]
        prev = self.spikes                      # spikes from the previous clock
        for k, m in enumerate(self.neurons):
            current = w * prev[(k - 1) % N]     # kick from the neuron before it
            current += i if k == 0 else direct[k - 1]
            m.refrac = REFRAC[mode]
            m.step(current)
