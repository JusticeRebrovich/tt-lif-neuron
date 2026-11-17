"""Regenerate the README figures from the golden models: python images/make_figures.py
Every waveform and raster comes from the same Python models the tests compare the RTL against.
The bar charts use the numbers measured by the GitHub Actions builds and the independent review."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "test"))

from chip_model import BIST_LEN, ChipModel  # noqa: E402
from lif_model import LifModel  # noqa: E402
from ring_model import RingModel  # noqa: E402

INK, MUTED, GRID, ACCENT, WARM, BG = "#1f2933", "#6b7785", "#d9dee4", "#1f6feb", "#c2410c", "#ffffff"
SHADES = ["#1f6feb", "#3b8eea", "#6aa9f0", "#9cc4f5"]
FONT = "font-family='Segoe UI, Helvetica, Arial, sans-serif'"


def svg(width, height, body, title):
    return (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}' width='{width}' "
            f"height='{height}' role='img' aria-label='{title}' {FONT}>\n"
            f"<rect width='{width}' height='{height}' fill='{BG}'/>\n"
            f"<text x='24' y='30' font-size='16' font-weight='600' fill='{INK}'>{title}</text>\n"
            + "\n".join(body) + "\n</svg>\n")


def text(x, y, s, size=12, fill=MUTED, anchor="start", weight="400"):
    return f"<text x='{x}' y='{y}' font-size='{size}' fill='{fill}' text-anchor='{anchor}' font-weight='{weight}'>{s}</text>"


def line(x1, y1, x2, y2, stroke=GRID, width=1, dash=""):
    d = f" stroke-dasharray='{dash}'" if dash else ""
    return f"<line x1='{x1:.1f}' y1='{y1:.1f}' x2='{x2:.1f}' y2='{y2:.1f}' stroke='{stroke}' stroke-width='{width}'{d}/>"


def step_path(values, x0, y0, dx, scale, stroke, width=1.8):
    pts, y = [], None
    for i, v in enumerate(values):
        x, ny = x0 + i * dx, y0 - v * scale
        pts.append(f"M{x:.1f} {ny:.1f}" if y is None else f"V{ny:.1f}")
        pts.append(f"H{x + dx:.1f}")
        y = ny
    return f"<path d='{' '.join(pts)}' fill='none' stroke='{stroke}' stroke-width='{width}'/>"


def fig_neuron():
    m, vs, spikes = LifModel(), [], []
    for _ in range(44):
        m.step(30)
        vs.append(m.v)
        spikes.append(m.spike)
    x0, y0, dx, sc = 70, 250, 15, 0.8
    b = [text(24, 50, "Golden model of one neuron, constant input 30. The climb slows as the leak grows; "
                      "it fires every 13 clocks.")]
    for val in (0, 100, 200):
        b += [line(x0, y0 - val * sc, x0 + 44 * dx, y0 - val * sc), text(x0 - 8, y0 - val * sc + 4, val, anchor="end")]
    b.append(line(x0, y0 - 200 * sc, x0 + 44 * dx, y0 - 200 * sc, WARM, 1.2, "5 4"))
    b.append(text(x0 + 44 * dx - 4, y0 - 200 * sc - 6, "threshold 200", fill=WARM, anchor="end"))
    b.append(step_path(vs, x0, y0, dx, sc, ACCENT))
    for i, s in enumerate(spikes):
        if s:
            b.append(line(x0 + i * dx + dx / 2, 292, x0 + i * dx + dx / 2, 272, WARM, 3))
    b += [text(x0 - 8, 286, "spike", anchor="end"), text(x0 - 8, 150, "V", anchor="end", fill=INK),
          text(x0, 316, "0"), text(x0 + 40 * dx, 316, "40 clocks", anchor="middle"),
          text(x0 + 13.5 * dx, 262, "4-clock refractory", fill=MUTED, size=11)]
    return svg(760, 330, b, "One leaky integrate-and-fire neuron")


def raster_rows(rows, x0, y0, dx, label):
    b = [text(x0, y0 - 10, label, fill=INK, size=13, weight="600")]
    for k, row in enumerate(rows):
        y = y0 + k * 22 + 10
        b += [text(x0 - 8, y + 4, f"N{k}", anchor="end"), line(x0, y, x0 + len(row) * dx, y)]
        b += [line(x0 + i * dx + dx / 2, y - 8, x0 + i * dx + dx / 2, y + 8, SHADES[0], 2.4)
              for i, s in enumerate(row) if s]
    return b


def ring_run(inputs, w_sel, mode):
    r, rows = RingModel(), [[] for _ in range(4)]
    for i in inputs:
        r.step(i, w_sel, mode)
        for k, s in enumerate(r.spikes):
            rows[k].append(s)
    return rows


def fig_ring():
    n, dx, x0 = 64, 10, 60
    b = [text(24, 50, "Spike rasters from the ring golden model. Each tick is one spike; time runs left to right.")]
    b += raster_rows(ring_run([30] * n, 3, 0), x0, 90, dx, "Weight 255, input 30: a spike travels N0 → N1 → N2 → N3")
    b += raster_rows(ring_run([30] * n, 2, 0), x0, 215, dx, "Weight 128, input 30: N1 needs several kicks, so it fires less often")
    b += raster_rows(ring_run([255] + [0] * (n - 1), 3, 1), x0, 340, dx,
                     "Refractory 3, one kick then no input: the spike circulates on its own")
    b.append(text(x0 + n * dx, 450, f"{n} clocks", anchor="end"))
    return svg(760, 465, b, "Three behaviours of the four-neuron ring")


def fig_bist():
    m, n = ChipModel(), 256
    vs = [[] for _ in range(4)]
    m.step(0, 0b01000)
    for _ in range(n):
        m.step(0, 0b01000)
        for k in range(4):
            vs[k].append(m.ring.v[k])
    x0, dx, sc = 60, 2.6, 0.26
    b = [text(24, 50, "Membrane voltage of each neuron for the first 256 of 1,024 self-test clocks (weight off).")]
    for k in range(4):
        y0 = 150 + k * 95
        b += [line(x0, y0, x0 + n * dx, y0), text(x0 - 8, y0 - 26, f"N{k}", anchor="end", fill=INK),
              line(x0, y0 - 200 * sc, x0 + n * dx, y0 - 200 * sc, WARM, 1, "4 4"),
              step_path(vs[k], x0, y0, dx, sc, ACCENT, 1.2)]
    for s in range(0, n + 1, 32):
        b.append(line(x0 + s * dx, 80, x0 + s * dx, 440, GRID, 1, "2 4"))
    b += [text(x0, 462, "0"), text(x0 + n * dx, 462, "256 clocks", anchor="end"),
          text(x0 + 16 * dx, 76, "level changes every 32 clocks: quiet, creep, small, full", size=11)]
    return svg(760, 475, b, "Built-in self-test: every neuron is driven directly")


def bars(title, note, items, unit, top):
    x0, y0, h, bw, gap = 70, 300, 210, 120, 40
    b = [text(24, 50, note)]
    for val in range(0, top + 1, top // 4):
        y = y0 - val / top * h
        b += [line(x0, y, x0 + len(items) * (bw + gap), y), text(x0 - 8, y + 4, f"{val}{unit}", anchor="end")]
    for i, (label, sub, val, shown, colour) in enumerate(items):
        x, bh = x0 + gap / 2 + i * (bw + gap), val / top * h
        b += [f"<rect x='{x}' y='{y0 - bh:.1f}' width='{bw}' height='{bh:.1f}' rx='4' fill='{colour}'/>",
              text(x + bw / 2, y0 - bh - 8, shown, 14, INK, "middle", "600"),
              text(x + bw / 2, y0 + 20, label, 12, INK, "middle"), text(x + bw / 2, y0 + 37, sub, 11, MUTED, "middle")]
    return svg(760, 355, b, title)


def box(x, y, w, h, title, sub="", fill="#f3f6fa", stroke=GRID):
    out = [f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='8' fill='{fill}' stroke='{stroke}'/>",
           text(x + w / 2, y + (h / 2 if not sub else h / 2 - 5), title, 13, INK, "middle", "600")]
    if sub:
        out.append(text(x + w / 2, y + h / 2 + 13, sub, 11, MUTED, "middle"))
    return out


def arrow(x1, y1, x2, y2):
    return f"<path d='M{x1} {y1}L{x2} {y2}' stroke='{MUTED}' stroke-width='1.4' fill='none' marker-end='url(#a)'/>"


def fig_architecture():
    b = ["<defs><marker id='a' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='7' markerHeight='7' "
         f"orient='auto'><path d='M0 0L10 5L0 10z' fill='{MUTED}'/></marker></defs>",
         text(24, 50, "Normal mode: the pins drive the ring. Self-test mode: the on-chip generator does, and a signature is checked.")]
    b += box(30, 90, 130, 54, "Input pins", "current, weight, mode")
    b += box(30, 230, 130, 74, "Self-test", "counter + LFSR")
    b += box(210, 150, 110, 70, "Select", "pins or self-test")
    for k in range(4):
        b += box(370 + k * 82, 160, 66, 50, f"N{k}", "LIF", "#e8f1fe", ACCENT)
        if k:
            b.append(arrow(370 + k * 82 - 16, 185, 370 + k * 82, 185))
    b.append(f"<path d='M649 210V232H403V212' stroke='{MUTED}' stroke-width='1.4' fill='none' marker-end='url(#a)'/>")
    b.append(text(526, 248, "ring closes: N3 kicks N0", 11, MUTED, "middle"))
    b += box(370, 290, 150, 54, "Signature (MISR)", "all voltages and spikes")
    b += box(580, 290, 150, 54, "Compare", "with golden 0x53DF")
    b += box(580, 90, 150, 46, "Output pages", "uo[7:0]")
    b += [arrow(160, 117, 222, 150), arrow(160, 262, 222, 220), arrow(320, 185, 370, 185),
          arrow(445, 232, 445, 290), arrow(520, 317, 580, 317), arrow(712, 290, 712, 136),
          arrow(403, 160, 580, 122), text(478, 130, "V0, spike", 11, MUTED, "middle"),
          text(704, 262, "DONE, PASS", 11, MUTED, "end"), arrow(160, 280, 370, 310),
          text(250, 322, "stimulus to N1..N3", 11, MUTED, "middle"),
          text(370, 362, "The four spikes also leave on pins uo[0] and uio[7:5].", 11, MUTED)]
    return svg(760, 380, b, "Chip architecture")


FIGURES = {
    "neuron_waveform.svg": fig_neuron,
    "ring_behaviours.svg": fig_ring,
    "bist_voltages.svg": fig_bist,
    "architecture.svg": fig_architecture,
    "utilization.svg": lambda: bars(
        "Tile utilization at each stage", "Standard-cell utilization of the 1x1 tile, from the GitHub Actions builds.",
        [("Single neuron", "149 cells", 8.3, "8.3%", "#9aa5b1"), ("Four-neuron ring", "431 cells", 27.7, "27.7%", "#9aa5b1"),
         ("+ first self-test", "671 cells", 42.6, "42.6%", "#9aa5b1"),
         ("+ improved self-test", "930 cells", 61.0, "61.0%", ACCENT)], "%", 80),
    "fault_coverage.svg": lambda: bars(
        "Self-test fault coverage, before and after", "Share of testable single faults that make the chip report FAIL "
        "(independent review, 193 faults).",
        [("First self-test", "130 of 171 detected", 76.0, "76%", "#9aa5b1"),
         ("Improved self-test", "174 of 175 detected", 99.4, "99.4%", ACCENT)], "%", 100),
}

if __name__ == "__main__":
    assert BIST_LEN == 1024
    for name, make in FIGURES.items():
        (HERE / name).write_text(make(), encoding="utf-8")
        print("wrote", name)
