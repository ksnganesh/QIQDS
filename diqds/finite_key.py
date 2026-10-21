"""
Finite-size secret-key length for the DIQKD distribution stage.

Implements Eq. (9) / (B12) of Fan et al., Phys. Rev. A 114, 032617 (2026), which is
Theorem 1 of Tan et al., Quantum 6, 880 (2022) (arXiv:2012.08714), together with the
CHSH entropy bounds of Pironio et al. (p = 0) and Ho et al., PRL 124, 230502 (noisy
preprocessing, p > 0) that the paper uses as r_0 and r_p.

Everything is plain-Python float math so it is fast enough to sit inside an optimiser.
Notation follows the paper:  n rounds, gamma test probability, omega_thr CHSH threshold,
t tangent point, alpha / alpha' Renyi parameters, beta free min-tradeoff parameter, ...
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional

import numpy as np
from scipy.optimize import minimize

LN2 = math.log(2.0)
SQRT2 = math.sqrt(2.0)

W_CLASSICAL = 0.75                      # best classical CHSH winning probability
W_MAX = (1.0 + 1.0 / SQRT2) / 2.0       # Tsirelson: (2 + sqrt2)/4 ~ 0.8536
W_MIN = (1.0 - 1.0 / SQRT2) / 2.0       # (2 - sqrt2)/4 ~ 0.1464
V_PRIME = 2.0 * math.log2(5.0)          # V' = 2 log 5  (paper, after Eq. B8)
LOG2_33 = math.log2(33.0)               # log(2 dim(S_j)^2 + 1) with dim(S_j) = 4


# --------------------------------------------------------------------------- entropies
def h2(x: float) -> float:
    """Binary Shannon entropy in bits."""
    if x <= 0.0 or x >= 1.0:
        return 0.0
    return -x * math.log2(x) - (1.0 - x) * math.log2(1.0 - x)


def _u(w: float) -> float:
    """u(w) = 16 w^2 - 16 w + 3 = (S/2)^2 - 1 with S = 8w - 4."""
    return 16.0 * w * w - 16.0 * w + 3.0


def r0(w: float) -> float:
    """Eq. (B3): CHSH-based single-basis entropy bound (Pironio et al.), p = 0."""
    u = _u(w)
    if u <= 0.0:
        return 0.0
    return 1.0 - h2(0.5 * (1.0 + math.sqrt(u)))


def rp(w: float, p: float) -> float:
    """Eq. (B2): entropy bound with noisy preprocessing (Ho et al., Eq. 9): 1 - I_p(S)."""
    base = r0(w)
    if p <= 0.0:
        return base
    v = 1.0 + p * (1.0 - p) * (64.0 * w * w - 64.0 * w + 8.0)   # = 1 - p(1-p)(8 - S^2)
    return base + h2(0.5 * (1.0 + math.sqrt(max(v, 0.0))))


def r0_prime(w: float) -> float:
    u = _u(w)
    if u <= 1e-14:
        return 16.0 / (2.0 * LN2)                      # analytic limit at w -> 3/4
    a = 0.5 * (1.0 + math.sqrt(u))
    if a >= 1.0:
        return float("inf")
    return math.log2(a / (1.0 - a)) * (32.0 * w - 16.0) / (4.0 * math.sqrt(u))


def rp_prime(w: float, p: float) -> float:
    d = r0_prime(w)
    if p <= 0.0:
        return d
    v = 1.0 + p * (1.0 - p) * (64.0 * w * w - 64.0 * w + 8.0)
    if v <= 1e-14:
        return d
    b = 0.5 * (1.0 + math.sqrt(v))
    if b >= 1.0:
        return d
    dv = p * (1.0 - p) * (128.0 * w - 64.0)
    return d + math.log2((1.0 - b) / b) * dv / (4.0 * math.sqrt(v))


# ------------------------------------------------------------------ min-tradeoff function
@dataclass(frozen=True)
class MinTradeoff:
    """Affine min-tradeoff data built from the tangent g_t of eta (Eqs. B1-B4, B6-B7).

    eta(w)  = (1-gamma)/2 * r_p(w) + gamma * r_0(w)
    g_t(w)  = eta(t) + (w - t) * eta'(t)
    """
    gamma: float
    p: float
    t: float
    beta_frac: float          # beta = g(1) - beta_frac * (g(1) - g(0)),  beta_frac in [0, 1]
    key_weight: float = 0.5   # 1/2 = sifting factor of Eq. (B1)/(28); 1.0 = no sifting factor

    @property
    def eta_t(self) -> float:
        return self.key_weight * (1 - self.gamma) * rp(self.t, self.p) + self.gamma * r0(self.t)

    @property
    def slope(self) -> float:
        return self.key_weight * (1 - self.gamma) * rp_prime(self.t, self.p) + self.gamma * r0_prime(self.t)

    def g(self, w: float) -> float:
        return self.eta_t + (w - self.t) * self.slope

    @property
    def beta(self) -> float:
        g0, g1 = self.g(0.0), self.g(1.0)
        return g1 - self.beta_frac * (g1 - g0)

    def max_f(self) -> float:                         # Eq. (B6), first line
        gam = self.gamma
        return self.g(1.0) / gam + (1.0 - 1.0 / gam) * self.beta

    def min_f(self) -> float:                         # Eq. (B6), second line
        return self.g(W_MIN)

    def var_f(self) -> float:                         # Eq. (B7)
        gam = self.gamma
        d0 = (self.beta - self.g(0.0)) ** 2
        d1 = (self.beta - self.g(1.0)) ** 2
        return (2.0 - SQRT2) / (4.0 * gam) * min(d0, d1) + (2.0 + SQRT2) / (4.0 * gam) * max(d0, d1)


def theta_eps(eps: float) -> float:
    """vartheta_eps = log2 1/(1 - sqrt(1-eps^2))  (<= log2(2/eps^2)); numerically stable form."""
    if eps <= 0.0:
        return math.inf
    return math.log2((1.0 + math.sqrt(max(1.0 - eps * eps, 0.0))) / (eps * eps))


def V_const(mt: MinTradeoff) -> float:
    return math.sqrt(mt.var_f() + 2.0) + LOG2_33


def K_alpha(alpha: float, mt: MinTradeoff) -> float:
    d = 4.0 + mt.max_f() - mt.min_f()                 # 2 log 4 + Max - Min
    ln_term = d * LN2 + math.log1p(math.e ** 2 * 2.0 ** (-d))   # ln(2^d + e^2), overflow-safe
    return math.exp((alpha - 1.0) * d * LN2) / (6.0 * (2.0 - alpha) ** 3 * LN2) * ln_term ** 3


# --------------------------------------------------------------- protocol-side parameters
def omega_expected(S: float) -> float:
    """Expected CHSH winning probability omega = (4 + S) / 8."""
    return (4.0 + S) / 8.0


def omega_threshold(n: int, gamma: float, S: float, k: float = 3.0) -> float:
    """Eq. (B10): omega_thr = 1 - q_thr/gamma,  q_thr = q + k sqrt(q(1-q)/n),  q = gamma (1 - omega)."""
    w = omega_expected(S)
    q = gamma * (1.0 - w)
    q_thr = q + k * math.sqrt(q * (1.0 - q) / n)
    return 1.0 - q_thr / gamma


def ec_max(n: int, gamma: float, S: float, Q: float, p: float = 0.0, model: str = "sifted") -> float:
    """Error-correction leakage budget EC_max (bits).

    model="sifted"  (default)  n[(1-g)/2 * h(p + (1-2p) Q) + g * h((4-S)/8)] + 50 sqrt(n)
        Only the rounds with X = Y carry key bits (sifting factor 1/2) and, after noisy
        preprocessing, their error rate is Q' = p + (1-2p) Q  (Tan et al. Eq. 26).  This is the
        reading that reproduces the paper's Fig. 5 thresholds (see scripts/reproduce_thresholds.py).
    model="printed"            Eq. (B11) verbatim: n[(1-g) h(Q) + g h((4-S)/8)] + 50 sqrt(n).
        Ignores both the sifting factor and p; combined with Eq. (B1) it contradicts the paper's own
        thresholds (V_min ~ 0.91 instead of 0.862 at n = 1e10, p = 0).
    """
    if model == "sifted":
        per_round = 0.5 * (1.0 - gamma) * h2(p + (1.0 - 2.0 * p) * Q) + gamma * h2((4.0 - S) / 8.0)
    elif model == "printed":
        per_round = (1.0 - gamma) * h2(Q) + gamma * h2((4.0 - S) / 8.0)
    elif model == "sifted_no_p":      # diagnostic only: ignores the NP flips (unphysical free lunch)
        per_round = 0.5 * (1.0 - gamma) * h2(Q) + gamma * h2((4.0 - S) / 8.0)
    else:
        raise ValueError(model)
    return n * per_round + 50.0 * math.sqrt(n)


# ------------------------------------------------------------------------- key length
@dataclass(frozen=True)
class SecurityBudget:
    """Table I values. eps_snd: DIQKD soundness; eps_ea / eps_pa: entropy-accumulation and
    privacy-amplification parameters. `hash_weight` is the multiplicity of eps_h in the soundness
    budget: Tan et al. Thm 1 gives max{eps_EA, eps_PA + 2 eps_s} + 2 eps_h  (hash_weight = 2);
    the wording in the paper (secret to +2 eps_h plus eps_h-correct) would give 3."""
    eps_snd: float = 5.0e-11
    eps_ea: float = 1.0e-11
    eps_pa: float = 1.0e-11
    hash_weight: int = 2
    eps_h: Optional[float] = 2.0 ** -61     # EC verification-hash collision prob. (paper: eps_corr <= 2^-61);
                                            # None -> optimised (it then drifts to ~1e-14, worth only a few bits)

    def eps_s(self, eps_h: float) -> float:
        """Largest smoothing parameter allowed by the soundness budget."""
        return (self.eps_snd - self.hash_weight * eps_h - self.eps_pa) / 2.0


@dataclass
class KeyParams:
    """Optimisation variables of Eq. (9)."""
    gamma: float
    t: float
    alpha: float
    alpha_p: float
    beta_frac: float
    eps_h: float
    x1: float                 # eps'_s  = x1 * eps_s
    x2: float                 # 2 eps''_s = x2 * eps_s     (x1 + x2 < 1)
    p: float = 0.0
    x3: Optional[float] = None   # eps_s - eps'_s - 2 eps''_s = x3 * eps_s  (default 1 - x1 - x2)


def key_length(n: int, S: float, Q: float, kp: KeyParams, budget: SecurityBudget = SecurityBudget(),
               ec_model: str = "sifted", k_sigma: float = 3.0, details: bool = False,
               key_weight: float = 0.5):
    """Right-hand side of Eq. (9)/(B12): upper bound on the secure key length (bits).

    Returns -inf if the parameter choice violates a constraint of Theorem 1.
    """
    g, p = kp.gamma, kp.p
    if not (0.0 < g < 1.0 and 0.0 <= p <= 0.5 and W_CLASSICAL < kp.t < W_MAX):
        return -math.inf
    if not (1.0 < kp.alpha < 2.0 and 1.0 < kp.alpha_p < 1.0 + 2.0 / V_PRIME):
        return -math.inf
    if not (0.0 <= kp.beta_frac <= 1.0 and kp.x1 > 0 and kp.x2 > 0):
        return -math.inf
    eps_s = budget.eps_s(kp.eps_h)
    if eps_s <= 0.0 or eps_s < (budget.eps_ea - budget.eps_pa) / 2.0:
        return -math.inf
    eps_s1 = kp.x1 * eps_s                       # eps'_s
    eps_s2 = 0.5 * kp.x2 * eps_s                 # eps''_s
    x3 = kp.x3 if kp.x3 is not None else 1.0 - kp.x1 - kp.x2
    eps_rest = x3 * eps_s                        # eps_s - eps'_s - 2 eps''_s  > 0
    if not (eps_rest > 0.0 and eps_s1 > 0.0 and eps_s2 > 0.0):
        return -math.inf

    mt = MinTradeoff(g, p, kp.t, kp.beta_frac, key_weight)
    w_thr = omega_threshold(n, g, S, k_sigma)
    V = V_const(mt)
    Ka = K_alpha(kp.alpha, mt)
    L_ea = math.log2(1.0 / budget.eps_ea)
    ecm = ec_max(n, g, S, Q, p, ec_model)

    terms = {
        "n g(w_thr)": n * mt.g(w_thr),
        "- n (a-1) ln2/2 V^2": -n * (kp.alpha - 1.0) * LN2 / 2.0 * V * V,
        "- n (a-1)^2 K_a": -n * (kp.alpha - 1.0) ** 2 * Ka,
        "- n gamma": -n * g,
        "- n (a'-1)/4 V'^2": -n * (kp.alpha_p - 1.0) / 4.0 * V_PRIME ** 2,
        "- th(eps's)/(a-1)": -theta_eps(eps_s1) / (kp.alpha - 1.0),
        "- th(eps''s)/(a'-1)": -theta_eps(eps_s2) / (kp.alpha_p - 1.0),
        "- (a/(a-1)+a'/(a'-1)-2) log 1/eps_EA":
            -(kp.alpha / (kp.alpha - 1.0) + kp.alpha_p / (kp.alpha_p - 1.0) - 2.0) * L_ea,
        "- 3 th(eps_s - eps's - 2eps''s)": -3.0 * theta_eps(eps_rest),
        "- EC_max": -ecm,
        "- ceil(log 1/eps_h)": -math.ceil(math.log2(1.0 / kp.eps_h)),
        "- 2 log 1/eps_PA": -2.0 * math.log2(1.0 / budget.eps_pa),
        "+ 2": 2.0,
    }
    total = sum(terms.values())
    if details:
        return total, terms, dict(omega_thr=w_thr, V=V, K_alpha=Ka, EC_max=ecm, eps_s=eps_s)
    return total


# --------------------------------------------------------------------- optimisation
def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z)) if z > -700 else 0.0


def _decode(z, p_fixed: Optional[float], n: int, beta_fixed: Optional[float] = None,
            eps_h_fixed: Optional[float] = None) -> KeyParams:
    gamma = min(max(10.0 ** z[0], 1e-8), 0.95)
    t = W_CLASSICAL + 1e-4 + (W_MAX - W_CLASSICAL - 2e-4) * _sigmoid(z[1])
    alpha = 1.0 + min(10.0 ** z[2], 1.0 - 1e-6)
    alpha_p = 1.0 + min(10.0 ** z[3], 2.0 / V_PRIME * (1.0 - 1e-6))
    beta_frac = _sigmoid(z[4]) if beta_fixed is None else beta_fixed
    e1, e2 = math.exp(max(min(z[5], 30.0), -30.0)), math.exp(max(min(z[6], 30.0), -30.0))
    tot = e1 + e2 + 1.0
    x1, x2, x3 = e1 / tot, e2 / tot, 1.0 / tot
    eps_h = eps_h_fixed if eps_h_fixed is not None else 10.0 ** min(max(z[7], -19.0), -11.7)
    p = p_fixed if p_fixed is not None else 0.5 * _sigmoid(z[8])
    return KeyParams(gamma, t, alpha, alpha_p, beta_frac, eps_h, x1, x2, p, x3)


def _initial_points(n: int, S: float, p_fixed: Optional[float]):
    w = omega_expected(S)
    t0 = min(max(w, 0.76), W_MAX - 1e-3)
    zt = math.log((t0 - W_CLASSICAL) / (W_MAX - t0))
    sq = 1.0 / math.sqrt(n)
    a0 = math.log10(max(30.0 * sq, 1e-7))
    pts = []
    for lg in (-3.0, -2.0, -1.2):
        z = [lg, zt, a0, a0, -8.0, 3.0, 3.0, -14.0]
        if p_fixed is None:
            z.append(-1.0)
        pts.append(z)
    return pts


def maximize_key_length(n: int, S: float, Q: float, p: Optional[float] = 0.0,
                        budget: SecurityBudget = SecurityBudget(), ec_model: str = "sifted",
                        k_sigma: float = 3.0, restarts: int = 3, maxiter: int = 4000,
                        key_weight: float = 0.5, z0=None, beta_frac: Optional[float] = None):
    """Numerically maximise Eq. (9) over (gamma, t, alpha, alpha', beta, eps splits, [p]).

    p = float -> noisy-preprocessing probability held fixed; p = None -> optimised as well.
    z0 -> optional warm start (the `z` returned in extras["z"] of a previous call).
    Returns (ell, KeyParams, extras); ell may be negative (= no key)."""
    def obj(z):
        kp = _decode(z, p, n, beta_frac, budget.eps_h)
        v = key_length(n, S, Q, kp, budget, ec_model, k_sigma, key_weight=key_weight)
        return -v if math.isfinite(v) else 1e30

    starts = [list(z0)] if z0 is not None else _initial_points(n, S, p)[:max(1, restarts)]
    best = (math.inf, None)
    for zs in starts:
        res = minimize(obj, zs, method="Nelder-Mead",
                       options=dict(maxiter=maxiter, xatol=1e-5, fatol=1e-6, adaptive=True))
        res = minimize(obj, res.x, method="Nelder-Mead",
                       options=dict(maxiter=maxiter, xatol=1e-7, fatol=1e-8, adaptive=True))
        if res.fun < best[0]:
            best = (res.fun, res.x)
    kp = _decode(best[1], p, n, beta_frac, budget.eps_h)
    ell, terms, extras = key_length(n, S, Q, kp, budget, ec_model, k_sigma, details=True,
                                    key_weight=key_weight)
    extras["terms"] = terms
    extras["z"] = list(best[1])
    return ell, kp, extras


def min_visibility(n: int, p: Optional[float] = 0.0, v_lo: float = 0.80, v_hi: float = 0.97,
                   tol: float = 1e-5, ell_min: float = 0.0, **kw) -> float:
    """Smallest Werner visibility V for which the optimised key length of Eq. (9) exceeds `ell_min`.
    ell_min = 0   : Fig. 5 horizontal intercepts of Fan et al. (the continuous signature rate hits zero);
    ell_min = 3 n_s: "at least one whole signature" (the definition in Sec. 3.4 of the follow-up paper).
    Bisection with warm-started optimisation."""
    z = None
    lo, hi = v_lo, v_hi
    ell_hi, _, ex = maximize_key_length(n, *werner_S_Q(hi), p, **kw)
    if ell_hi <= ell_min:
        return math.nan
    z = ex["z"]
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        ell, _, ex = maximize_key_length(n, *werner_S_Q(mid), p, z0=z, **kw)
        if ell > ell_min:
            hi, z = mid, ex["z"]
        else:
            lo = mid
    return 0.5 * (lo + hi)


# ------------------------------------------------------------ depolarizing-noise model
def werner_S_Q(V: float):
    """Paper Fig. 3: S = 2 sqrt(2) V and Q = (1 - V)/2 for the Werner state V|Phi+><Phi+| + (1-V) I/4."""
    return 2.0 * SQRT2 * V, (1.0 - V) / 2.0


def key_length_werner(n: int, V: float, p: Optional[float] = 0.0, **kw):
    S, Q = werner_S_Q(V)
    return maximize_key_length(n, S, Q, p, **kw)


# ------------------------------------------------------------ sanity limits and diagnostics
def asymptotic_visibility_threshold(p: Optional[float] = 0.0, p_grid: int = 1000) -> float:
    """n -> infinity, gamma -> 0 threshold of the single-basis entropy bound used by Fan et al.:
    the visibility V at which  max_p [ r_p(w) - h(p + (1-2p) Q) ] = 0  (the sifting factor 1/2 cancels).
    Any finite-size bound that keeps this single-round entropy (so that it recovers it as alpha -> 1) must satisfy
    V_min(n) >= this value.  p = None optimises p (p = 0 gives 0.8570; optimised p gives 0.8383)."""
    from scipy.optimize import brentq

    def rate(V, pp):
        S, Q = werner_S_Q(V)
        return rp(omega_expected(S), pp) - h2(pp + (1.0 - 2.0 * pp) * Q)

    if p is not None:
        return brentq(lambda V: rate(V, p), 0.80, 0.95, xtol=1e-10)
    grid = [0.5 * i / p_grid for i in range(p_grid)]
    return brentq(lambda V: max(rate(V, pp) for pp in grid), 0.80, 0.95, xtol=1e-9)


PENALTY_GROUPS = {
    "second-order EAT terms": ["- n (a-1) ln2/2 V^2", "- n (a-1)^2 K_a"],
    "test register (n gamma)": ["- n gamma"],
    "second Renyi order (a')": ["- n (a'-1)/4 V'^2", "- th(eps''s)/(a'-1)"],
    "smoothing / acceptance (1/(a-1))": ["- th(eps's)/(a-1)", "- (a/(a-1)+a'/(a'-1)-2) log 1/eps_EA",
                                         "- 3 th(eps_s - eps's - 2eps''s)"],
}


def penalty_breakdown(terms: dict) -> dict:
    """Group the terms of Eq. (9) that make up Delta_EAT (everything between n g(w_thr) and EC_max), as bits and as a
    fraction of n g(w_thr). `terms` is the dict returned in extras['terms'] by maximize_key_length."""
    gross = terms["n g(w_thr)"]
    out = {name: -sum(terms[k] for k in keys) for name, keys in PENALTY_GROUPS.items()}
    out["Delta_EAT total"] = sum(out.values())
    out["EC_max"] = -terms["- EC_max"]
    out["hash + PA + const"] = -(terms["- ceil(log 1/eps_h)"] + terms["- 2 log 1/eps_PA"] + terms["+ 2"])
    return {"gross entropy n g(w_thr)": gross, **out,
            "fraction of gross": {k: v / gross for k, v in out.items()}}
