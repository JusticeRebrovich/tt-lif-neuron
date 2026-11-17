<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

Four digital leaky integrate-and-fire (LIF) neurons are wired in a ring. Neuron 0 is driven by the input pins, and
every spike "kicks" the next neuron, so spikes travel 0 → 1 → 2 → 3 and back to 0.

Each neuron keeps an 8-bit membrane voltage `V` and updates it on every clock:

```
V_next = V - leak + I        leak = V >> 4 (V/16), but at least 1 whenever V > 0
```

- **Integrate:** the input current `I` is added to `V` each cycle. For neuron 0 it is `ui[7:0]` plus the kick from
  neuron 3. For the others it is the kick from the neuron before it.
- **Leak:** V/16 drains away every cycle. The leak is a right shift, so no multiplier is needed. It is forced to at
  least 1 while `V > 0`, so the voltage always decays back to 0 when input stops.
- **Clamp:** the result is clamped to 0..255 instead of wrapping.
- **Fire:** when the new voltage reaches the threshold (200), the neuron emits a one-cycle spike and resets `V` to 0.
- **Refractory period:** after a spike the neuron ignores its input for 4 or 3 clock cycles (`MODE` pin).

The kick weight is chosen with `uio[1:0]`:

| `uio[1:0]` | Weight | Behaviour |
| --- | --- | --- |
| 0 | 0 | Ring off. Neuron 0 works as a single LIF neuron |
| 1 | 64 | A weak nudge that leaks away between spikes |
| 2 | 128 | A neuron needs several kicks to fire, so it fires less often than the one driving it |
| 3 | 255 | One kick is enough. A spike hops to the next neuron on each clock |

`MODE` (`uio[2]`) selects the refractory period. With `MODE = 0` (4 cycles) the kick from neuron 3 reaches neuron 0
while it is still refractory, so each wave makes one pass and the input sets the rhythm. With `MODE = 1` (3 cycles)
and weight 255, a single spike keeps circulating with a period of 4 clocks and no further input.

`rst_n` is an active-low reset that clears every neuron. The design is checked in simulation against a Python golden
model, cycle by cycle, using cocotb.

## How to test

1. Hold `rst_n` low for a few clock cycles, then release it. Set `ui[7:0]` and `uio[2:0]` to 0.
2. **Single neuron:** apply a constant input on `ui[7:0]`, for example 30. `V` of neuron 0 (shown on `uo[7:1]`) climbs
   until it crosses the threshold, then `uo[0]` pulses high for one cycle. Input 30 gives one spike every 13 clocks.
3. **Travelling wave:** set `uio[1:0] = 3`. Every spike on `uo[0]` is followed by spikes on `uio[5]`, `uio[6]` and
   `uio[7]` on the next three clocks.
4. **Rate division:** set `uio[1:0] = 2`. Neuron 1 (`uio[5]`) fires less often than neuron 0.
5. **Self-sustaining oscillator:** set `uio[2:0] = 7`, apply `ui[7:0] = 255` for one clock, then 0. A spike keeps
   circulating: each of the four spike pins pulses once every 4 clocks. Clear `uio[2]` and it stops.

Slow the clock down to see the pattern on LEDs.

## External hardware

None. LEDs or a logic analyzer on `uo[0]` and `uio[7:5]` show the spike pattern.
