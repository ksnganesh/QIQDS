import numpy as np
import pytest
from diqds.diqkd import distribute_for_qds, plan_distribution, run_diqkd
from diqds.finite_key import SecurityBudget
from diqds.messaging import encode_document, run_session
from diqds.presets import RKM_SIFTED, STANDARD
from diqds.quantum import CHSHSource, ClassicalSource
from diqds.security import choose_n_s

LOOSE = SecurityBudget(eps_snd=1e-3, eps_ea=1e-4, eps_pa=1e-4)     # small budget -> small n suffices (tests only)
V = 0.99
S, Q = 2 * np.sqrt(2) * V, (1 - V) / 2


@pytest.fixture(scope="module")
def plan_rkm():
    return plan_distribution(800_000, S, Q, RKM_SIFTED, budget=LOOSE)


def test_plan_has_positive_key(plan_rkm):
    assert plan_rkm.ell > 1000 and 0 < plan_rkm.gamma < 0.5 and plan_rkm.omega_thr > 0.75
    assert plan_rkm.tag_len >= 30


@pytest.mark.parametrize("ec", ["cascade", "oracle"])
def test_honest_run_gives_identical_keys(plan_rkm, ec):
    rng = np.random.default_rng(1)
    res = run_diqkd(plan_rkm, CHSHSource(V, "exact"), rng, ec=ec)
    assert res.accepted, res.reason
    assert len(res.key_alice) == plan_rkm.ell and np.array_equal(res.key_alice, res.key_bob)
    assert res.stats["ec_leak"] <= plan_rkm.ec_max and res.stats["hash_ok"]
    assert abs(res.key_alice.mean() - 0.5) < 0.03                     # sanity: key bits look uniform


def test_unentangled_devices_are_rejected(plan_rkm):
    res = run_diqkd(plan_rkm, ClassicalSource(), np.random.default_rng(2))
    assert not res.accepted and "CHSH" in res.reason


def test_too_noisy_devices_are_rejected(plan_rkm):
    res = run_diqkd(plan_rkm, CHSHSource(0.93, "exact"), np.random.default_rng(3))
    assert not res.accepted


def test_standard_variant_has_no_sifting_loss():
    plan = plan_distribution(300_000, S, Q, STANDARD, budget=LOOSE)
    assert plan.p == 0.0 and plan.ell > 0
    res = run_diqkd(plan, CHSHSource(V, "exact"), np.random.default_rng(4))
    assert res.accepted and np.array_equal(res.key_alice, res.key_bob)
    assert res.stats["n_matched"] == plan.n - res.stats["n_test"]      # every key round is usable


def test_aer_circuit_backend_end_to_end(plan_rkm):
    res = run_diqkd(plan_rkm, CHSHSource(V, "aer"), np.random.default_rng(5))
    assert res.accepted and np.array_equal(res.key_alice, res.key_bob)


def test_distribution_feeds_signature_stage(plan_rkm):
    rng = np.random.default_rng(6)
    n_s = choose_n_s()
    ab, ac, pool = distribute_for_qds(plan_rkm, plan_rkm, CHSHSource(V), CHSHSource(V), rng, n_s)
    assert pool is not None and pool.capacity >= 5
    A, B, C = pool.next_keys()
    b, c, _ = run_session(A, B, C, encode_document(b"signed with device-independent keys", 1000))
    assert b and c
