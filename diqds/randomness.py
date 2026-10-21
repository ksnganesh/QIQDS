"""
Randomness ledger (Sec. 2.3 of the follow-up paper): every private random bit a DIQDS key-generation run consumes.

Analytic side
    entropy_per_round   Eq. (5):  H_round = 2 + h(gamma) + (1 - gamma)/2 h(p)      (random-key-basis protocol)
    sampler_bits_per_round   biased bits made by thresholding r uniform bits cost r bits, not h(.)
    seed_bits           Toeplitz seeds (public, but uniform and independent of the devices)
    demand / supply_check   totals, ratio to the key one signature needs, bit rates, min-entropy kappa < 1

Empirical side
    RandomnessLedger    counts what a run really draws (diqkd.run_diqkd fills one), so Eq. (5) can be checked
                        against the implementation instead of being assumed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from .finite_key import h2


# ------------------------------------------------------------------ analytic ledger
def entropy_per_round(gamma: float, p: float, random_key_basis: bool = True) -> float:
    """Expected private entropy (bits) per heralded round.

    random_key_basis=True (Sec. II.A protocol, Eq. 5):
        Alice's input X (1) + Bob's test flag h(gamma) + Bob's setting bit (1) + flip bit in each matched key round
        (probability (1-gamma)/2) h(p).
    random_key_basis=False (no-sifting protocol of Ref. [73]): key rounds use fixed inputs, so X and Y are drawn in
        test rounds only: h(gamma) + 2 gamma + (1-gamma) h(p)  (every key round is matched)."""
    if random_key_basis:
        return 2.0 + h2(gamma) + 0.5 * (1.0 - gamma) * h2(p)
    return h2(gamma) + 2.0 * gamma + (1.0 - gamma) * h2(p)


def entropy_per_party(gamma: float, p: float, random_key_basis: bool = True):
    """(Alice, Bob) split of Eq. (5): Alice draws X and the flips; Bob draws the test flag and his setting bit."""
    if random_key_basis:
        return 1.0 + 0.5 * (1.0 - gamma) * h2(p), h2(gamma) + 1.0
    return gamma + (1.0 - gamma) * h2(p), h2(gamma) + gamma


def sampler_bits_per_round(gamma: float, p: float, r: int = 16, random_key_basis: bool = True) -> float:
    """Raw uniform bits per round if every biased draw is made by thresholding r uniform bits (cost r, not h)."""
    flips = r if p > 0 else 0
    if random_key_basis:
        return 2.0 + r + 0.5 * (1.0 - gamma) * flips
    return r + 2.0 * gamma + (1.0 - gamma) * flips


def seed_bits(n: int, ell: int, tag_len: int, toeplitz_tag: bool = True) -> Dict[str, int]:
    """Public-but-uniform seeds: privacy-amplification Toeplitz seed (n + ell - 1 bits) and, if the EC verification
    hash is also a Toeplitz hash, another n + tag_len - 1 bits (about one more bit per round)."""
    out = {"privacy-amplification Toeplitz seed": n + ell - 1}
    if toeplitz_tag:
        out["EC-verification Toeplitz seed"] = n + tag_len - 1
    return out


@dataclass
class Demand:
    gamma: float
    p: float
    rounds: float
    entropy_per_round: float
    total_bits: float
    bits_per_key_bit: float            # total_bits / (3 n_s)
    bits_per_second: Optional[float]   # needs an event rate


def demand(rounds: float, gamma: float, p: float, key_bits_needed: int, events_per_second: Optional[float] = None,
           random_key_basis: bool = True, sampler_r: Optional[int] = None, kappa: float = 1.0) -> Demand:
    """Total private bits for `rounds` heralded rounds. sampler_r: price biased draws as r raw bits; kappa < 1: the
    generator has min-entropy kappa per raw bit, so the raw-bit demand is multiplied by 1/kappa."""
    per = (sampler_bits_per_round(gamma, p, sampler_r, random_key_basis) if sampler_r
           else entropy_per_round(gamma, p, random_key_basis)) / kappa
    total = rounds * per
    return Demand(gamma, p, rounds, per, total, total / key_bits_needed,
                  None if events_per_second is None else events_per_second * per)


def supply_check(gamma: float, p: float, events_per_second: float, generator_bits_per_second: float,
                 random_key_basis: bool = True, sampler_r: Optional[int] = None, kappa: float = 1.0) -> dict:
    """'Supply check' box of Fig. 2: can the generator keep up with the run? (Bandwidth only; uniformity, privacy during
    the run and independence from the devices cannot be certified by a rate check.)"""
    need = demand(1.0, gamma, p, 1, events_per_second, random_key_basis, sampler_r, kappa).bits_per_second
    return dict(required_bps=need, available_bps=generator_bits_per_second, ok=generator_bits_per_second >= need,
                margin=generator_bits_per_second / need)


# ------------------------------------------------------------------ empirical ledger
@dataclass
class _Entry:
    draws: int = 0
    entropy: float = 0.0               # expected Shannon entropy of the drawn bits
    private: bool = True
    biased: bool = False


@dataclass
class RandomnessLedger:
    """Counts the random draws a protocol run makes. `uniform` = fair bits; `biased` = Bernoulli(bias) draws."""
    entries: Dict[str, _Entry] = field(default_factory=dict)

    def uniform(self, name: str, count: int, private: bool = True):
        e = self.entries.setdefault(name, _Entry(private=private))
        e.draws += int(count)
        e.entropy += int(count)

    def biased(self, name: str, count: int, bias: float, private: bool = True):
        e = self.entries.setdefault(name, _Entry(private=private, biased=True))
        e.draws += int(count)
        e.entropy += int(count) * h2(bias)

    def entropy(self, private_only: bool = True) -> float:
        return sum(e.entropy for e in self.entries.values() if e.private or not private_only)

    def sampler_bits(self, r: int = 16, private_only: bool = True) -> float:
        """Raw bits if every biased draw is made by thresholding r uniform bits."""
        return sum((e.draws * r if e.biased else e.entropy) for e in self.entries.values()
                   if e.private or not private_only)

    def per_round(self, n: int, r: Optional[int] = None) -> float:
        return (self.sampler_bits(r) if r else self.entropy()) / n

    def summary(self) -> str:
        w = max(len(k) for k in self.entries) if self.entries else 10
        rows = [f"{k:{w}s}  draws={e.draws:>12,}  entropy={e.entropy:>14,.1f} bits  "
                f"{'private' if e.private else 'public seed'}{'  (biased)' if e.biased else ''}"
                for k, e in self.entries.items()]
        return "\n".join(rows)
