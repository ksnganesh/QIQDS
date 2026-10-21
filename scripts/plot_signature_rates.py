"""Fig. 3-like (signature rate vs n for several V) and Fig. 5-like (rate vs V with / without noisy preprocessing)
plots from the finite-size analysis. Writes PNGs into --out (default: project root)."""
import argparse, sys, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from diqds.experiments import signature_rate_werner
from diqds.presets import RKM_SIFTED

ap = argparse.ArgumentParser()
ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ap.add_argument("--quick", action="store_true", help="coarser grids")
ap.add_argument("--which", choices=["fig3", "fig5", "both"], default="both")
a = ap.parse_args()
pts = 8 if a.quick else 14


def fig3():
    """r_sig vs n for several visibilities, p = 0."""
    fig, ax = plt.subplots(figsize=(6, 4))
    ns = np.logspace(6.5, 11, pts)
    for V in (0.99, 0.95, 0.92, 0.90):
        r = [signature_rate_werner(int(n), V, RKM_SIFTED, p=0.0, restarts=1)["r_sig"] for n in ns]
        ax.loglog(ns, np.maximum(r, 1e-3), "o-", ms=3, label=f"V = {V}")
    ax.set_xlabel("number of rounds n"); ax.set_ylabel("signature rate r_sig (per execution)"); ax.set_ylim(1e-2, None)
    ax.set_title("Fig. 3-like: threshold, then ~linear growth (p = 0)"); ax.legend(); ax.grid(alpha=.3, which="both")
    fig.tight_layout(); fig.savefig(os.path.join(a.out, "fig3_like.png"), dpi=150)


def fig5():
    """r_sig vs V for n = 1e8, 1e9, 1e10; p = 0 (solid) and optimised p (dashed)."""
    fig, ax = plt.subplots(figsize=(6, 4))
    colors = {1e8: "tab:red", 1e9: "tab:green", 1e10: "tab:blue"}
    Vs = np.concatenate([np.linspace(0.845, 0.895, 9 if a.quick else 16), [0.93, 0.96]])   # dense near thresholds
    for n, c in colors.items():
        for p, ls, lab in ((0.0, "-", "p = 0"), (None, "--", "p optimised")):
            r = np.array([signature_rate_werner(int(n), V, RKM_SIFTED, p=p, restarts=1)["r_sig"] for V in Vs])
            ax.semilogy(Vs, np.where(r > 0, r, np.nan), ls, color=c, marker="o", ms=2.5, label=f"n = {n:.0e}, {lab}")
    ax.set_xlabel("visibility V"); ax.set_ylabel("r_sig  (zero below threshold: not drawn)")
    ax.set_title("Fig. 5-like: noisy preprocessing lowers the V threshold")
    ax.legend(fontsize=7); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(os.path.join(a.out, "fig5_like.png"), dpi=150)


if a.which in ("fig3", "both"):
    fig3()
if a.which in ("fig5", "both"):
    fig5()
print("done")
