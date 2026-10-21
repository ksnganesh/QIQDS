"""
Hash functions used by the protocol.

1. LFSR-based Toeplitz hash h_{p,s}(M) = H_{n x m} M   (Appendix A, Eqs. A1-A12), the one-time
   universal hash of the messaging stage.  Two independent implementations:
     * lfsr_toeplitz_matrix / hash_matrix : the explicit n x m matrix of Eq. (A9)
     * hash_fast                          : M_W(W) s via polynomial reduction, Eq. (A10)
2. toeplitz_hash : random Toeplitz 2-universal hash via FFT, used for privacy amplification and
   for the error-correction verification tag of the DIQKD distribution stage.
"""
from __future__ import annotations

import numpy as np

from .gf2 import deg, pmod


# ------------------------------------------------------------------ bit helpers
def bits_to_int(bits) -> int:
    """bits[i] -> coefficient of x^i."""
    v = 0
    for i, b in enumerate(np.asarray(bits, dtype=np.uint8)):
        if b:
            v |= 1 << i
    return v


def int_to_bits(v: int, length: int) -> np.ndarray:
    return np.array([(v >> i) & 1 for i in range(length)], dtype=np.uint8)


# ----------------------------------------------------------- LFSR-based Toeplitz hash
def _lfsr_sequence(p: int, s_bits: np.ndarray, length: int) -> np.ndarray:
    """S_1..S_length with initial state (S_1..S_n) = s_bits and S_{k+n} = sum_j p_j S_{k+j} (mod 2).

    p is the integer form of p(x) = x^n + p_{n-1} x^{n-1} + ... + p_0 (bit j = p_j)."""
    n = deg(p)
    pj = int_to_bits(p, n)                        # p_0 .. p_{n-1}
    S = np.zeros(length, dtype=np.uint8)
    S[:n] = s_bits[:n]
    taps = np.nonzero(pj)[0]
    for k in range(length - n):
        S[k + n] = np.bitwise_xor.reduce(S[k + taps]) if len(taps) else 0
    return S


def lfsr_toeplitz_matrix(p: int, s_bits: np.ndarray, m: int) -> np.ndarray:
    """The n x m matrix H = (s_0, ..., s_{m-1}) of Eq. (A9); s_i = W^i s is a window of the LFSR
    sequence: H[r, i] = S_{n+i-r} (1-indexed), a Toeplitz matrix."""
    n = deg(p)
    S = _lfsr_sequence(p, np.asarray(s_bits, dtype=np.uint8), n + m - 1)
    r = np.arange(n)[:, None]
    i = np.arange(m)[None, :]
    return S[n + i - r - 1]


def hash_matrix(p: int, s_bits, message_bits) -> np.ndarray:
    """Digest via the explicit matrix (reference implementation, O(n m))."""
    msg = np.asarray(message_bits, dtype=np.uint8)
    H = lfsr_toeplitz_matrix(p, s_bits, len(msg))
    return (H.astype(np.int64) @ msg.astype(np.int64) % 2).astype(np.uint8)


def hash_fast(p: int, s_bits, message_bits) -> np.ndarray:
    """Digest via Eq. (A10): H M = M_W(W) s, where M_W(x) = sum_i M_i x^i.  Because p(W) = 0
    (Cayley-Hamilton, A5), M_W(W) = r(W) with r = M_W mod p, so only the first n columns of H are
    needed:  digest = XOR_{j: r_j = 1} s_j.   O(m + n^2)."""
    n = deg(p)
    r = pmod(bits_to_int(message_bits), p)
    S = _lfsr_sequence(p, np.asarray(s_bits, dtype=np.uint8), 2 * n - 1)
    out = np.zeros(n, dtype=np.uint8)
    for j in range(n):
        if (r >> j) & 1:
            # s_j = (S_{n+j}, ..., S_{j+1})  ->  row index rr holds S_{n+j-rr}
            out ^= S[j:j + n][::-1]
    return out


# -------------------------------------------------- 2-universal Toeplitz hash via FFT
def toeplitz_hash(bits: np.ndarray, seed: np.ndarray, out_len: int) -> np.ndarray:
    """Random Toeplitz hash {0,1}^n -> {0,1}^out_len. `seed` has n + out_len - 1 random bits.
    out_r = XOR_i seed[r - i + n - 1] * bits[i]  (a 2-universal family)."""
    bits = np.asarray(bits, dtype=np.float64)
    n = len(bits)
    if len(seed) != n + out_len - 1:
        raise ValueError("seed must have n + out_len - 1 bits")
    if out_len == 0:
        return np.zeros(0, dtype=np.uint8)
    size = 1 << int(np.ceil(np.log2(n + len(seed))))
    conv = np.fft.irfft(np.fft.rfft(seed.astype(np.float64), size) *
                        np.fft.rfft(bits, size), size)
    # conv[k] = sum_i seed[k - i] bits[i]; taking k = r + n - 1 gives seed[r + n - 1 - i] bits[i]
    out = np.rint(conv[n - 1:n - 1 + out_len]).astype(np.int64) % 2
    return out.astype(np.uint8)
