"""
Distribution stage (Sec. II.A): device-independent key generation between two parties, steps 1-7.

  1  parameters  (n, gamma, omega_thr, p, EC_max)           -> plan_distribution()
  2  data acquisition (n heralded rounds, random inputs)    -> run_diqkd()
  3  sifting (X != Y key rounds overwritten by 0)
  4  noisy preprocessing (Alice flips matched key bits with probability p)
  5  error correction (Alice -> Bob, <= EC_max bits) + 2-universal hash check
  6  parameter estimation (CHSH losses in test rounds <= n gamma (1 - omega_thr))
  7  privacy amplification (Toeplitz hash to ell bits)

All random choices come from a numpy Generator that stands in for each party's trusted local randomness.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .error_correction import get_ec
from .finite_key import (KeyParams, SecurityBudget, maximize_key_length, omega_threshold, ec_max as ec_max_fn)
from .hashing import toeplitz_hash
from .messaging import KeyPool
from .presets import RKM_SIFTED, Variant
from .randomness import RandomnessLedger


# ------------------------------------------------------------------ planning
@dataclass
class DIQKDPlan:
    n: int
    variant: Variant
    S_exp: float
    Q_exp: float
    gamma: float
    p: float
    omega_thr: float
    ec_max: int
    eps_h: float
    tag_len: int
    ell: int                      # floor of the bound in Eq. (9); <= 0 means "no key at these parameters"
    budget: SecurityBudget
    key_params: KeyParams
    details: dict = field(default_factory=dict)

    def summary(self) -> str:
        return (f"n={self.n:,}  gamma={self.gamma:.4f}  p={self.p:.4f}  omega_thr={self.omega_thr:.5f}  "
                f"EC_max={self.ec_max:,}  tag={self.tag_len} bits  ->  ell={self.ell:,} secret bits "
                f"({self.ell / self.n:.4f} per round)")


def plan_distribution(n: int, S: float, Q: float, variant: Variant = RKM_SIFTED, p: Optional[float] = "auto",
                      budget: SecurityBudget = SecurityBudget(), restarts: int = 2, k_sigma: float = 3.0) -> DIQKDPlan:
    """Optimise Eq. (9) for the expected honest-device behaviour (S, Q) and freeze the protocol parameters.
    p = "auto": optimised for the random-key-basis variant, 0 for the standard variant."""
    if p == "auto":
        p = None if variant.random_key_basis else 0.0
    ell, kp, ex = maximize_key_length(n, S, Q, p, budget, variant.ec_model, k_sigma, restarts=restarts,
                                      key_weight=variant.key_weight)
    return DIQKDPlan(
        n=n, variant=variant, S_exp=S, Q_exp=Q, gamma=kp.gamma, p=kp.p, omega_thr=ex["omega_thr"],
        ec_max=int(math.ceil(ex["EC_max"])), eps_h=kp.eps_h, tag_len=int(math.ceil(math.log2(1.0 / kp.eps_h))),
        ell=int(math.floor(ell)), budget=budget, key_params=kp, details=ex)


# ------------------------------------------------------------------ execution
@dataclass
class DIQKDResult:
    accepted: bool
    reason: str
    key_alice: Optional[np.ndarray]
    key_bob: Optional[np.ndarray]
    stats: dict
    ledger: Optional[RandomnessLedger] = None


def run_diqkd(plan: DIQKDPlan, source, rng: np.random.Generator, ec: str = "cascade",
              ledger: Optional[RandomnessLedger] = None) -> DIQKDResult:
    """Execute the protocol once with the given device pair (`source.sample(X, Y, rng) -> (A, B)`).
    Every private random draw is recorded in `ledger` (a fresh one is created if none is given) and returned in
    the result, so the randomness ledger of Eq. (5) can be checked against what the run really consumes."""
    ledger = ledger if ledger is not None else RandomnessLedger()
    stats: dict = {"n": plan.n, "ell_planned": plan.ell}
    if plan.ell <= 0:
        return DIQKDResult(False, "no key: the finite-size bound (Eq. 9) is <= 0 for these parameters",
                           None, None, stats, ledger)
    n, g = plan.n, plan.gamma

    # --- 2. data acquisition (draw exactly the bits the protocol needs) --------------------------
    test = rng.random(n) < g
    ledger.biased("Bob: test flag", n, g)
    if plan.variant.random_key_basis:
        X = rng.integers(0, 2, n).astype(np.uint8)
        ledger.uniform("Alice: input X", n)
        setting = rng.integers(0, 2, n).astype(np.uint8)       # setting inside the chosen class ({0,1} or {2,3})
        ledger.uniform("Bob: setting bit", n)
        Y = (setting + 2 * test).astype(np.uint8)
    else:                                    # standard protocol: fixed key basis, no sifting loss
        n_t = int(test.sum())
        X = np.zeros(n, dtype=np.uint8)
        Y = np.zeros(n, dtype=np.uint8)
        X[test] = rng.integers(0, 2, n_t)
        ledger.uniform("Alice: input X (test rounds)", n_t)
        Y[test] = 2 + rng.integers(0, 2, n_t)
        ledger.uniform("Bob: setting bit (test rounds)", n_t)
    A, B = source.sample(X, Y, rng)

    key_round = ~test
    matched = key_round & (X == Y)
    stats.update(n_test=int(test.sum()), n_matched=int(matched.sum()),
                 qber_key=float((A[matched] != B[matched]).mean()) if matched.any() else float("nan"))

    # --- 3. sifting ------------------------------------------------------------------------
    mism = key_round & (X != Y)
    A[mism] = 0
    B[mism] = 0

    # --- 4. noisy preprocessing --------------------------------------------------------------
    if plan.p > 0:
        n_match = int(matched.sum())
        flips = (rng.random(n_match) < plan.p).astype(np.uint8)     # one flip bit per matched key round
        ledger.biased("Alice: noisy-preprocessing flip", n_match, plan.p)
        A[matched] ^= flips

    # --- 5. error correction ------------------------------------------------------------------
    R = B.copy()                                              # Bob's best local guess for A
    R[test] = B[test] ^ (X[test] * (Y[test] - 2))             # CHSH rounds: A ~ B xor X (Y-2)
    q_est = plan.p + (1 - 2 * plan.p) * plan.Q_exp
    A_tilde = np.zeros(n, dtype=np.uint8)
    n_test = int(test.sum())
    A_tilde[test] = A[test]                                   # test-round outputs are sent directly (1 bit each)
    codec = get_ec(ec)
    if ec == "oracle":
        _, leak_m, done = codec.reconcile(A[matched], R[matched], q_est, plan.ec_max - n_test, rng)
        A_tilde[matched] = A[matched]
        leak = plan.ec_max                                   # the full budget is booked
    else:
        corrected, leak_m, done = codec.reconcile(A[matched], R[matched], q_est, plan.ec_max - n_test, rng)
        A_tilde[matched] = corrected
        leak = leak_m + n_test
    stats.update(ec_leak=int(leak), ec_max=plan.ec_max, ec_method=ec)
    if not done or leak > plan.ec_max:
        return DIQKDResult(False, f"error-correction budget exhausted: reconciliation needs more than "
                                  f"EC_max = {plan.ec_max:,} bits (Bob cannot reconstruct A)", None, None, stats, ledger)

    # verification tag: 2-universal hash of A, checked by Bob against his reconstruction
    seed_h = rng.integers(0, 2, n + plan.tag_len - 1).astype(np.uint8)
    ledger.uniform("EC-verification Toeplitz seed (public)", n + plan.tag_len - 1, private=False)
    hash_ok = bool(np.array_equal(toeplitz_hash(A, seed_h, plan.tag_len),
                                  toeplitz_hash(A_tilde, seed_h, plan.tag_len)))
    stats["hash_ok"] = hash_ok

    # --- 6. parameter estimation ----------------------------------------------------------------
    won = (A_tilde[test] ^ B[test]) == (X[test] * (Y[test] - 2))
    n_loss = int((~won).sum())
    n_loss_max = n * g * (1.0 - plan.omega_thr)
    stats.update(n_loss=n_loss, n_loss_max=float(n_loss_max),
                 S_hat=8.0 * float(won.mean()) - 4.0 if n_test else float("nan"))
    if not hash_ok:
        return DIQKDResult(False, "verification hash mismatch (Bob's reconstruction differs from A)", None, None, stats, ledger)
    if n_loss > n_loss_max:
        return DIQKDResult(False, f"CHSH test failed: {n_loss:,} losses > {n_loss_max:,.0f} allowed "
                                  f"(S_hat = {stats['S_hat']:.3f})", None, None, stats, ledger)

    # --- 7. privacy amplification ------------------------------------------------------------------
    seed_pa = rng.integers(0, 2, n + plan.ell - 1).astype(np.uint8)
    ledger.uniform("privacy-amplification Toeplitz seed (public)", n + plan.ell - 1, private=False)
    key_a = toeplitz_hash(A, seed_pa, plan.ell)
    key_b = toeplitz_hash(A_tilde, seed_pa, plan.ell)
    stats["keys_equal"] = bool(np.array_equal(key_a, key_b))
    return DIQKDResult(True, "accepted", key_a, key_b, stats, ledger)


# ------------------------------------------------------------------ both links of the QDS network
def distribute_for_qds(plan_ab: DIQKDPlan, plan_ac: DIQKDPlan, source_ab, source_ac, rng,
                       n_s: int, ec: str = "cascade"):
    """Run the Alice-Bob and Alice-Charlie distributions (independent devices, Sec. II.A) and wrap the
    two keys into a one-time KeyPool for the messaging stage. Returns (res_ab, res_ac, pool_or_None)."""
    res_ab = run_diqkd(plan_ab, source_ab, rng, ec)
    res_ac = run_diqkd(plan_ac, source_ac, rng, ec)
    if not (res_ab.accepted and res_ac.accepted):
        return res_ab, res_ac, None
    # Alice's copies are key_alice; Bob / Charlie hold key_bob (equal when EC + hash succeeded)
    return res_ab, res_ac, KeyPool(res_ab.key_alice, res_ac.key_alice, n_s)
