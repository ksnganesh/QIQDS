"""Compare the curves drawn by scripts/plot_signature_rates.py with numbers READ OFF the printed Figs. 3-7 of
Fan et al., PRA 114, 032617 (2026).

The readings were taken from a 300-dpi render of the PDF by colour-mask digitisation (axis frames = axis limits).
Accuracy: ~2e-4 in V, ~1-2 % in rate for Figs. 3-6; for the dashed curves of Fig. 7 the abscissa is good to ~1 km,
i.e. ~5 % in rate.  Where the paper prints a number in its text or caption (V_min of Fig. 5, the cutoffs of Fig. 7)
that number is used instead.

    python scripts/plot_signature_rates.py           # fills results/curves/ (once)
    python scripts/compare_figure_readings.py        # markdown tables: code / paper
"""
import json
import math
import os
import sys

import numpy as np
from scipy.interpolate import PchipInterpolator

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
CURVES = os.path.join(ROOT, "results", "curves")

# ---- readings: {curve: ({abscissa: rate}, {rate: abscissa} or V_min)} ---------------------------------------------
FIG3 = {  # signature rate vs n, p = 0
    1.0: ({1e8: 2.93e5, 1e9: 3.29e6}, {1e2: 9.54e5, 1e3: 1.53e6, 1e4: 5.74e6}),
    0.96: ({1e8: 1.68e5, 1e9: 1.98e6}, {1e2: 2.50e6, 1e3: 3.44e6, 1e4: 1.06e7}),
    0.92: ({1e8: 7.43e4, 1e9: 1.03e6}, {1e2: 9.57e6, 1e3: 1.14e7, 1e4: 2.54e7}),
    0.88: ({1e9: 2.15e5}, {1e3: 1.51e8, 1e4: 2.04e8})}
FIG4 = {  # signature rate vs V at n = 1e10; (rates, V_min).  V_min of p = 0 is printed (0.8622); the others are read.
    0.0: ({0.90: 7.13e6, 0.96: 2.09e7, 0.995: 3.21e7}, 0.8622),
    0.05: ({0.90: 6.05e6, 0.96: 1.56e7, 0.995: 2.28e7}, 0.8540),
    0.10: ({0.90: 4.70e6, 0.96: 1.17e7, 0.995: 1.71e7}, 0.8517),
    0.15: ({0.90: 3.47e6, 0.96: 8.51e6, 0.995: 1.24e7}, 0.8510)}
FIG5 = {  # (n, p): (rates vs V, V_min printed in the caption)
    (1e10, 0.0): ({0.90: 7.13e6, 0.95: 1.84e7, 0.995: 3.21e7}, 0.8622),
    (1e10, 0.155): ({0.90: 3.38e6, 0.95: 7.31e6, 0.995: 1.20e7}, 0.8508),
    (1e9, 0.0): ({0.90: 5.92e5, 0.995: 3.06e6}, 0.8686),
    (1e9, 0.090): ({0.90: 4.05e5, 0.995: 1.69e6}, 0.8608),
    (1e8, 0.0): ({0.95: 1.40e5, 0.995: 2.70e5}, 0.8835),
    (1e8, 0.035): ({0.95: 1.15e5, 0.995: 2.13e5}, 0.8799)}
FIG6 = {  # STANDARD variant; (rates vs n, n at rate levels)
    "nadlinger": ({1e8: 3.57e5, 1e9: 4.00e6}, {1e2: 8.69e5, 1e3: 1.28e6, 1e4: 4.82e6, 1e5: 3.12e7}),
    "zhang": ({1e8: 4.81e4, 1e9: 8.65e5}, {1e2: 2.24e7, 1e3: 2.44e7, 1e4: 4.18e7, 1e5: 1.66e8}),
    "lu": ({1e8: 2.31e5, 1e9: 2.76e6}, {1e2: 1.92e6, 1e4: 7.90e6, 1e5: 4.67e7})}
FIG7 = {  # (kind, N): rate at distance L (km)
    ("ideal", 2e14): {1: 3.10e6, 5: 2.50e6, 10: 1.89e6, 20: 1.29e6, 25: 9.92e5, 40: 4.41e5, 60: 1.44e5, 80: 5.23e4,
                      100: 1.37e4, 110: 6.01e3, 120: 1.27e3},
    ("ideal", 1e14): {1: 1.51e6, 5: 1.19e6, 10: 9.17e5, 20: 6.11e5, 25: 4.66e5, 40: 2.02e5, 60: 6.34e4, 80: 1.70e4,
                      100: 2.86e3},
    ("real", 2e14): {1: 2.74e5, 5: 2.02e5, 10: 1.26e5, 15: 7.26e4, 20: 3.65e4, 25: 1.18e4},
    ("real", 1e14): {1: 9.41e4, 5: 6.27e4, 10: 2.98e4, 15: 6.81e3}}


# ---- evaluate cached curves ------------------------------------------------------------------------------------------
def load(key):
    return json.load(open(os.path.join(CURVES, key + ".json")))


def _xr(c):
    x, r = np.array(c["x"], float), np.array(c["r"], float)
    m = r > 0
    return x[m], r[m]


def r_at(c, x, logx):
    xs, rs = _xr(c)
    if not xs[0] <= x <= xs[-1]:
        return math.nan
    f = PchipInterpolator(np.log(xs) if logx else xs, np.log(rs))
    return math.exp(float(f(math.log(x) if logx else x)))


def x_at_r(c, level, logx):
    xs, rs = _xr(c)
    rs = np.maximum.accumulate(rs)
    keep = np.concatenate([[True], np.diff(rs) > 0])
    xs, rs = xs[keep], rs[keep]
    if not rs[0] < level < rs[-1]:
        return math.nan
    v = float(PchipInterpolator(np.log(rs), np.log(xs) if logx else xs)(math.log(level)))
    return math.exp(v) if logx else v


# ---- report ----------------------------------------------------------------------------------------------------------
def main():
    import plot_signature_rates as psr
    from diqds.photonic import HERALDING_SCALE as HS
    psr.Opt.replot = True
    allratios = {}

    def row(fig, label, what, code, paper, rel=True):
        ratio = code / paper
        allratios.setdefault(fig, []).append(abs(ratio - 1.0) if rel else None)
        print(f"| {label} | {what} | {code:.4g} | {paper:.4g} | {ratio:.3f} |")

    def table(title):
        print(f"\n**{title}**\n\n| curve | quantity | code | paper (read) | code / paper |\n|---|---|---|---|---|")

    table("Fig. 3 (p = 0): rate at fixed n, and n at which a given rate is reached")
    for V, (rn, nr) in FIG3.items():
        c = load(f"fig3_V{V:g}_p0_rkm")
        for n, v in rn.items():
            row("fig3", f"V = {V:g}", f"r_sig(n = {n:.0e})", r_at(c, n, True), v)
        for lev, n in nr.items():
            row("fig3", f"V = {V:g}", f"n at r_sig = {lev:.0e}", x_at_r(c, lev, True), n)

    table("Fig. 4 (n = 1e10): rate at fixed V, and V_min")
    for p, (rv, vmin) in FIG4.items():
        c = load(f"V_n1e10_p{p:g}_rkm")
        for V, v in rv.items():
            row("fig4", f"p = {p:g}", f"r_sig(V = {V})", r_at(c, V, False), v)
        row("fig4", f"p = {p:g}", "V_min", c["x_min"], vmin)

    table("Fig. 5: rate at fixed V (solid: p = 0, dashed: the legend's p), and V_min printed in the caption")
    for (n, p), (rv, vmin) in FIG5.items():
        c = load(f"V_n{n:.0e}_p{p:g}_rkm".replace("+", ""))
        for V, v in rv.items():
            row("fig5", f"n = {n:.0e}, p = {p:g}", f"r_sig(V = {V})", r_at(c, V, False), v)
        row("fig5", f"n = {n:.0e}, p = {p:g}", "V_min", c["x_min"], vmin)

    table("Fig. 6 (STANDARD protocol): rate at fixed n, and n at which a given rate is reached")
    for key, (rn, nr) in FIG6.items():
        c = load(f"fig6_{key}_standard")
        for n, v in rn.items():
            row("fig6", key, f"r_sig(n = {n:.0e})", r_at(c, n, True), v)
        for lev, n in nr.items():
            row("fig6", key, f"n at r_sig = {lev:.0e}", x_at_r(c, lev, True), n)

    table("Fig. 7 (CALIBRATED model, see README): rate at fixed L")
    d = psr.fig7_data()
    cal = d["calibration"]
    for c in d["curves"]:
        rd = FIG7[(c["kind"], c["N"])]
        for L, v in rd.items():
            row("fig7", f"{c['kind']}, N = {c['N']:.0e}", f"r_sig(L = {L} km)", r_at(c, float(L), False), v)
        print(f"| {c['kind']}, N = {c['N']:.0e} | cutoff (km) | {c['L_cut']:.2f} | {c['L_cut_paper']:.2f} | "
              f"{c['L_cut'] / c['L_cut_paper']:.4f} |")
    print(f"\nFig. 7 calibration: heralding scale {HS} (fitted to the printed ideal curves); "
          f"V_eff(ideal) = {cal['V_ideal']:.4f} (fitted to 111.46 km at N = 1e14); "
          f"realistic V_eff(L) = {cal['V0']:.4f} - {cal['c']:.2e} (exp(L/2L0) - 1) (fitted to 17.82 and 28.87 km).")

    print("\n**Median |code/paper - 1| per figure** (readings of rate/threshold quantities only)\n")
    for fig, v in allratios.items():
        v = [x for x in v if x is not None]
        print(f"- {fig}: {100 * float(np.median(v)):.1f} %  (max {100 * max(v):.1f} %, {len(v)} readings)")


if __name__ == "__main__":
    main()
