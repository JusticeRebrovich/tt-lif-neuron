"""Golden reference model of the four-neuron ring, built from LifModel.
Neuron 0 gets the external input; each spike kicks the next neuron with
weight W one clock later (spikes are registered in the RTL)."""

from lif_model import LifModel

WEIGHTS = (0, 64, 128, 255)   # selected by uio_in[1:0]; 0 turns the ring off
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

    def step(self, i, w_sel):
        """Advance one clock with external input i (0..255) and weight select w_sel (0..3)."""
        w = WEIGHTS[w_sel]
        prev = self.spikes                      # spikes from the previous clock
        for k, m in enumerate(self.neurons):
            current = w * prev[(k - 1) % N]     # kick from the neuron before it
            if k == 0:
                current += i
            m.step(current)
