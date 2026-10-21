"""
Signature rates and feasibility analysis (Secs. III-IV): Eq. (4) on top of the finite-size key length of Eq. (9).
"""
from __future__ import annotations

import math
from typing import Optional

from .finite_key import SecurityBudget, maximize_key_length, werner_S_Q
from .presets import RKM_SIFTED, STANDARD, Experiment, Variant
from .security import QDSParams, choose_n_s, signature_rate


def _p_for(variant: Variant, p):
    if p == "auto":
        return None if variant.random_key_basis else 0.0
    return p


def secret_key_length(n: int, S: float, Q: float, variant: Variant = RKM_SIFTED, p="auto",
                      budget: SecurityBudget = SecurityBudget(), restarts: int = 2, z0=None):
    """(ell, KeyParams, extras) of Eq. (9), optimised over the free parameters."""
    return maximize_key_length(n, S, Q, _p_for(variant, p), budget, variant.ec_model,
                               restarts=restarts, key_weight=variant.key_weight, z0=z0)


def signature_rate_for(n: int, S: float, Q: float, variant: Variant = RKM_SIFTED, p="auto",
                       qds: QDSParams = QDSParams(), restarts: int = 2) -> dict:
    """Signature rate r_sig = ell / (3 n_s) of Eq. (4) for honest devices described by (S, Q)."""
    budget = SecurityBudget(eps_snd=qds.eps_snd)
    ell, kp, ex = secret_key_length(n, S, Q, variant, p, budget, restarts)
    n_s = choose_n_s(qds)
    return dict(n=n, ell=float(ell), n_s=n_s, r_sig=float(signature_rate(ell, n_s)), gamma=float(kp.gamma),
                p=float(kp.p), t=float(kp.t), omega_thr=float(ex["omega_thr"]), ec_max=float(ex["EC_max"]))


def signature_rate_werner(n: int, V: float, variant: Variant = RKM_SIFTED, p="auto", **kw) -> dict:
    S, Q = werner_S_Q(V)
    return signature_rate_for(n, S, Q, variant, p, **kw)


def minimum_rounds(S: float, Q: float, variant: Variant = STANDARD, p="auto", lo: float = 3e4, hi: float = 5e10,
                   ratio: float = 1.02, budget: SecurityBudget = SecurityBudget(), ell_min: float = 0.0) -> float:
    """Smallest number of rounds n (to within `ratio`) for which the finite-size key of Eq. (9) exceeds `ell_min`
    (0: Fan et al.'s 'positive rate'; 3 n_s: at least one whole signature); nan if even `hi` rounds do not suffice."""
    ell, _, ex = secret_key_length(int(hi), S, Q, variant, p, budget)
    if ell <= ell_min:
        return math.nan
    z = ex["z"]
    while hi / lo > ratio:
        mid = math.sqrt(lo * hi)
        ell, _, ex = secret_key_length(int(mid), S, Q, variant, p, budget, z0=z)
        if ell > ell_min:
            hi, z = mid, ex["z"]
        else:
            lo = mid
    return hi


def experiment_report(exp: Experiment, variant: Optional[Variant] = None, p="auto") -> dict:
    """Fig. 6-style feasibility statement for a published experiment."""
    v = variant or exp.variant
    n_min = minimum_rounds(exp.S, exp.Q, v, p)
    ell_actual, _, _ = secret_key_length(int(exp.rounds), exp.S, exp.Q, v, p)
    return dict(name=exp.name, variant=v.name, n_min=n_min, hours_needed=n_min / exp.rate_per_hour,
                rounds_collected=exp.rounds, hours_collected=exp.hours, ell_at_collected=ell_actual,
                feasible_with_collected=bool(ell_actual > 0))


def scaled_budget(eps_snd: float, like: SecurityBudget = SecurityBudget()) -> SecurityBudget:
    """Budget with the same proportions as Table I (eps_EA = eps_PA = eps_snd / 5), so that the DIQKD soundness
    eps_snd can be moved between the key layer and the hashing layer without making the key budget infeasible."""
    return SecurityBudget(eps_snd=eps_snd, eps_ea=0.2 * eps_snd, eps_pa=0.2 * eps_snd,
                          hash_weight=like.hash_weight, eps_h=like.eps_h)


def budget_split_scan(n: int, S: float, Q: float, variant: Variant = RKM_SIFTED, p="auto",
                      qds: QDSParams = QDSParams(), fractions=(0.01, 0.1, 0.3, 0.5, 0.7, 0.9, 0.99), restarts: int = 2):
    """Move the total failure budget eps between the key layer (eps_snd = x eps) and the hashing layer
    (eps - eps_snd): n_s follows from Eq. (4), ell from Eq. (9). Returns one row per split, plus the best one.
    The key layer sees eps_snd through logarithms multiplied by ~1/(alpha-1), the signature layer only through n_s."""
    rows = []
    for x in fractions:
        q = QDSParams(eps=qds.eps, eps_snd=x * qds.eps, n_m=qds.n_m, eps_cl=qds.eps_cl, eps_corr=qds.eps_corr)
        n_s = choose_n_s(q)
        ell, kp, _ = secret_key_length(n, S, Q, variant, p, scaled_budget(q.eps_snd), restarts)
        rows.append(dict(fraction=x, eps_snd=q.eps_snd, n_s=n_s, key_bits_per_signature=3 * n_s, ell=float(ell),
                         r_sig=float(signature_rate(ell, n_s)), p=float(kp.p)))
    best = max(rows, key=lambda r: r["r_sig"])
    return rows, best
