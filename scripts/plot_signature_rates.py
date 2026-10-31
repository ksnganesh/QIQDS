"""Reproduce the plots of Fan et al., PRA 114, 032617 (2026): Figs. 3-7 (signature rate vs n, vs V, vs distance L).

    python scripts/plot_signature_rates.py                    # all five figures (~20 min on one core; curves are cached)
    python scripts/plot_signature_rates.py --which fig3       # one figure (fig3 ... fig7)
    python scripts/plot_signature_rates.py --replot           # redraw from results/curves/*.json, compute nothing
    python scripts/plot_signature_rates.py --quick            # coarser grids (~10 min)
    python scripts/plot_signature_rates.py --force            # ignore the cache and recompute

Settings are the ones printed in the paper's figures (legends and axes read from the PDF):

  Fig. 3  p = 0;  V = 1, 0.96, 0.92, 0.88;  n = 1e5 ... 1e10          (Table I parameters)
  Fig. 4  n = 1e10;  p = 0, 0.05, 0.10, 0.15;  V = 0.84 ... 1
  Fig. 5  solid: p = 0, dashed: p = 0.155 / 0.090 / 0.035 for n = 1e10 / 1e9 / 1e8 (legend values; fixed, not re-optimised
          at every V, which is why the dashed curves fall below the solid ones at high V);  V = 0.84 ... 1
  Fig. 6  (S, Q) of Refs. [73]-[75], protocol variant STANDARD (Ref. [73]'s KGP, as in the paper's text); star at
          n = 1.5e6 on the Ref. [73] curve, diamond at n = 2.4e6 on the Ref. [75] curve
  Fig. 7  all-photonic scheme.  NOT an independent reproduction: the paper does not give P_H or the heralded state, so a
          heralding-probability scale (0.3) and the effective visibility of the heralded state are CALIBRATED on the
          printed curves and the quoted cutoff distances (see fig7_data and diqds/photonic.py).

Figs. 3-5 and 7 use RKM_SIFTED, Fig. 6 uses STANDARD (see diqds/presets.py).
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, ROOT)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.interpolate import PchipInterpolator

from diqds.experiments import minimum_rounds, secret_key_length
from diqds.finite_key import min_visibility, werner_S_Q
from diqds.presets import EXPERIMENTS, RKM_SIFTED, STANDARD
from diqds.security import QDSParams, choose_n_s, signature_rate

N_S = choose_n_s(QDSParams())                       # Table I -> n_s = 46
CURVES = os.path.join(ROOT, "results", "curves")    # one JSON per computed curve (resumable)
COL = dict(red="#FF6A2A", red3="#D95319", blue="#1A9AF7", yellow="#EDB120", green="#77AC30")   # sampled from the PDF
# (the paper's Fig. 3 uses the darker red "red3"; Figs. 4-7 the brighter one)

# ----------------------------------------------------------------------------- settings printed in the paper
FIG3_V = (1.0, 0.96, 0.92, 0.88)
FIG4_P = (0.0, 0.05, 0.10, 0.15)
FIG5 = ((1e10, 0.155, "red"), (1e9, 0.090, "blue"), (1e8, 0.035, "yellow"))     # (n, dashed-curve p, colour)
FIG6 = (("nadlinger", "parameters from Ref. [73]", "blue"),
        ("zhang", "parameters from Ref. [74]", "red"),
        ("lu", "parameters from Ref. [75]", "yellow"))
FIG7_CUTS = {"ideal": {1e14: 111.46, 2e14: 126.53}, "real": {1e14: 17.82, 2e14: 28.87}}   # quoted in Sec. IV
FIG7_L0 = 22.0


class Opt:
    npts, replot, force = 26, False, False


def log(*a):
    print(*a, flush=True)


# ----------------------------------------------------------------------------- compute helpers
def _ell(n, S, Q, variant, p, z=None):
    """Optimised key length of Eq. (9); warm start from the previous optimum (z), cold start as a fallback."""
    if z is not None:
        ell, _, ex = secret_key_length(int(n), S, Q, variant, p, restarts=1, z0=z)
        if ell > 0:
            return ell, ex["z"]
    ell, _, ex = secret_key_length(int(n), S, Q, variant, p, restarts=2)
    return ell, ex["z"]


def p_opt_rule(n):
    """Noisy-preprocessing p that maximises the key at the threshold, as a smooth function of n: the quadratic through the
    paper's three legend values (n, p) = (1e8, 0.035), (1e9, 0.090), (1e10, 0.155) of Fig. 5.  A direct search gives
    0.080 at n = 6.5e8 (rule: 0.079).  Used by Fig. 7 instead of p = None: the p = None path of maximize_key_length can
    stay in the p ~ 0 basin when warm-started (see maximize_key_length_over_p), and a full search per point is ~12 x slower."""
    x = math.log10(n) - 8.0
    return float(min(0.3, max(0.0, 0.035 + 0.055 * x + 0.005 * x * (x - 1.0))))


def _ell_p01(n, S, Q, variant, zs=None):
    """Key length with p = the better of {0, p_opt_rule(n)}.  The rule is the threshold-optimal p; far above the threshold
    p = 0 is better (the dashed curves of the paper's Fig. 5 fall below the solid ones there), so both are tried."""
    zs = zs or [None, None]
    best = -math.inf
    for i, p in enumerate((0.0, p_opt_rule(n))):
        if i == 1 and p == 0.0:
            break
        ell, zs[i] = _ell(n, S, Q, variant, p, zs[i])
        best = max(best, ell)
    return best, zs


def _cached(key, fn):
    path = os.path.join(CURVES, key + ".json")
    if os.path.exists(path) and not Opt.force:
        return json.load(open(path))
    if Opt.replot:
        raise SystemExit(f"--replot: no cached curve '{key}' (run without --replot first)")
    t0 = time.time()
    out = fn()
    os.makedirs(CURVES, exist_ok=True)
    json.dump(out, open(path, "w"))
    log(f"  computed {key}  [{time.time() - t0:.0f} s]")
    return out


def rate_vs_n(S, Q, variant, p, n_hi=1e10, n_lo=1e5):
    """r_sig(n): the threshold n_min by bisection, then a grid that is dense just above it (the rise is ~vertical)."""
    n_min = minimum_rounds(S, Q, variant, p=p, lo=n_lo, hi=n_hi, ratio=1.01)
    if math.isnan(n_min):
        raise RuntimeError("no positive key up to n_hi")
    ns = n_min * (1.0 + np.geomspace(1e-3, n_hi / n_min - 1.0, Opt.npts))
    r, z = [], None
    for n in ns:
        ell, z = _ell(n, S, Q, variant, p, z)
        r.append(float(signature_rate(ell, N_S)))
    return dict(x_min=float(n_min), x=[float(v) for v in ns], r=r)


def rate_vs_V(n, variant, p, v_hi=1.0):
    """r_sig(V) at fixed n and fixed p: the threshold V_min by bisection, then a grid dense just above it."""
    v_min = min_visibility(int(n), p=p, v_lo=0.80, v_hi=0.99, tol=2e-5,
                           key_weight=variant.key_weight, ec_model=variant.ec_model, restarts=2)
    vs = v_min + np.geomspace(2e-4, v_hi - v_min, Opt.npts)
    r, z = [], None
    for V in vs:
        S, Q = werner_S_Q(float(V))
        ell, z = _ell(n, S, Q, variant, p, z)
        r.append(float(signature_rate(ell, N_S)))
    return dict(x_min=float(v_min), x=[float(v) for v in vs], r=r)


# ----------------------------------------------------------------------------- data for each figure
def fig3_data():
    out = []
    for V in FIG3_V:
        S, Q = werner_S_Q(V)
        c = _cached(f"fig3_V{V:g}_p0_rkm", lambda: rate_vs_n(S, Q, RKM_SIFTED, 0.0))
        out.append(dict(label=f"V={V:g}", V=V, **c))
    return out


def _vcurve(n, p):
    return _cached(f"V_n{n:.0e}_p{p:g}_rkm".replace("+", ""), lambda: rate_vs_V(n, RKM_SIFTED, p))


def fig4_data():
    return [dict(label="p=0" if p == 0 else f"p={p:.2f}", p=p, **_vcurve(1e10, p)) for p in FIG4_P]


def fig5_data():
    out = []
    for n, pd, col in FIG5:
        out.append(dict(n=n, p=0.0, col=col, **_vcurve(n, 0.0)))
        out.append(dict(n=n, p=pd, col=col, **_vcurve(n, pd)))
    return out


def fig6_data():
    out = []
    for key, label, col in FIG6:
        e = EXPERIMENTS[key]
        c = _cached(f"fig6_{key}_standard", lambda: rate_vs_n(e.S, e.Q, STANDARD, "auto"))
        out.append(dict(key=key, label=label, col=col, S=e.S, Q=e.Q, rate_per_hour=e.rate_per_hour, **c))
    for item, n in ((out[0], 1.5e6), (out[2], 2.4e6)):          # star (Ref. [73]) and diamond (Ref. [75])
        e = EXPERIMENTS[item["key"]]
        ell, _ = _ell(n, e.S, e.Q, STANDARD, "auto")
        item["marker"] = dict(n=n, r=float(signature_rate(ell, N_S)))
    return out


def fig7_data():
    """Signature rate vs distance for the all-photonic scheme.

    Model (see diqds/photonic.py): n_H(L) = N P_H(L) heralded rounds with P_H = 0.3 [2T(1-T)]^2 eta_C^2 / 2 (the factor 0.3
    is calibrated on the printed ideal curves), and the heralded state is a Werner state of effective visibility V_eff, so
    r_sig = r_sig(n_H, V_eff) from Eq. (9) with p = the better of 0 and p_opt_rule(n_H).
      ideal : V_eff constant, fitted to ONE number (cutoff 111.46 km at N = 1e14).  The cutoff at N = 2e14 is a prediction
              (126.71 km vs 126.53 km printed).
      real  : V_eff(L) = V0 - c (exp(L / 2 L0) - 1), i.e. noise growing like 1/eta_C (multiphoton false heralds); V0 and c
              are fitted to BOTH quoted cutoffs (17.82 and 28.87 km).  The rest of the realistic curves is model output;
              scripts/compare_figure_readings.py compares it with readings off the printed curves.
    """
    from diqds.photonic import heralding_probability as PH
    nH = lambda L, N: N * PH(L)
    kw = dict(key_weight=RKM_SIFTED.key_weight, ec_model=RKM_SIFTED.ec_model, restarts=2)

    def calib():
        n_cut = nH(FIG7_CUTS["ideal"][1e14], 1e14)
        Vmin = lambda n: min_visibility(int(n), p=p_opt_rule(n), v_hi=0.99, tol=2e-5, **kw)
        return dict(V_ideal=Vmin(n_cut), n_cut_ideal=n_cut,
                    V_real_a=Vmin(nH(FIG7_CUTS["real"][1e14], 1e14)), V_real_b=Vmin(nH(FIG7_CUTS["real"][2e14], 2e14)))

    cal = _cached("fig7_calibration", calib)
    u = lambda L: math.exp(L / (2.0 * FIG7_L0)) - 1.0
    La, Lb = FIG7_CUTS["real"][1e14], FIG7_CUTS["real"][2e14]
    c = (cal["V_real_a"] - cal["V_real_b"]) / (u(Lb) - u(La))
    V0 = cal["V_real_a"] + c * u(La)
    V_real = lambda L: V0 - c * u(L)
    cal = dict(cal, V0=V0, c=c)

    def ideal_chain():                                  # r depends on n_H only: one chain serves both N
        n_cut, n_hi = cal["n_cut_ideal"], nH(0.0, 2e14)
        ns = n_cut * (1.0 + np.geomspace(1e-3, n_hi / n_cut - 1.0, Opt.npts))
        S, Q = werner_S_Q(cal["V_ideal"])
        r, z = [], None
        for n in ns:
            ell, z = _ell_p01(n, S, Q, RKM_SIFTED, z)
            r.append(float(signature_rate(ell, N_S)))
        return dict(x=[float(v) for v in ns], r=r)

    chain = _cached("fig7_ideal_chain", ideal_chain)
    f = PchipInterpolator(np.log(chain["x"]), np.log(np.maximum(chain["r"], 1e-12)))
    P0, curves = PH(0.0), []
    for N, col in ((1e14, "yellow"), (2e14, "red")):
        L_cut = FIG7_L0 * math.log(N * P0 / cal["n_cut_ideal"])          # n_H(L_cut) = n_cut -> prediction for N = 2e14
        Ls = L_cut - np.geomspace(0.01, L_cut, 160)
        n = np.array([nH(L, N) for L in Ls])
        r = np.where(n > chain["x"][0], np.exp(f(np.log(np.clip(n, chain["x"][0], chain["x"][-1])))), 0.0)
        curves.append(dict(kind="ideal", N=N, col=col, L_cut=L_cut, L_cut_paper=FIG7_CUTS["ideal"][N],
                           x=[float(v) for v in Ls[::-1]], r=[float(v) for v in r[::-1]]))
    for N, col in ((1e14, "yellow"), (2e14, "red")):
        L_cut = FIG7_CUTS["real"][N]

        def chain_real():                               # V_eff depends on L: direct chain from the cutoff towards L = 0
            Ls = L_cut - np.geomspace(0.01, L_cut, Opt.npts)
            r, z = [], None
            for L in Ls:
                S, Q = werner_S_Q(V_real(float(L)))
                ell, z = _ell_p01(nH(float(L), N), S, Q, RKM_SIFTED, z)
                r.append(float(signature_rate(ell, N_S)))
            return dict(x=[float(v) for v in Ls[::-1]], r=r[::-1])

        c_ = _cached(f"fig7_real_N{N:.0e}".replace("+", ""), chain_real)
        curves.append(dict(kind="real", N=N, col=col, L_cut=L_cut, L_cut_paper=L_cut, **c_))
    return dict(curves=curves, calibration=cal)


# ----------------------------------------------------------------------------- drawing
def _style():
    plt.rcParams.update({
        "font.family": ["Liberation Sans", "DejaVu Sans"], "font.weight": "bold", "axes.labelweight": "bold",
        "mathtext.default": "regular", "axes.linewidth": 0.8, "savefig.dpi": 220})


def _axes(xlabel, xlim, ylim, logx):
    fig, ax = plt.subplots(figsize=(4.4, 4.1))
    ax.set_yscale("log")
    if logx:
        ax.set_xscale("log")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel("Signature rate", fontsize=9)
    ax.minorticks_off()
    ax.tick_params(which="both", direction="in", top=True, right=True, labelsize=7, width=0.8)
    return fig, ax


def _legend(ax, loc="upper left", anchor=None, handles=None, labels=None):
    kw = dict(loc=loc, bbox_to_anchor=anchor, frameon=False, handlelength=2.4, labelspacing=0.12, borderaxespad=0.5,
              prop=dict(size=7, style="italic", weight="bold"))
    ax.legend(handles, labels, **kw) if handles is not None else ax.legend(**kw)


def _line(c, logx):
    """Smooth (PCHIP on log r) polyline of a cached curve, starting with the ~vertical rise from the axis floor."""
    x, r = np.array(c["x"], float), np.array(c["r"], float)
    m = r > 0
    x, r = x[m], r[m]
    xi = np.geomspace(x[0], x[-1], 700) if logx else np.linspace(x[0], x[-1], 700)
    yi = np.exp(PchipInterpolator(np.log(x) if logx else x, np.log(r))(np.log(xi) if logx else xi))
    return np.concatenate([[c["x_min"]], xi]), np.concatenate([[1e-3], yi])


def _vticks(ax):
    ax.set_xticks(np.arange(0.84, 1.0001, 0.02))
    ax.set_xticklabels(["0.84", "0.86", "0.88", "0.9", "0.92", "0.94", "0.96", "0.98", "1"])


def plot_fig3(d, out):
    fig, ax = _axes("Number of rounds", (1e5, 1e10), (1, 1e8), True)
    for c, col in zip(d, ("red3", "blue", "yellow", "green")):
        ax.plot(*_line(c, True), color=COL[col], lw=1.5, label=c["label"])
    _legend(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig3_like.png"))


def plot_fig4(d, out):
    fig, ax = _axes("V", (0.84, 1.0), (1, 1e8), False)
    for c, col, ls in zip(d, ("red", "blue", "yellow", "green"), ("-", "--", ":", "-.")):
        ax.plot(*_line(c, False), color=COL[col], lw=1.5, ls=ls, label=c["label"])
    _vticks(ax)
    _legend(ax, "lower right", (1.0, 0.16))
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig4_like.png"))


def plot_fig5(d, out):
    fig, ax = _axes("V", (0.84, 1.0), (1, 1e8), False)
    fmt = lambda n: f"n=10$^{{{int(round(math.log10(n)))}}}$"
    for c in d:
        solid = c["p"] == 0.0
        ax.plot(*_line(c, False), color=COL[c["col"]], lw=1.5, ls="-" if solid else "--",
                label=f"{fmt(c['n'])},p={'0' if solid else format(c['p'], '.3f')}")
    h, lab = ax.get_legend_handles_labels()
    order = [0, 2, 4, 1, 3, 5]                      # the paper's legend order: three p = 0 entries, then the dashed ones
    _legend(ax, "lower right", (1.0, 0.16), [h[i] for i in order], [lab[i] for i in order])
    _vticks(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig5_like.png"))


def plot_fig6(d, out):
    fig, ax = _axes("Number of round", (1e5, 1e10), (1, 1e8), True)
    for c in d:
        ax.plot(*_line(c, True), color=COL[c["col"]], lw=1.5, label=c["label"])
    m73, m75 = d[0]["marker"], d[2]["marker"]
    ax.plot(m73["n"], m73["r"], marker="*", ms=9, mfc=COL["blue"], mec="k", mew=0.8, ls="none",
            label="Achievable rounds for Ref. [73]")
    ax.plot(m75["n"], m75["r"], marker="D", ms=6, mfc=COL["yellow"], mec="k", mew=0.8, ls="none",
            label="Extrapolated rounds for Ref. [75]")
    _legend(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig6_like.png"))


def plot_fig7(d, out, note=True):
    fig, ax = _axes("L (km)", (0, 160), (1, 1e7), False)
    lab = lambda ideal, N: (f"$V_{{HOM}}$={'1' if ideal else '0.975'}, $g^{{(2)}}$={'0' if ideal else '0.01'}, "
                            f"N={int(N / 1e14)}×10$^{{14}}$")
    by = {(c["kind"], c["N"]): c for c in d["curves"]}
    for kind, N, ls in (("real", 1e14, "-"), ("real", 2e14, "-"), ("ideal", 1e14, "--"), ("ideal", 2e14, "--")):
        c = by[(kind, N)]
        x, r = np.array(c["x"]), np.array(c["r"])
        m = r > 0
        x, r = x[m], r[m]
        xi = np.linspace(x[0], x[-1], 800)
        yi = np.exp(PchipInterpolator(x, np.log(r))(xi))
        ax.plot(np.concatenate([xi, [c["L_cut"]]]), np.concatenate([yi, [1e-3]]), color=COL[c["col"]], lw=1.5, ls=ls,
                label=lab(kind == "ideal", N))
    ax.set_xticks(range(0, 161, 20))
    _legend(ax, "upper right", (1.0, 1.0))
    if note:
        ax.text(0.03, 0.03, "calibrated model (see README)", transform=ax.transAxes, fontsize=6, style="italic", color="0.35")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "fig7_like.png"))


DATA = dict(fig3=fig3_data, fig4=fig4_data, fig5=fig5_data, fig6=fig6_data, fig7=fig7_data)
PLOT = dict(fig3=plot_fig3, fig4=plot_fig4, fig5=plot_fig5, fig6=plot_fig6, fig7=plot_fig7)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=ROOT, help="directory for the PNGs (default: project root)")
    ap.add_argument("--which", choices=["fig3", "fig4", "fig5", "fig6", "fig7", "both", "all"], default="all",
                    help="'both' = fig3 + fig5 (the old default)")
    ap.add_argument("--quick", action="store_true", help="coarser grids")
    ap.add_argument("--replot", action="store_true", help="draw from the cache only, compute nothing")
    ap.add_argument("--force", action="store_true", help="recompute even if cached")
    ap.add_argument("--no-note", action="store_true", help="omit the 'calibrated model' note on Fig. 7")
    a = ap.parse_args()
    Opt.npts, Opt.replot, Opt.force = (14 if a.quick else 26), a.replot, a.force
    _style()
    names = {"all": list(DATA), "both": ["fig3", "fig5"]}.get(a.which, [a.which])
    for name in names:
        log(f"[{name}]")
        d = DATA[name]()
        if name == "fig7":
            PLOT[name](d, a.out, note=not a.no_note)
            cal = d["calibration"]
            log(f"  calibration: V_eff(ideal) = {cal['V_ideal']:.4f}; realistic V0 = {cal['V0']:.4f}, c = {cal['c']:.2e}")
            for c in d["curves"]:
                log(f"  {c['kind']:5s} N={c['N']:.0e}: cutoff {c['L_cut']:.2f} km (paper {c['L_cut_paper']:.2f}), "
                    f"rate at L = 0: {c['r'][0]:.3g}")
        else:
            PLOT[name](d, a.out)
    log("done")


if __name__ == "__main__":
    main()
