import math
import numpy as np
import pytest
from diqds.quantum import (CHSHSource, ClassicalSource, chsh_statistics, exact_joint_probabilities, key_qber,
                           round_circuit)


@pytest.mark.parametrize("V", [1.0, 0.95, 0.9, 0.85])
def test_exact_werner_statistics(V):
    S = 0.0
    for x in (0, 1):
        for y in (2, 3):
            P = np.array(exact_joint_probabilities(V, x, y))
            S += (P[0, 0] + P[1, 1] - P[0, 1] - P[1, 0]) * (-1 if (x, y) == (1, 3) else 1)
    assert S == pytest.approx(2 * math.sqrt(2) * V, abs=1e-9)
    for k in (0, 1):                                     # key settings: Y = X = k
        P = np.array(exact_joint_probabilities(V, k, k))
        assert P[0, 1] + P[1, 0] == pytest.approx((1 - V) / 2, abs=1e-9)


def test_round_circuit_structure():
    qc = round_circuit(1, 3)
    names = [i.operation.name for i in qc.data]
    assert names.count("cx") == 1 and names.count("measure") == 2


def _inputs(n, gamma, rng):
    X = rng.integers(0, 2, n).astype(np.uint8)
    T = rng.random(n) < gamma
    Y = np.where(T, 2 + rng.integers(0, 2, n), rng.integers(0, 2, n)).astype(np.uint8)
    return X, Y


@pytest.mark.parametrize("backend", ["exact", "aer"])
def test_sampled_statistics_match_theory(backend):
    rng = np.random.default_rng(10)
    V, n = 0.93, 300_000
    X, Y = _inputs(n, 0.3, rng)
    src = CHSHSource(V, backend)
    A, B = src.sample(X, Y, rng)
    w, S = chsh_statistics(X, Y, A, B)
    n_test = (Y >= 2).sum()
    sigma_S = 8 * math.sqrt(w * (1 - w) / n_test)
    assert abs(S - src.S) < 4.5 * sigma_S
    n_match = ((Y < 2) & (X == Y)).sum()
    sigma_Q = math.sqrt(src.Q * (1 - src.Q) / n_match)
    assert abs(key_qber(X, Y, A, B) - src.Q) < 4.5 * sigma_Q


def test_classical_source_cannot_beat_2():
    rng = np.random.default_rng(11)
    X, Y = _inputs(200_000, 0.3, rng)
    _, S = chsh_statistics(X, Y, *ClassicalSource().sample(X, Y, rng))
    assert S == pytest.approx(2.0, abs=0.05)
