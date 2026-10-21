import math
import numpy as np
import pytest
from diqds.diqkd import plan_distribution, run_diqkd
from diqds.experiments import budget_split_scan, minimum_rounds, scaled_budget, secret_key_length
from diqds.finite_key import (SecurityBudget, asymptotic_visibility_threshold, maximize_key_length, penalty_breakdown,
                              werner_S_Q)
from diqds.presets import LU_2026_11KM, RKM_SIFTED, STANDARD
from diqds.quantum import CHSHSource, ClassicalSource
from diqds.randomness import (RandomnessLedger, demand, entropy_per_party, entropy_per_round, sampler_bits_per_round,
                              seed_bits, supply_check)
from diqds.security import QDSParams, choose_n_s

LOOSE = SecurityBudget(eps_snd=1e-3, eps_ea=1e-4, eps_pa=1e-4)
V = 0.99
S, Q = 2 * math.sqrt(2) * V, (1 - V) / 2


# ----------------------------------------------------------------------- Eq. (5) and Table 3
@pytest.mark.parametrize("gamma,row", [(0.01, (2.08, 2.22, 2.31, 25.9)), (0.05, (2.29, 2.42, 2.51, 25.6)),
                                       (0.10, (2.47, 2.60, 2.68, 25.2)), (0.30, (2.88, 2.98, 3.05, 23.6))])
def test_table3_of_the_paper(gamma, row):
    got = (entropy_per_round(gamma, 0.0), entropy_per_round(gamma, 0.05), entropy_per_round(gamma, 0.10),
           sampler_bits_per_round(gamma, 0.05, 16))
    assert [round(x, 2 if i < 3 else 1) for i, x in enumerate(got)] == list(row)


def test_party_split_and_totals_quoted_in_section_3_3():
    a, b = entropy_per_party(0.10, 0.05)
    assert (round(a, 2), round(b, 2)) == (1.13, 1.47) and a + b == pytest.approx(entropy_per_round(0.10, 0.05))
    d_ion = demand(1.5e6, 0.10, 0.05, 138, events_per_second=1.5e6 / (8 * 3600))
    d_11 = demand(2.4e6, 0.10, 0.05, 138, events_per_second=1.208e6 / (624 * 3600))
    assert d_ion.total_bits / 1e6 == pytest.approx(3.9, abs=0.05) and d_ion.bits_per_key_bit == pytest.approx(2.8e4, rel=0.02)
    assert d_11.total_bits / 1e6 == pytest.approx(6.2, abs=0.05) and d_11.bits_per_key_bit == pytest.approx(4.5e4, rel=0.02)
    assert d_11.bits_per_second == pytest.approx(1.4, abs=0.05) and d_ion.bits_per_second == pytest.approx(135, abs=1)
    # the same ledger at the *tightened* 11 km operating point of the paper (1.04e6 rounds)
    assert demand(1.04e6, 0.10, 0.05, 138).bits_per_key_bit == pytest.approx(1.96e4, rel=0.02)


def test_min_entropy_and_supply_check():
    assert demand(1e6, 0.1, 0.05, 138, kappa=0.5).total_bits == pytest.approx(2 * demand(1e6, 0.1, 0.05, 138).total_bits)
    ok = supply_check(0.1, 0.05, events_per_second=0.538, generator_bits_per_second=100.0)
    assert ok["ok"] and ok["required_bps"] == pytest.approx(1.4, abs=0.05)
    assert not supply_check(0.1, 0.05, 75e6 * 1e-3, generator_bits_per_second=1e4)["ok"]    # photonic link needs ~0.2 Mbit/s


def test_toeplitz_seeds_add_about_one_bit_per_round_each():
    s = seed_bits(10 ** 6, 10 ** 5, 61)
    assert len(s) == 2 and all(abs(v / 1e6 - 1) < 0.2 for v in s.values())


# ----------------------------------------------------------------------- instrumentation of the real protocol
@pytest.mark.parametrize("variant", [RKM_SIFTED, STANDARD])
def test_ledger_of_a_real_run_matches_eq5(variant):
    n = 800_000 if variant is RKM_SIFTED else 300_000
    plan = plan_distribution(n, S, Q, variant, budget=LOOSE)
    res = run_diqkd(plan, CHSHSource(V), np.random.default_rng(3))
    assert res.accepted and res.ledger is not None
    per_round = res.ledger.per_round(n)                                # private entropy only (seeds are public)
    assert per_round == pytest.approx(entropy_per_round(plan.gamma, plan.p, variant.random_key_basis), rel=0.02)
    assert res.ledger.per_round(n, r=16) == pytest.approx(
        sampler_bits_per_round(plan.gamma, plan.p, 16, variant.random_key_basis), rel=0.02)
    seeds = {k: e.draws for k, e in res.ledger.entries.items() if not e.private}
    assert seeds["privacy-amplification Toeplitz seed (public)"] == n + plan.ell - 1
    assert "Alice: input X" in res.ledger.summary() or "Alice: input X (test rounds)" in res.ledger.summary()


def test_aborted_run_only_counts_what_it_drew():
    plan = plan_distribution(800_000, S, Q, RKM_SIFTED, budget=LOOSE)
    res = run_diqkd(plan, ClassicalSource(), np.random.default_rng(4))
    assert not res.accepted
    assert "privacy-amplification Toeplitz seed (public)" not in res.ledger.entries   # no key, no PA seed drawn


# ----------------------------------------------------------------------- budget layer (Eq. 3-4, Sec. 3.2)
def test_section_3_2_signature_lengths():
    ns = lambda es, nm=1000: choose_n_s(QDSParams(eps=1e-10, eps_snd=es, n_m=nm))
    assert [ns(e) for e in (1e-11, 5e-11, 9e-11, 9.9e-11)] == [45, 46, 48, 51]
    assert ns(5e-11, 10 ** 6) == 56
    assert [3 * ns(e) for e in (1e-11, 9.9e-11)] == [135, 153]


@pytest.mark.slow
def test_budget_split_scan_structure():
    rows, best = budget_split_scan(10 ** 9, *werner_S_Q(0.95), RKM_SIFTED, p=0.0, fractions=(0.1, 0.5, 0.9))
    assert [r["n_s"] for r in rows] == sorted(r["n_s"] for r in rows)          # n_s grows with eps_snd
    assert all(r["r_sig"] > 0 for r in rows) and best["r_sig"] == max(r["r_sig"] for r in rows)
    b = scaled_budget(5e-11)
    assert (b.eps_ea, b.eps_pa) == (pytest.approx(1e-11), pytest.approx(1e-11))   # reproduces Table I proportions


# ----------------------------------------------------------------------- thresholds, definitions, limits
@pytest.mark.slow
def test_ell_min_definition_changes_threshold_slightly():
    n0 = minimum_rounds(LU_2026_11KM.S, LU_2026_11KM.Q, STANDARD, ratio=1.0002)
    n1 = minimum_rounds(LU_2026_11KM.S, LU_2026_11KM.Q, STANDARD, ratio=1.0002, ell_min=138)
    assert n0 < n1 < 1.01 * n0          # requiring a whole signature (138 bits) moves the threshold by well under 1 %


def test_asymptotic_threshold_limits():
    assert asymptotic_visibility_threshold(0.0) == pytest.approx(0.8570, abs=2e-4)
    assert asymptotic_visibility_threshold(None) == pytest.approx(0.8383, abs=2e-3)
    assert asymptotic_visibility_threshold(None) < asymptotic_visibility_threshold(0.05) < asymptotic_visibility_threshold(0.0)


def test_penalty_breakdown_adds_up():
    ell, kp, ex = maximize_key_length(10 ** 9, *werner_S_Q(0.95), p=0.0, restarts=1)
    pb = penalty_breakdown(ex["terms"])
    total = pb["gross entropy n g(w_thr)"] - pb["Delta_EAT total"] - pb["EC_max"] - pb["hash + PA + const"]
    assert total == pytest.approx(ell, rel=1e-9)
