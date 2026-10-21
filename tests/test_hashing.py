import numpy as np
from diqds.gf2 import all_irreducibles, clmul, deg, irreducible_from_key, is_irreducible
from diqds.hashing import bits_to_int, hash_fast, hash_matrix, int_to_bits, toeplitz_hash


def test_irreducible_counts():
    # number of irreducible polynomials of degree n over GF(2)
    for n, expected in [(2, 1), (3, 2), (4, 3), (5, 6), (8, 30), (10, 99), (12, 335)]:
        assert len(all_irreducibles(n)) == expected
    assert is_irreducible(0b10011) and not is_irreducible(0b10001)   # x^4+x+1 yes, x^4+1 no


def test_generated_polynomial_is_irreducible_and_deterministic():
    p = irreducible_from_key(0xDEADBEEF, 46)
    assert deg(p) == 46 and is_irreducible(p)
    assert p == irreducible_from_key(0xDEADBEEF, 46)


def test_matrix_and_fast_hash_agree():
    rng = np.random.default_rng(1)
    for _ in range(60):
        n, m = int(rng.integers(5, 60)), int(rng.integers(1, 300))
        p = irreducible_from_key(int(rng.integers(0, 2 ** 62)), n)
        s, M = rng.integers(0, 2, n).astype(np.uint8), rng.integers(0, 2, m).astype(np.uint8)
        assert np.array_equal(hash_matrix(p, s, M), hash_fast(p, s, M))


def test_multiples_of_p_hash_to_zero_eq_A12():
    rng = np.random.default_rng(2)
    n = 46
    p = irreducible_from_key(99, n)
    s = rng.integers(0, 2, n).astype(np.uint8)
    M = clmul(p, int(rng.integers(1, 2 ** 50)))
    assert not hash_fast(p, s, int_to_bits(M, deg(M) + 1)).any()


def test_hash_is_linear():
    rng = np.random.default_rng(3)
    n, m = 31, 200
    p = irreducible_from_key(5, n)
    s = rng.integers(0, 2, n).astype(np.uint8)
    a, b = rng.integers(0, 2, m).astype(np.uint8), rng.integers(0, 2, m).astype(np.uint8)
    assert np.array_equal(hash_fast(p, s, a ^ b), hash_fast(p, s, a) ^ hash_fast(p, s, b))


def test_collision_probability_below_paper_bound():
    """Sec. III.A: Pr[h(D) = 0] <= n_m / 2^(n_s - 1) for the LFSR-Toeplitz family with uniform p, s.
    Worst-case D = product of 5 distinct degree-12 irreducibles (the family's actual collision rate is
    about 5/335 + 2^-12 ~ 0.015, bound 0.031)."""
    rng = np.random.default_rng(4)
    n_s, n_m = 12, 64
    irr = all_irreducibles(n_s)
    D = 1
    for q in irr[:5]:
        D = clmul(D, q)
    Dbits = int_to_bits(D, deg(D) + 1)
    assert deg(D) < n_m
    trials, hits = 20000, 0
    for _ in range(trials):
        p = irr[int(rng.integers(0, len(irr)))]
        s = rng.integers(0, 2, n_s).astype(np.uint8)
        hits += not hash_fast(p, s, Dbits).any()
    rate = hits / trials
    assert rate <= n_m / 2 ** (n_s - 1)
    assert abs(rate - (5 / len(irr) + 2.0 ** -12)) < 0.006


def test_fft_toeplitz_matches_brute_force():
    rng = np.random.default_rng(5)
    for n, l in [(200, 37), (513, 512), (1000, 1)]:
        bits = rng.integers(0, 2, n).astype(np.uint8)
        seed = rng.integers(0, 2, n + l - 1).astype(np.uint8)
        T = np.array([[seed[r - i + n - 1] for i in range(n)] for r in range(l)], dtype=np.int64)
        assert np.array_equal(toeplitz_hash(bits, seed, l), (T @ bits) % 2)
