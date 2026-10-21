import math
import numpy as np
import pytest
from diqds.finite_key import (KeyParams, MinTradeoff, SecurityBudget, W_CLASSICAL, W_MAX, ec_max, h2, key_length,
                              maximize_key_length, min_visibility, r0, r0_prime, rp, rp_prime, theta_eps, werner_S_Q)
from diqds.experiments import minimum_rounds, secret_key_length
from diqds.presets import LU_2026_11KM, NADLINGER_2022, RKM_SIFTED, STANDARD


@pytest.mark.parametrize("p", [0.0, 0.1, 0.3])
def test_derivatives_match_finite_differences(p):
    for w in (0.78, 0.82, 0.85):
        fd = (rp(w + 1e-6, p) - rp(w - 1e-6, p)) / 2e-6
        assert rp_prime(w, p) == pytest.approx(fd, rel=1e-5)


def test_noisy_preprocessing_entropy_bound_endpoints():
    assert r0(0.75) == 0.0 and rp(0.75, 0.2) == pytest.approx(h2(0.2), abs=1e-12)    # h(p) at the classical point
    assert rp(W_MAX, 0.3) == pytest.approx(1.0, abs=1e-9) and r0(W_MAX) == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("p,gamma,t", [(0.0, 0.05, 0.80), (0.1, 0.02, 0.82), (0.3, 0.2, 0.78)])
def test_tangent_is_a_valid_affine_lower_bound(p, gamma, t):
    """g_t <= eta on the quantum range above 3/4 (requires convexity of eta, Eq. B4)."""
    mt = MinTradeoff(gamma, p, t, 0.0)
    for w in np.linspace(0.7501, W_MAX - 1e-4, 300):
        eta = 0.5 * (1 - gamma) * rp(w, p) + gamma * r0(w)
        assert mt.g(w) <= eta + 1e-9


def test_theta_eps_bound():
    for e in (1e-3, 1e-11, 1e-20):
        assert theta_eps(e) <= math.log2(2 / e ** 2) + 1e-9


def _kp(**over):
    d = dict(gamma=0.05, t=0.82, alpha=1 + 1e-5, alpha_p=1 + 1e-5, beta_frac=0.1, eps_h=1e-16, x1=0.5, x2=0.4, p=0.0)
    d.update(over)
    return KeyParams(**d)


def test_constraints_are_enforced():
    S, Q = werner_S_Q(0.95)
    assert math.isfinite(key_length(10 ** 9, S, Q, _kp()))
    assert key_length(10 ** 9, S, Q, _kp(alpha=2.5)) == -math.inf
    assert key_length(10 ** 9, S, Q, _kp(alpha_p=1.5)) == -math.inf     # alpha' < 1 + 2/V'
    assert key_length(10 ** 9, S, Q, _kp(x1=0.7, x2=0.7)) == -math.inf  # eps'_s + 2 eps''_s must stay below eps_s
    assert key_length(10 ** 9, S, Q, _kp(t=0.7)) == -math.inf           # tangent point above 3/4


def test_key_length_monotone_in_n_and_visibility():
    ells = [maximize_key_length(n, *werner_S_Q(0.95), p=0.0, restarts=1)[0] for n in (10 ** 7, 10 ** 8, 10 ** 9)]
    assert ells[0] < ells[1] < ells[2] and ells[2] > 0
    vs = [maximize_key_length(10 ** 9, *werner_S_Q(V), p=0.0, restarts=1)[0] for V in (0.88, 0.92, 0.96)]
    assert vs[0] < vs[1] < vs[2]


def test_ec_models():
    # printed (B11) has no sifting factor and ignores p -> strictly more expensive than the sifted form
    assert ec_max(10 ** 8, 0.05, 2.5, 0.05, 0.0, "printed") > ec_max(10 ** 8, 0.05, 2.5, 0.05, 0.0, "sifted")
    assert ec_max(10 ** 8, 0.05, 2.5, 0.05, 0.2, "sifted") > ec_max(10 ** 8, 0.05, 2.5, 0.05, 0.0, "sifted")


# ------------------------------------------------------------------ regressions against the paper
PAPER_P0 = {10 ** 8: 0.8835, 10 ** 9: 0.8686, 10 ** 10: 0.8622}        # Fig. 5 / text, p = 0
PAPER_NP = {10 ** 8: 0.8799, 10 ** 9: 0.8608, 10 ** 10: 0.8508}        # optimised noisy preprocessing


@pytest.mark.slow
@pytest.mark.parametrize("n", list(PAPER_P0))
def test_fig5_thresholds_without_noisy_preprocessing(n):
    v = min_visibility(n, p=0.0, key_weight=0.5, ec_model="sifted", restarts=2, tol=5e-5)
    assert abs(v - PAPER_P0[n]) < 1.5e-3


@pytest.mark.slow
@pytest.mark.parametrize("n", list(PAPER_NP))
def test_fig5_thresholds_with_noisy_preprocessing(n):
    v = min_visibility(n, p=None, key_weight=0.5, ec_model="sifted", restarts=2, tol=5e-5)
    v0 = min_visibility(n, p=0.0, key_weight=0.5, ec_model="sifted", restarts=2, tol=5e-5)
    assert abs(v - PAPER_NP[n]) < 2e-3
    assert v < v0                                                    # NP lowers the tolerated noise


@pytest.mark.slow
def test_fig6_statements_for_matter_qubit_experiments():
    # Ref. [73]: its 1.5e6 rounds are enough; Ref. [75]: 1.208e6 rounds are NOT enough but ~2.4e6 are.
    assert minimum_rounds(NADLINGER_2022.S, NADLINGER_2022.Q, STANDARD) < 1.5e6
    n75 = minimum_rounds(LU_2026_11KM.S, LU_2026_11KM.Q, STANDARD)
    assert 1.208e6 < n75 <= 2.4e6
    assert secret_key_length(1_500_000, NADLINGER_2022.S, NADLINGER_2022.Q, STANDARD)[0] > 0
