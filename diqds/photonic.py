"""
Appendix C / D helpers: quantum-dot single-photon source imperfections, the heralded polarization-entangled
state of the all-photonic architecture, and the channel model.

What is and is NOT here.  Implemented from the paper: Eqs. (C7), (C8), (C13), (D1), (D2), (D3) and the
"370 hours" bookkeeping.  NOT reproducible from the paper alone: the heralding probability P_H and the
map from (V_HOM, g2, eta_l, T, t) to the heralded two-qubit state, which the paper takes from
Kolodynski et al. (Quantum 4, 260), Gonzalez-Ruiz et al. (PRA 106, 012222; Opt. Express 32, 13181);
hence Fig. 7 is not reproduced here.  `heralded_rounds` therefore takes P_H as an input.
"""
from __future__ import annotations

import math

import numpy as np
from qiskit.quantum_info import DensityMatrix, Statevector
from scipy.special import erfcx

_PAULI = [np.array([[0, 1], [1, 0]], dtype=complex),
          np.array([[0, -1j], [1j, 0]], dtype=complex),
          np.array([[1, 0], [0, -1]], dtype=complex)]


# ------------------------------------------------------------------ source model (App. C)
def hom_visibility_local(gamma: float, gamma_d: float) -> float:
    """Eq. (C7): V_alpha^(0) = gamma / (gamma + 2 gamma_d)  (photons from the same quantum dot)."""
    return gamma / (gamma + 2.0 * gamma_d)


def hom_visibility_remote(gamma: float, gamma_d: float, sigma: float) -> float:
    """Eq. (C8): visibility of photons from different dots whose detuning is Gaussian with std sigma:
        V_beta^(0) = sqrt(pi/2) (gamma/sigma) exp(G^2/2 sigma^2) erfc(G/(sqrt2 sigma)),  G = gamma + 2 gamma_d.
    (The extracted PDF text shows 'pi/2'; sqrt(pi/2) is what makes sigma -> 0 recover gamma/G = Eq. C7.)
    exp(x^2) erfc(x) is evaluated as the overflow-safe scaled function erfcx(x)."""
    G = gamma + 2.0 * gamma_d
    return math.sqrt(math.pi / 2.0) * (gamma / sigma) * float(erfcx(G / (math.sqrt(2.0) * sigma)))


def multiphoton_corrected_visibility(v0: float, g2: float, kappa: float = 2.0) -> float:
    """Eq. (C13): V = V0 - kappa g2 with 1 < kappa < 3 (kappa depends on the distinguishability of the 1- and 2-photon parts)."""
    if not 1.0 < kappa < 3.0:
        raise ValueError("kappa must lie in (1, 3)")
    return v0 - kappa * g2


# ------------------------------------------------------------------ heralded state (App. D)
def heralded_state(t: float, convention: str = "printed") -> Statevector:
    """Heralded polarization state, |+-> = (|H>+|V>)/sqrt2 etc.

    convention="printed" : Eq. (D1) of Fan et al.:  |psi> ~ |+-> - sqrt(t/(1-t)) |-+>
    convention="derived" : |psi> ~ (1-t) |+-> - t |-+>   i.e. ratio t/(1-t), as in Gonzalez-Ruiz et al.
        (Opt. Express 32, 13181, Eq. 1) and as a beam-splitter derivation gives (the two pathways have
        amplitudes sqrt(t)*sqrt(t) and sqrt(1-t)*sqrt(1-t)).  The two coincide at t = 1/2, the only value
        used in the paper's simulations, so none of its results is affected.
    t = 1/2 gives a maximally entangled state."""
    if not 0.0 < t < 1.0:
        raise ValueError("t must lie in (0, 1)")
    ratio = math.sqrt(t / (1.0 - t)) if convention == "printed" else t / (1.0 - t)
    s_ = 1.0 / math.sqrt(2.0)
    plus, minus = np.array([s_, s_], dtype=complex), np.array([s_, -s_], dtype=complex)
    v = np.kron(plus, minus) - ratio * np.kron(minus, plus)
    return Statevector(v / np.linalg.norm(v))


def max_chsh(state) -> float:
    """Horodecki criterion: S_max = 2 sqrt(m1 + m2), m1, m2 the two largest eigenvalues of T^T T,
    T_ij = Tr[rho sigma_i x sigma_j]. Accepts a Statevector or DensityMatrix of two qubits."""
    rho = state.data if isinstance(state, DensityMatrix) else np.outer(state.data, state.data.conj())
    T = np.array([[np.real(np.trace(rho @ np.kron(si, sj))) for sj in _PAULI] for si in _PAULI])
    m = np.sort(np.linalg.eigvalsh(T.T @ T))[::-1]
    return 2.0 * math.sqrt(m[0] + m[1])


def max_chsh_pure_formula(t: float, convention: str = "printed") -> float:
    """Closed form S_max = 2 sqrt(1 + sin^2(2 theta)) of the heralded state: with amplitude ratio r (|-+> over |+->),
    sin(2 theta) = 2 r / (1 + r^2); r = sqrt(t/(1-t)) (printed) or t/(1-t) (derived)."""
    r = math.sqrt(t / (1.0 - t)) if convention == "printed" else t / (1.0 - t)
    return 2.0 * math.sqrt(1.0 + (2.0 * r / (1.0 + r * r)) ** 2)


# ------------------------------------------------------------------ channel / bookkeeping
def channel_efficiency(L_km: float, eta_conv: float = 0.5, L0_km: float = 22.0) -> float:
    """Eq. (D2): eta_C = eta_conv exp(-L / (2 L0))  (each party sits L/2 from the heralding station)."""
    return eta_conv * math.exp(-L_km / (2.0 * L0_km))


def heralded_rounds(N: float, P_H: float) -> float:
    """Eq. (D3): n_H = P_H N."""
    return P_H * N


def acquisition_hours(N: float, rate_hz: float = 75e6) -> float:
    """Time to emit N rounds at a source rate (paper: N = 1e14 at 75 MHz -> ~370 h)."""
    return N / rate_hz / 3600.0
