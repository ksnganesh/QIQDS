"""
Qiskit models of the honest DIQKD devices (Sec. IV of the paper).

Honest source: the two-qubit Werner state  rho_V = V |Phi+><Phi+| + (1 - V) I/4.
Measurements (the paper's choice for the depolarizing-noise scenario):
    Alice  X = 0 : Z                    X = 1 : X
    Bob    Y = 0 : Z   (= Alice's X=0)  Y = 1 : X   (= Alice's X=1)     <- key-generation inputs
           Y = 2 : (Z + X)/sqrt2        Y = 3 : (Z - X)/sqrt2           <- CHSH-test inputs
CHSH game: win iff A xor B = X * (Y - 2).  For rho_V:  S = 2 sqrt2 V,  QBER Q = (1 - V)/2.

Two interchangeable back ends:
  "exact" : rho_V evolved with qiskit.quantum_info.DensityMatrix, outcomes sampled from the exact
            joint distribution (fast; used for the large-n runs).
  "aer"   : actual circuits (H, CX, Ry, measure) run on qiskit_aer.AerSimulator with a two-qubit
            depolarizing error attached to the CX that creates the Bell pair, which yields exactly rho_V.
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Optional

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import DensityMatrix

# measurement axis angle theta: observable cos(theta) Z + sin(theta) X
THETA_ALICE = {0: 0.0, 1: math.pi / 2}
THETA_BOB = {0: 0.0, 1: math.pi / 2, 2: math.pi / 4, 3: -math.pi / 4}


# ------------------------------------------------------------------ circuits
def bell_pair_circuit() -> QuantumCircuit:
    qc = QuantumCircuit(2, name="bell")
    qc.h(0)
    qc.cx(0, 1)
    return qc


def round_circuit(x: int, y: int, measure: bool = True) -> QuantumCircuit:
    """One protocol round: Bell pair, local basis rotations for (X=x, Y=y), computational-basis readout.
    Qubit 0 = Alice's device, qubit 1 = Bob's device; classical bit 0 = A, bit 1 = B."""
    qc = QuantumCircuit(2, 2 if measure else 0, name=f"round_x{x}_y{y}")
    qc.compose(bell_pair_circuit(), inplace=True)
    qc.ry(-THETA_ALICE[x], 0)      # Ry(-theta)^dag Z Ry(-theta) = cos(theta) Z + sin(theta) X
    qc.ry(-THETA_BOB[y], 1)
    if measure:
        qc.measure([0, 1], [0, 1])
    return qc


def werner_state(V: float) -> DensityMatrix:
    """rho_V = V |Phi+><Phi+| + (1-V) I/4  as a Qiskit DensityMatrix."""
    psi = np.array([1, 0, 0, 1], dtype=complex) / math.sqrt(2)
    return DensityMatrix(V * np.outer(psi, psi.conj()) + (1.0 - V) * np.eye(4) / 4.0)


@lru_cache(maxsize=None)
def exact_joint_probabilities(V: float, x: int, y: int) -> tuple:
    """P[a][b] = Pr(A=a, B=b | X=x, Y=y) for the Werner state, via qiskit.quantum_info."""
    rot = QuantumCircuit(2)
    rot.ry(-THETA_ALICE[x], 0)
    rot.ry(-THETA_BOB[y], 1)
    p = np.clip(werner_state(V).evolve(rot).probabilities(), 0.0, None)   # index = a + 2 b
    p = p / p.sum()
    return ((p[0], p[2]), (p[1], p[3]))


def aer_backend(V: float):
    """AerSimulator whose CX carries a 2-qubit depolarizing error of strength 1-V."""
    from qiskit_aer import AerSimulator
    from qiskit_aer.noise import NoiseModel, depolarizing_error
    nm = NoiseModel()
    nm.add_quantum_error(depolarizing_error(1.0 - V, 2), ["cx"], [0, 1])
    return AerSimulator(noise_model=nm)


# ------------------------------------------------------------------ sources
class CHSHSource:
    """Honest device pair (Werner state + the CHSH measurements above)."""

    def __init__(self, V: float, backend: str = "exact"):
        if not 0.0 <= V <= 1.0:
            raise ValueError("visibility must lie in [0, 1]")
        if backend not in ("exact", "aer"):
            raise ValueError(backend)
        self.V, self.backend = V, backend
        self._sim = aer_backend(V) if backend == "aer" else None

    # expectations
    @property
    def S(self) -> float:
        return 2.0 * math.sqrt(2.0) * self.V

    @property
    def Q(self) -> float:
        return (1.0 - self.V) / 2.0

    def sample(self, X: np.ndarray, Y: np.ndarray, rng: np.random.Generator):
        """Outcomes (A, B) for all rounds. Rounds with equal (x, y) are i.i.d., so they are
        grouped: one batch per setting pair (8 circuits in total); reproducible through `rng`."""
        A = np.zeros(len(X), dtype=np.uint8)
        B = np.zeros(len(X), dtype=np.uint8)
        for x in (0, 1):
            for y in (0, 1, 2, 3):
                idx = np.nonzero((X == x) & (Y == y))[0]
                if len(idx) == 0:
                    continue
                if self.backend == "exact":
                    P = np.array(exact_joint_probabilities(self.V, x, y)).reshape(-1)   # (a,b) row-major
                    outcome = rng.choice(4, size=len(idx), p=P)
                    A[idx], B[idx] = outcome // 2, outcome % 2
                else:
                    qc = transpile(round_circuit(x, y), self._sim)
                    # independent simulator seed per setting pair (a shared seed would reuse the same random
                    # stream in every group and correlate the four CHSH correlators)
                    seed = int(rng.integers(0, 2 ** 31 - 1))
                    counts = self._sim.run(qc, shots=len(idx), seed_simulator=seed).result().get_counts()
                    pairs = []
                    for bitstring, c in counts.items():          # 'b a' (classical bit 1 leftmost)
                        pairs += [(int(bitstring[-1]), int(bitstring[-2]))] * c
                    pairs = np.array(pairs, dtype=np.uint8)
                    pairs = pairs[rng.permutation(len(pairs))]
                    A[idx], B[idx] = pairs[:, 0], pairs[:, 1]
        return A, B


class ClassicalSource:
    """Best local-deterministic strategy (a = b = 0 always): wins the CHSH game with probability 3/4.
    Models a dishonest device pair that has no entanglement; the parameter-estimation step must abort."""

    S = 2.0
    Q = 0.0

    def sample(self, X, Y, rng):
        z = np.zeros(len(X), dtype=np.uint8)
        return z, z.copy()


# ------------------------------------------------------------------ statistics
def chsh_statistics(X, Y, A, B):
    """Empirical CHSH winning probability and S = 8 w - 4 from the test rounds (Y in {2,3})."""
    t = (Y >= 2)
    won = ((A[t] ^ B[t]) == (X[t] * (Y[t] - 2)))
    w = float(won.mean()) if t.any() else float("nan")
    return w, 8.0 * w - 4.0


def key_qber(X, Y, A, B):
    """Error rate among matched key rounds (Y in {0,1}, X == Y), before noisy preprocessing."""
    m = (Y < 2) & (X == Y)
    return float((A[m] != B[m]).mean()) if m.any() else float("nan")
