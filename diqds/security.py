"""
Composable-security bookkeeping of the QDS protocol: Eqs. (4)-(8) of the paper, plus the choice
of the per-component key length n_s from the target security parameter.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class QDSParams:
    """Table I of the paper (defaults)."""
    eps: float = 1.0e-10        # target total security parameter  epsilon
    eps_snd: float = 5.0e-11    # soundness of the underlying DIQKD (bounds eps_sec in Eq. 5)
    n_m: int = 1000             # message length (bits)
    eps_cl: float = 1.0e-11     # prob. of error in classical message transmission (eps' in Eqs. 6-7)
    eps_corr: float = 2.0 ** -61  # key-disagreement probability after distribution (VHASH, Ref. [73])


def eps_forgery(n_s: int, n_m: int, eps_sec: float) -> float:
    """Eq. (5): eps_for = 2^(-n_s + 1) n_m + eps_sec."""
    return 2.0 ** (-n_s + 1) * n_m + eps_sec


def eps_repudiation(eps_cl: float) -> float:
    """Eq. (6): eps_rep = 2 eps'."""
    return 2.0 * eps_cl


def eps_robustness(eps_corr: float, eps_cl: float) -> float:
    """Eq. (7): eps_rob = 2 eps_corr + 2 eps'."""
    return 2.0 * eps_corr + 2.0 * eps_cl


def eps_total(n_s: int, prm: QDSParams = QDSParams()) -> float:
    """Eq. (8): eps = max{eps_rob, eps_rep, eps_for}."""
    return max(eps_robustness(prm.eps_corr, prm.eps_cl),
               eps_repudiation(prm.eps_cl),
               eps_forgery(n_s, prm.n_m, prm.eps_snd))


def choose_n_s(prm: QDSParams = QDSParams()) -> int:
    """Smallest n_s with 2^(-n_s+1) n_m + eps_snd <= eps  (Table I gives n_s = 46)."""
    budget = prm.eps - prm.eps_snd
    if budget <= 0:
        raise ValueError("eps must exceed eps_snd")
    return math.ceil(1.0 + math.log2(prm.n_m / budget))


def signature_rate(ell: float, n_s: int) -> float:
    """Eq. (4): r_sig = ell / (3 n_s) = signatures per protocol execution (real-valued)."""
    return max(ell, 0.0) / (3.0 * n_s)


def num_signatures(ell: int, n_s: int) -> int:
    """Whole signatures that fit into ell key bits (each consumes 3 n_s bits per link)."""
    return max(ell, 0) // (3 * n_s)
