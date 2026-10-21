"""
Error correction for step 5.1 of the DIQKD distribution stage.

The paper (and Tan et al.) only need that the total number of communicated bits is capped at EC_max;
interactive schemes are allowed as long as every communicated bit is counted.  Two options:

  OracleEC : models a capacity-approaching code; Bob learns A exactly and the whole budget EC_max is booked
             as leakage.  Statistically this is the paper's own treatment (completeness assumption eps_com_EC).
  cascade  : a real interactive Cascade reconciliation (Brassard-Salvail) on bit strings; every parity
             revealed is counted, and reconciliation stops when the budget is exhausted.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np


class OracleEC:
    name = "oracle"

    def reconcile(self, a: np.ndarray, r: np.ndarray, qber: float, budget: Optional[int], rng):
        leak = int(budget) if budget is not None else 0
        return a.copy(), leak, True


class CascadeEC:
    name = "cascade"

    def __init__(self, passes: int = 6):
        self.passes = passes

    def reconcile(self, a, r, qber, budget, rng):
        return cascade(a, r, qber, rng, passes=self.passes, budget=budget)


def cascade(a: np.ndarray, b: np.ndarray, qber: float, rng: np.random.Generator,
            passes: int = 6, budget: Optional[int] = None):
    """Interactive Cascade. Alice holds `a`, Bob holds `b` (noisy copy). Returns (b_corrected, leaked_bits, completed).

    Block size of pass 1 is 0.73/qber and doubles every pass; passes >= 2 use a fresh random permutation.
    Whenever a bit is corrected, every other pass' block containing it is re-examined (cascade effect).
    Each revealed parity (block parities and binary-search queries) counts as one leaked bit."""
    n = len(a)
    a = np.asarray(a, dtype=np.uint8)
    b = np.asarray(b, dtype=np.uint8).copy()
    if n == 0:
        return b, 0, True
    k1 = max(4, int(math.ceil(0.73 / max(qber, 1e-3))))
    leak = 0
    perms, ks, inv, diff = [], [], [], []
    exhausted = False

    def block_parities(vec, perm, k):
        nb = -(-n // k)
        v = vec[perm]
        pad = nb * k - n
        if pad:
            v = np.concatenate([v, np.zeros(pad, dtype=np.uint8)])
        return (v.reshape(nb, k).sum(axis=1) & 1).astype(np.uint8)

    def fix(j0, blk0):
        """Locate and flip one error in block blk0 of pass j0; cascade through the other passes."""
        nonlocal leak, exhausted
        stack = [(j0, blk0)]
        while stack:
            j, blk = stack.pop()
            if diff[j][blk] == 0:
                continue
            idx = perms[j][blk * ks[j]:(blk + 1) * ks[j]]
            while len(idx) > 1:
                if budget is not None and leak >= budget:
                    exhausted = True
                    return
                half = len(idx) // 2
                left = idx[:half]
                leak += 1                                   # Alice reveals the parity of `left`
                idx = left if (int(a[left].sum()) & 1) != (int(b[left].sum()) & 1) else idx[half:]
            i = idx[0]
            b[i] ^= 1
            for jj in range(len(perms)):
                bb = inv[jj][i] // ks[jj]
                diff[jj][bb] ^= 1
                if jj != j and diff[jj][bb]:
                    stack.append((jj, bb))

    for j in range(passes):
        k = k1 * (2 ** j)
        if k >= n and j > 0:
            k = n
        perm = np.arange(n) if j == 0 else rng.permutation(n)
        perms.append(perm)
        ks.append(k)
        iv = np.empty(n, dtype=np.int64)
        iv[perm] = np.arange(n)
        inv.append(iv)
        pa, pb = block_parities(a, perm, k), block_parities(b, perm, k)
        diff.append((pa ^ pb).astype(np.uint8))
        leak += len(pa)                                      # Alice sends all block parities of this pass
        if budget is not None and leak > budget:
            return b, leak, False
        for blk in np.nonzero(diff[j])[0]:
            fix(j, int(blk))
            if exhausted:
                return b, leak, False
    return b, leak, True


def get_ec(name: str):
    if name == "oracle":
        return OracleEC()
    if name == "cascade":
        return CascadeEC()
    raise ValueError(name)
