"""
Messaging stage of the OTUH-QDS protocol (Sec. II.B, Fig. 2 of the paper).

Key relations (Sec. II.B):   X_a = X_c,   Y_a = Y_b xor Y_c,   Z_a = Z_c
built from the two distributed keys:  K_AB block = (X_b, Y_b, Z_b),  K_AC block = (X_c, Y_c, Z_c)
(Alice holds a copy of both blocks):  X_a := X_c, Y_a := Y_b xor Y_c, Z_a := Z_c.

Remark (read off the paper's description): in verification Bob only uses X_c, Z_c and Y_b xor Y_c;
his own X_b and Z_b are never used. They are kept to follow the paper's notation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .gf2 import irreducible_from_key
from .hashing import bits_to_int, hash_fast


# ------------------------------------------------------------------ documents / keys
def encode_document(data: bytes, n_m: int) -> np.ndarray:
    """Fixed-length n_m-bit encoding with '10*' padding.  (Trailing zeros of a bit-string do not
    change the polynomial M(x), so the hash needs an injective fixed-length encoding.)"""
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8), bitorder="little")
    if len(bits) + 1 > n_m:
        raise ValueError(f"document of {len(bits)} bits does not fit into n_m = {n_m}")
    out = np.zeros(n_m, dtype=np.uint8)
    out[:len(bits)] = bits
    out[len(bits)] = 1
    return out


@dataclass
class PartyKeys:
    X: np.ndarray
    Y: np.ndarray
    Z: np.ndarray


def build_party_keys(block_ab: np.ndarray, block_ac: np.ndarray, n_s: int):
    """block_ab / block_ac: 3 n_s distributed bits each. Returns (alice, bob, charlie)."""
    if len(block_ab) != 3 * n_s or len(block_ac) != 3 * n_s:
        raise ValueError("each block must hold 3 n_s bits")
    xb, yb, zb = (block_ab[i * n_s:(i + 1) * n_s].copy() for i in range(3))
    xc, yc, zc = (block_ac[i * n_s:(i + 1) * n_s].copy() for i in range(3))
    alice = PartyKeys(xc.copy(), yb ^ yc, zc.copy())
    return alice, PartyKeys(xb, yb, zb), PartyKeys(xc, yc, zc)


class KeyPool:
    """One-time key material: consumes 3 n_s bits from each of K_AB and K_AC per signature."""

    def __init__(self, k_ab: np.ndarray, k_ac: np.ndarray, n_s: int):
        self.k_ab, self.k_ac, self.n_s = np.asarray(k_ab, np.uint8), np.asarray(k_ac, np.uint8), n_s
        self.used = 0

    @property
    def capacity(self) -> int:
        return min(len(self.k_ab), len(self.k_ac)) // (3 * self.n_s)

    @property
    def remaining(self) -> int:
        return self.capacity - self.used

    def next_keys(self):
        if self.remaining <= 0:
            raise RuntimeError("key pool exhausted (one-time keys must never be reused)")
        a, b = 3 * self.n_s * self.used, 3 * self.n_s * (self.used + 1)
        self.used += 1
        return build_party_keys(self.k_ab[a:b], self.k_ac[a:b], self.n_s)


# ------------------------------------------------------------------ the three roles
def _digest(doc_bits: np.ndarray, x_bits: np.ndarray, z_bits: np.ndarray, n_s: int) -> np.ndarray:
    p = irreducible_from_key(bits_to_int(z_bits), n_s)       # p = f(Z)
    return hash_fast(p, x_bits, doc_bits)                    # Dig = H_{ns x nm}(p, X) . Doc


def alice_sign(doc_bits: np.ndarray, ka: PartyKeys) -> np.ndarray:
    """Sig = Dig xor Y_a, with Dig = H(p_a = f(Z_a), X_a) . Doc."""
    n_s = len(ka.X)
    return _digest(doc_bits, ka.X, ka.Z, n_s) ^ ka.Y


def recipient_verify(sig: np.ndarray, doc_bits: np.ndarray, y_b_forwarded: np.ndarray,
                     x_c: np.ndarray, y_c: np.ndarray, z_c: np.ndarray) -> bool:
    """Common rule used by Bob (step 2) and Charlie (step 3):
         K_X = X_c, K_Y = Y_b xor Y_c, K_Z = Z_c;  Dig_exp = Sig xor K_Y;  accept iff Dig_exp == Dig_actual."""
    n_s = len(sig)
    k_y = y_b_forwarded ^ y_c
    expected = sig ^ k_y
    actual = _digest(doc_bits, x_c, z_c, n_s)
    return bool(np.array_equal(expected, actual))


class QDSSession:
    """Message flow of Fig. 2 with the ordering rule of the protocol: Charlie reveals {X_c, Y_c, Z_c}
    to Bob only AFTER he has received and recorded Bob's forwarded {Sig, Doc, Y_b}."""

    def __init__(self, alice: PartyKeys, bob: PartyKeys, charlie: PartyKeys):
        self.alice, self.bob, self.charlie = alice, bob, charlie
        self.log: list[str] = []
        self._bob_inbox: Optional[tuple] = None
        self._charlie_record: Optional[tuple] = None
        self._bob_accepted: Optional[bool] = None

    # step 1 ---------------------------------------------------------------
    def alice_sends(self, doc_bits: np.ndarray, tamper=None):
        """Alice signs and sends {Sig, Doc} to Bob. `tamper(sig, doc)` models an active adversary."""
        sig = alice_sign(doc_bits, self.alice)
        doc = doc_bits.copy()
        if tamper is not None:
            sig, doc = tamper(sig, doc)
        self._bob_inbox = (sig, doc)
        self.log.append("Alice -> Bob: {Sig, Doc}")

    # step 2a --------------------------------------------------------------
    def bob_forwards(self, tamper=None):
        """Bob forwards {Sig, Doc} with his key Y_b to Charlie (a dishonest Bob may tamper)."""
        sig, doc = self._bob_inbox
        y_b = self.bob.Y.copy()
        if tamper is not None:
            sig, doc, y_b = tamper(sig, doc, y_b)
        self._charlie_record = (sig, doc, y_b)
        self.log.append("Bob -> Charlie: {Sig, Doc, Y_b}  (Charlie records it)")

    # step 2b --------------------------------------------------------------
    def charlie_reveals(self):
        if self._charlie_record is None:
            raise RuntimeError("Charlie must record Bob's message before revealing his keys")
        self.log.append("Charlie -> Bob: {X_c, Y_c, Z_c}")
        return self.charlie.X, self.charlie.Y, self.charlie.Z

    def bob_verifies(self) -> bool:
        x_c, y_c, z_c = self.charlie_reveals()
        sig, doc = self._bob_inbox
        self._bob_accepted = recipient_verify(sig, doc, self.bob.Y, x_c, y_c, z_c)
        self.log.append(f"Bob {'accepts' if self._bob_accepted else 'rejects'}")
        return self._bob_accepted

    # step 3 ---------------------------------------------------------------
    def charlie_certifies(self) -> bool:
        if not self._bob_accepted:
            raise RuntimeError("Charlie only certifies after Bob's acceptance notification")
        sig, doc, y_b = self._charlie_record
        ok = recipient_verify(sig, doc, y_b, self.charlie.X, self.charlie.Y, self.charlie.Z)
        self.log.append(f"Charlie {'accepts' if ok else 'rejects'}")
        return ok


def run_session(alice, bob, charlie, doc_bits, alice_tamper=None, bob_tamper=None):
    """Convenience wrapper: returns (bob_accepts, charlie_accepts_or_None, session)."""
    s = QDSSession(alice, bob, charlie)
    s.alice_sends(doc_bits, alice_tamper)
    s.bob_forwards(bob_tamper)
    b = s.bob_verifies()
    c = s.charlie_certifies() if b else None
    return b, c, s


# ------------------------------------------------------------------ attack illustrations
def forgery_known_polynomial(doc_bits: np.ndarray, sig: np.ndarray, p_a: int, rng) -> tuple:
    """Why p_a must stay secret (Sec. III.A, Eq. A12): if the forger knows p_a he adds any multiple of
    p_a(x) to the message polynomial; the hash does not change, so the old Sig stays valid."""
    from .gf2 import clmul, deg
    from .hashing import int_to_bits
    n_m = len(doc_bits)
    dp = deg(p_a)
    q = int(rng.integers(1, 1 << min(n_m - dp - 1, 60)))      # keep the delta within n_m bits
    delta = clmul(p_a, q)
    forged = doc_bits.copy()
    forged ^= int_to_bits(delta, n_m)[:n_m]
    return forged, sig.copy()
