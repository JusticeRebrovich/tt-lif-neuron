<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This is a digital leaky integrate-and-fire (LIF) neuron, a simple model of a biological neuron. It keeps an 8-bit
membrane voltage `V` and updates it on every clock:

```
V_next = V - leak + I        leak = V >> 4 (V/16), but at least 1 whenever V > 0
```

- **Integrate:** the 8-bit input current `I` on `ui[7:0]` is added to `V` each cycle.
- **Leak:** a fraction of `V` (V/16) drains away every cycle. The leak is a right shift, so no multiplier is needed.
  It is forced to at least 1 while `V > 0`, so the voltage always decays all the way back to 0 when input stops.
- **Saturate:** the add saturates at 255 instead of wrapping around.
- **Fire:** when the new voltage reaches the threshold (200), the neuron emits a one-cycle spike on `uo[0]`
  and resets `V` to 0.
- **Refractory period:** after a spike the neuron ignores its input for 4 clock cycles, then starts integrating again.

The threshold, leak shift and refractory length are Verilog parameters (`THRESHOLD`, `LEAK_SHIFT`, `REFRAC`).
`rst_n` is an active-low reset that clears `V`, the spike output and the refractory counter.

The design is checked in simulation against a Python golden model, cycle by cycle, using cocotb.

## How to test

1. Hold `rst_n` low for a few clock cycles, then release it. Set `ui[7:0]` to 0.
2. Apply a constant input current on `ui[7:0]`, for example 30. `V` (shown on `uo[7:1]`) climbs until it crosses
   the threshold, then `uo[0]` pulses high for one cycle and `V` returns to 0.
3. With a constant input large enough to overcome the leak, the neuron spikes periodically. A larger input gives a
   shorter interval between spikes.
4. Set `ui[7:0]` back to 0. `V` leaks away to 0 and no more spikes occur.
5. Try `ui[7:0]` = 255. The neuron spikes right away, stays silent for the 4-cycle refractory period, then spikes again.

Output pins: `uo[0]` is the spike, and `uo[7:1]` are the top seven bits of the membrane voltage (`V[7:1]`).
The bidirectional pins `uio[7:0]` are unused.

## External hardware

None. A logic analyzer or LEDs on `uo[7:0]` make the spikes and the voltage easy to see.
