"""
Regenerate the tables / numbers of the follow-up paper ("Tighter finite-size security and a randomness budget for DIQDS")
that this package can compute, and leave the slot for the tightened (Renyi) results.

    python scripts/reproduce_paper_tables.py                     # everything below (~1-2 min)
    python scripts/reproduce_paper_tables.py --tightened results/renyi_thresholds.json

Baseline thresholds (Table 2, left column) are read from results/thr_*.json, produced by
`scripts/compare_with_paper.py --part thresholds --n 1e8` (also 1e9, 1e10).  Format of the --tightened file:
    {"1e8": {"p0": 0.8719, "np": 0.8646}, "1e9": {...}, "1e10": {...}, "n_min_11km": 1.04e6}
"""
import argparse, json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from diqds.diqkd import plan_distribution
from diqds.experiments import budget_split_scan, minimum_rounds
from diqds.finite_key import (asymptotic_visibility_threshold, maximize_key_length, penalty_breakdown, werner_S_Q)
from diqds.presets import LU_2026_11KM, NADLINGER_2022, RKM_SIFTED, STANDARD
from diqds.randomness import demand, entropy_per_round, entropy_per_party, sampler_bits_per_round
from diqds.security import QDSParams, choose_n_s

RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
ap = argparse.ArgumentParser()
ap.add_argument("--tightened", default=None, help="JSON with the Renyi-bound results (right-hand column of Table 2)")
a = ap.parse_args()
tight = json.load(open(a.tightened)) if a.tightened else None
P = print
PAPER_BASE = {"1e8": (0.8835, 0.8799), "1e9": (0.8686, 0.8608), "1e10": (0.8622, 0.8508)}
PAPER_TIGHT = {"1e8": (0.8719, 0.8646), "1e9": (0.8637, 0.8526), "1e10": (0.8600, 0.8462)}

# ------------------------------------------------------------------ Sec. 3.2
P("## Sec. 3.2  signature layer: n_s from Eq. (4)  (eps = 1e-10, n_m = 1000)\n")
P("| eps_snd | n_s (code) | paper | 3 n_s |\n|---|---|---|---|")
for es, pap in ((1e-11, 45), (5e-11, 46), (9e-11, 48), (9.9e-11, 51)):
    n_s = choose_n_s(QDSParams(eps_snd=es))
    P(f"| {es:.1e} | {n_s} | {pap} | {3 * n_s} |")
P(f"\nn_m = 1e6: n_s = {choose_n_s(QDSParams(n_m=10 ** 6))} (paper: 56)\n")

# ------------------------------------------------------------------ Table 3 and Sec. 3.3
P("## Table 3  private random bits per heralded round (Eq. 5; 16-bit thresholding sampler)\n")
P("| gamma | p = 0 | p = 0.05 | p = 0.10 | p = 0.05, 16-bit sampler |\n|---|---|---|---|---|")
for g in (0.01, 0.05, 0.10, 0.30):
    P(f"| {g} | {entropy_per_round(g, 0):.2f} | {entropy_per_round(g, .05):.2f} | {entropy_per_round(g, .10):.2f} | {sampler_bits_per_round(g, .05, 16):.1f} |")
al, bo = entropy_per_party(0.10, 0.05)
P(f"\nAt gamma = 0.1, p = 0.05: {al + bo:.2f} bits/round = Alice {al:.2f} + Bob {bo:.2f}.\n")
P("| Run | rounds | total | x the 138-bit key | bit/s |\n|---|---|---|---|---|")
lu_rate = LU_2026_11KM.rounds / (LU_2026_11KM.hours * 3600)
ion_rate = NADLINGER_2022.rounds / (7.9 * 3600)
for lab, n, rate in (("ion run [73]", 1.5e6, ion_rate), ("11 km, baseline extrapolation", 2.4e6, lu_rate),
                     ("11 km, tightened (paper's 1.04e6)", 1.04e6, lu_rate)):
    d = demand(n, 0.10, 0.05, 138, rate)
    P(f"| {lab} | {n:.3g} | {d.total_bits / 1e6:.2f} Mbit | {d.bits_per_key_bit:.2g} | {d.bits_per_second:.2f} |")
P(f"\nPhotonic link: nu * P_H * H_round = {75e6 * 1e-3 * entropy_per_round(.1, .05) / 1e6:.2f} Mbit/s at 75 MHz, P_H = 1e-3.\n")

# ------------------------------------------------------------------ ledger at the optimiser's own parameters
P("## Ledger at the optimiser's own (gamma, p)  (Table 3 uses an illustrative gamma = 0.1, p = 0.05)\n")
P("| operating point | protocol | gamma | p | bits/round | total for the run |\n|---|---|---|---|---|---|")
for lab, n, S, Q, v in (("ion run [73], n = 1.5e6", 1_500_000, NADLINGER_2022.S, NADLINGER_2022.Q, STANDARD),
                        ("11 km [75], n = 3e6", 3_000_000, LU_2026_11KM.S, LU_2026_11KM.Q, STANDARD),
                        ("Werner V = 0.95, n = 1e9", 10 ** 9, *werner_S_Q(0.95), RKM_SIFTED)):
    plan = plan_distribution(n, S, Q, v)
    H = entropy_per_round(plan.gamma, plan.p, v.random_key_basis)
    P(f"| {lab} | {v.name} | {plan.gamma:.3f} | {plan.p:.3f} | {H:.2f} | {n * H / 1e6:.3g} Mbit |")

# ------------------------------------------------------------------ Table 2
P("\n## Table 2  threshold visibility V_min (baseline = EAT bound of Fan et al., sifted reading)\n")
cols = "| n | p | paper baseline | this code (baseline) | asymptote | paper tightened |"
if tight:
    cols += " tightened (yours) | share of finite-size excess recovered |"
P(cols + "\n|" + "---|" * (cols.count("|") - 1))
recovered = []
for key, n in (("1e8", 1e8), ("1e9", 1e9), ("1e10", 1e10)):
    f = os.path.join(RES, f"thr_{n:.0e}.json")
    base = json.load(open(f)) if os.path.exists(f) else None
    for j, (lab, pv) in enumerate((("0", 0.0), ("opt", None))):
        mine = (base["p0"] if j == 0 else base["np"]) if base else float("nan")
        asym = asymptotic_visibility_threshold(pv)
        recovered.append(f"n = {key}, p = {lab}: {100 * (mine - PAPER_TIGHT[key][j]) / (mine - asym):.0f} %")
        row = f"| {key} | {lab} | {PAPER_BASE[key][j]:.4f} | {mine:.4f} | {asym:.4f} | {PAPER_TIGHT[key][j]:.4f} |"
        if tight:
            t = tight[key]["p0" if j == 0 else "np"]
            row += f" {t:.4f} | {100 * (mine - t) / (mine - asym):.0f} % |"
        P(row)
P("\n(Taken at face value, the paper's tightened column recovers this share of the baseline's finite-size excess over the "
  "asymptote: " + ", ".join(recovered) + ". None of its values lies below the asymptote.)\n")

# ------------------------------------------------------------------ 11 km operating point
P("## 11 km operating point (Lu et al.: S = 2.612, Q = 0.0285, 1.208e6 events in 624 h)\n")
P("| baseline protocol | rounds for ell > 0 | rounds for ell >= 3 n_s = 138 | hours at 0.538 events/s |\n|---|---|---|---|")
n_s = choose_n_s()
rows = {}
for v in (STANDARD, RKM_SIFTED):
    n0 = minimum_rounds(LU_2026_11KM.S, LU_2026_11KM.Q, v, ratio=1.002)
    n1 = minimum_rounds(LU_2026_11KM.S, LU_2026_11KM.Q, v, ratio=1.002, ell_min=3 * n_s)
    rows[v.name] = (n0, n1)
    P(f"| {v.name} | {n0:.3g} | {n1:.3g} | {n1 / LU_2026_11KM.rate_per_hour:.0f} |")
P(f"\nThe paper's baseline cell is 'at most 2.4e6 rounds / 1248 h' (Fan et al.'s extrapolated point, no-sifting protocol).")
if tight and "n_min_11km" in tight:
    nt = tight["n_min_11km"]
    P(f"Your tightened value {nt:.3g} rounds = {nt / LU_2026_11KM.rate_per_hour:.0f} h is x{rows['standard'][1] / nt:.2f} fewer rounds than "
      f"the exact no-sifting baseline and x{rows['rkm_sifted'][1] / nt:.2f} fewer than the exact sifted baseline: say which protocol it uses.")
else:
    P(f"The paper's 1.04e6 would be x{rows['standard'][1] / 1.04e6:.2f} fewer than the exact no-sifting baseline, "
      f"x{rows['rkm_sifted'][1] / 1.04e6:.2f} fewer than the exact sifted (random-key-basis) baseline.")

# ------------------------------------------------------------------ budget split
P("\n## Budget split between key layer and hashing layer (eps = 1e-10, eps_EA = eps_PA = eps_snd/5)\n")
for lab, n, S, Q, v in (("Werner V = 0.95, n = 1e9 (sifted)", 10 ** 9, *werner_S_Q(0.95), RKM_SIFTED),
                        ("11 km link, n = 3e6 (no-sifting)", 3_000_000, LU_2026_11KM.S, LU_2026_11KM.Q, STANDARD)):
    rows_, best = budget_split_scan(n, S, Q, v)
    P(f"**{lab}**\n\n| eps_snd/eps | n_s | 3 n_s | ell | r_sig |\n|---|---|---|---|---|")
    for r in rows_:
        P(f"| {r['fraction']} | {r['n_s']} | {r['key_bits_per_signature']} | {r['ell']:.4g} | {r['r_sig']:.4g} |{'  <- best' if r is best else ''}")
    P("")

# ------------------------------------------------------------------ where the EAT penalty sits
P("## Where the baseline's finite-size penalty sits (percent of the gross entropy n g(omega_thr))\n")
P("| point | Delta_EAT | second-order | test register n*gamma | alpha' terms | smoothing / acceptance | EC_max |\n|---|---|---|---|---|---|---|")
for lab, n, S, Q, v, pv in (("V = 0.95, n = 1e9", 10 ** 9, *werner_S_Q(0.95), RKM_SIFTED, 0.0),
                            ("V = 0.87, n = 1e9 (near threshold)", 10 ** 9, *werner_S_Q(0.87), RKM_SIFTED, 0.0),
                            ("11 km, n = 3e6", 3_000_000, LU_2026_11KM.S, LU_2026_11KM.Q, STANDARD, 0.0)):
    ell, kp, ex = maximize_key_length(n, S, Q, pv, ec_model=v.ec_model, key_weight=v.key_weight, restarts=2)
    f = penalty_breakdown(ex["terms"])["fraction of gross"]
    k2, k3 = "second Renyi order (a')", "smoothing / acceptance (1/(a-1))"
    P(f"| {lab} | {100 * f['Delta_EAT total']:.1f} | {100 * f['second-order EAT terms']:.1f} | {100 * f['test register (n gamma)']:.1f} | "
      f"{100 * f[k2]:.1f} | {100 * f[k3]:.1f} | {100 * f['EC_max']:.1f} |")
