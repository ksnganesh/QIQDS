"""
Arithmetic in GF(2)[x]. A polynomial is a Python int: bit i is the coefficient of x^i.
Used for the irreducible polynomial p(x) of the LFSR-based Toeplitz hash (Appendix A).
"""
from __future__ import annotations


def deg(a: int) -> int:
    return a.bit_length() - 1


def clmul(a: int, b: int) -> int:
    """Carry-less (GF(2)[x]) product."""
    r = 0
    while b:
        low = b & -b
        r ^= a << (low.bit_length() - 1)
        b ^= low
    return r


def pmod(a: int, m: int) -> int:
    """a(x) mod m(x)."""
    dm = deg(m)
    if dm < 0:
        raise ZeroDivisionError
    while True:
        da = deg(a)
        if da < dm:
            return a
        a ^= m << (da - dm)


def pmulmod(a: int, b: int, m: int) -> int:
    return pmod(clmul(a, b), m)


def pgcd(a: int, b: int) -> int:
    while b:
        a, b = b, pmod(a, b)
    return a


def _prime_factors(n: int):
    out, d = [], 2
    while d * d <= n:
        if n % d == 0:
            out.append(d)
            while n % d == 0:
                n //= d
        d += 1
    if n > 1:
        out.append(n)
    return out


def _x_pow_2k(k: int, f: int) -> int:
    """x^(2^k) mod f by k modular squarings."""
    r = pmod(0b10, f)
    for _ in range(k):
        r = pmulmod(r, r, f)
    return r


def is_irreducible(f: int) -> bool:
    """Rabin's irreducibility test over GF(2)."""
    n = deg(f)
    if n < 1:
        return False
    if n == 1:
        return True
    if f & 1 == 0:                       # divisible by x
        return False
    if _x_pow_2k(n, f) != pmod(0b10, f):  # x^(2^n) == x (mod f)
        return False
    for q in _prime_factors(n):
        g = pgcd(f, _x_pow_2k(n // q, f) ^ 0b10)
        if g != 1:
            return False
    return True


def irreducible_from_key(z: int, n: int) -> int:
    """Deterministic polynomial-generation function f: n-bit string z -> irreducible p(x), deg n.

    STAND-IN for the function f of Ref. [32] (Li et al., PR Applied 20, 044011), which the paper
    does not spell out: start at the candidate x^n + z (low bit forced to 1) and step through odd
    polynomials of degree n until an irreducible one is found (about n/2 steps on average).
    Alice and Bob compute the same p(x) from the same key.  Note the output is not exactly
    uniform over irreducibles (gaps bias it), which the paper's security analysis assumes;
    swap in the exact f of Ref. [32] for a production claim.
    """
    top, mask = 1 << n, (1 << n) - 1
    cand = top | (z & mask) | 1
    while True:
        if is_irreducible(cand):
            return cand
        cand += 2
        if cand >= (top << 1):          # wrapped past degree n
            cand = top | 1


def all_irreducibles(n: int):
    """Enumerate all irreducible polynomials of degree n (small n only; used in tests)."""
    return [f for f in range(1 << n, 1 << (n + 1)) if is_irreducible(f)]
