"""
SCAFFOLD for the tightened key-length bound of the follow-up paper, Eq. (2)  --  NOT IMPLEMENTED.

        ell <= n r_alpha(omega_thr) - Delta_alpha(n, eps) - EC_max - ceil(log2 1/eps_h) - 2 log2 1/eps_PA + 2        (2)

Eq. (2) differs from the baseline Eq. (1)/(9) of Fan et al. (diqds.finite_key.key_length) ONLY in its first two
terms.  Everything else is reused unchanged from the existing package:

    reuse as is                                             where
    ------------------------------------------------------  ----------------------------------------------
    omega_thr = 1 - q_thr/gamma, k = 3                       finite_key.omega_threshold            (B10)
    EC_max (sifted reading, depends on p and gamma)          finite_key.ec_max(model="sifted")
    -ceil(log2 1/eps_h) - 2 log2 1/eps_PA + 2                finite_key.key_length (last four terms)
    failure budget eps_snd -> eps_s, n_s from Eq. (4)        finite_key.SecurityBudget, security.choose_n_s
    tau thresholds, plans, protocol run, ledger              experiments.*, diqkd.*, randomness.*

What has to be written (and nothing in this repository can supply it):

1. r_alpha(omega_thr; alpha, gamma, p)  --  the single-round Renyi rate from the convex program of Arqand, Hahn & Tan,
   PRX 15, 041013 (2025).  As described in Sec. 2.2 of the paper:

       r_alpha = min over [ statistics q with omega(q) >= omega_thr ],  [ states and measurements with statistics nu ]  of
                 H^up_{1/(2-alpha)}( A | X Y E )  +  (2-alpha)/(alpha-1) * D(q || nu)

   with the same protocol weights as Eq. (B1) (key rounds (1-gamma)/2, test rounds gamma, noisy preprocessing p).
   For the CHSH test the test statistic is one number (the winning probability), so
   D(q || nu) = gamma * D_bin(omega_q || omega_nu) and the outer minimisation is one-dimensional.
   The inner object g_{1/(2-alpha)}(omega) -- the smallest Renyi entropy of that order compatible with CHSH winning
   probability omega -- is what needs the numerical machinery (NPA/BFF-type SDP or an exact qubit-reduction).

2. Delta_alpha(n, eps) = alpha/(alpha-1) log2(1/eps_EA) + vartheta(eps_s)/(alpha-1) + chain-rule cost,
   where the chain-rule cost replaces  n*gamma + the max-entropy (alpha') terms  of Delta_EAT. Use the exact
   expression from the GREAT theorem you rely on; finite_key.theta_eps already provides vartheta.

3. An optimiser: the variables shrink from the baseline's
       (gamma, t, alpha, alpha', beta, eps'_s/eps''_s split, eps_h, p)   to   (alpha, gamma, p, smoothing split, eps_h)
   because there is no tangent point t, no beta and no second Renyi order.  Copy finite_key._decode /
   maximize_key_length (Nelder-Mead on an unconstrained transform with warm starts) and min_visibility (bisection).

Acceptance tests the finished module has to pass (all computable with the existing code):
   (a) alpha -> 1 and n -> infinity must recover the asymptotic threshold of the single-round entropy it uses:
       finite_key.asymptotic_visibility_threshold -> 0.8570 (p = 0), 0.8383 (optimised p) for the single-basis bound
       of the baseline; a lower asymptote means r_alpha uses the true random-key-basis entropy, and then part of the
       gain over the baseline is NOT finite-size (compare against Tan et al.'s numerical RKM tradeoff as well).
   (b) r_alpha <= von Neumann rate for every alpha > 1, increasing to it as alpha -> 1.
   (c) V_min(n) decreases with n, stays above that asymptote, and its gap to the baseline closes as n grows.
   (d) With an AFFINE tradeoff plugged into the same code it must reproduce the baseline thresholds
       (0.8827 / 0.8681 / 0.8619 for p = 0 at n = 1e8 / 1e9 / 1e10 with the sifted reading).
   (e) Table 2 of the paper: 0.8719 / 0.8637 / 0.8600 (p = 0) and 0.8646 / 0.8526 / 0.8462 (optimised p).
"""
from __future__ import annotations


def single_round_rate(omega_thr: float, alpha: float, gamma: float, p: float, key_weight: float = 0.5) -> float:
    """r_alpha(omega_thr): the convex program of Eq. (2). TO BE IMPLEMENTED."""
    raise NotImplementedError("r_alpha needs the Renyi-accumulation convex program (see module docstring)")


def penalty(n: int, alpha: float, eps_ea: float, eps_s: float, gamma: float) -> float:
    """Delta_alpha(n, eps) of Eq. (2). TO BE IMPLEMENTED."""
    raise NotImplementedError("Delta_alpha needs the chain-rule cost of the generalized Renyi accumulation theorem")


def key_length(n: int, S: float, Q: float, **kw) -> float:
    """Eq. (2). TO BE IMPLEMENTED."""
    raise NotImplementedError("see module docstring")


def min_visibility(n: int, p=0.0, ell_min: float = 0.0, **kw) -> float:
    """Smallest visibility with ell > ell_min under Eq. (2): copy finite_key.min_visibility once key_length exists."""
    raise NotImplementedError("see module docstring")
