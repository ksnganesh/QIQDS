import numpy as np
import pytest
from diqds.gf2 import irreducible_from_key
from diqds.hashing import bits_to_int
from diqds.messaging import (KeyPool, QDSSession, alice_sign, build_party_keys, encode_document,
                             forgery_known_polynomial, recipient_verify, run_session)

N_S, N_M = 46, 1000


def _pool(rng, blocks=6, n_s=N_S):
    return KeyPool(rng.integers(0, 2, 3 * n_s * blocks).astype(np.uint8),
                   rng.integers(0, 2, 3 * n_s * blocks).astype(np.uint8), n_s)


def test_key_relations_of_section_IIB():
    rng = np.random.default_rng(0)
    A, B, C = _pool(rng).next_keys()
    assert np.array_equal(A.X, C.X) and np.array_equal(A.Z, C.Z)
    assert np.array_equal(A.Y, B.Y ^ C.Y)


def test_honest_signature_accepted_by_both():
    rng = np.random.default_rng(1)
    A, B, C = _pool(rng).next_keys()
    b, c, s = run_session(A, B, C, encode_document(b"Pay Bob 100 EUR", N_M))
    assert b is True and c is True
    assert s.log[-1] == "Charlie accepts"


def test_tampered_document_or_signature_rejected():
    rng = np.random.default_rng(2)
    A, B, C = _pool(rng).next_keys()
    doc = encode_document(b"original", N_M)
    sig = alice_sign(doc, A)
    d2 = doc.copy(); d2[7] ^= 1
    assert not recipient_verify(sig, d2, B.Y, C.X, C.Y, C.Z)
    s2 = sig.copy(); s2[3] ^= 1
    assert not recipient_verify(s2, doc, B.Y, C.X, C.Y, C.Z)


def test_forwarded_tampering_is_caught_by_charlie():
    rng = np.random.default_rng(3)
    A, B, C = _pool(rng).next_keys()
    doc = encode_document(b"original", N_M)

    def bob_tamper(sig, d, yb):
        d = d.copy(); d[11] ^= 1
        return sig, d, yb
    b, c, _ = run_session(A, B, C, doc, bob_tamper=bob_tamper)
    assert b is True and c is False        # Bob checks what Alice sent; Charlie sees the forged forward


def test_charlie_must_record_before_revealing():
    rng = np.random.default_rng(4)
    s = QDSSession(*_pool(rng).next_keys())
    with pytest.raises(RuntimeError):
        s.charlie_reveals()


def test_one_time_keys_are_not_reused():
    rng = np.random.default_rng(5)
    pool = _pool(rng, blocks=2)
    pool.next_keys(); pool.next_keys()
    with pytest.raises(RuntimeError):
        pool.next_keys()


def test_forgery_requires_knowledge_of_p_a():
    """Eq. (A12): adding a multiple of p_a(x) to the message leaves the hash (hence Sig) unchanged."""
    rng = np.random.default_rng(6)
    A, B, C = _pool(rng).next_keys()
    doc = encode_document(b"original", N_M)
    sig = alice_sign(doc, A)
    p_a = irreducible_from_key(bits_to_int(A.Z), N_S)
    fdoc, fsig = forgery_known_polynomial(doc, sig, p_a, rng)
    assert not np.array_equal(fdoc, doc)
    assert recipient_verify(fsig, fdoc, B.Y, C.X, C.Y, C.Z)
    # without p_a, a random modification is rejected
    rnd = doc.copy(); rnd[:50] ^= rng.integers(0, 2, 50).astype(np.uint8)
    assert not recipient_verify(sig, rnd, B.Y, C.X, C.Y, C.Z)


def test_random_forgery_success_rate_matches_2_pow_minus_ns():
    """Bob fabricates a random (Doc, Sig): success probability 2^-n_s (Sec. III.A). Use n_s = 8."""
    rng = np.random.default_rng(7)
    n_s, trials, hits = 8, 12000, 0
    for _ in range(trials):
        A, B, C = build_party_keys(rng.integers(0, 2, 3 * n_s).astype(np.uint8),
                                   rng.integers(0, 2, 3 * n_s).astype(np.uint8), n_s)
        doc = rng.integers(0, 2, 100).astype(np.uint8)
        sig = rng.integers(0, 2, n_s).astype(np.uint8)
        hits += recipient_verify(sig, doc, B.Y, C.X, C.Y, C.Z)
    assert 0.5 * 2.0 ** -n_s < hits / trials < 2.0 * 2.0 ** -n_s
