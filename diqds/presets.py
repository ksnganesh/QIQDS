"""
Named protocol variants and experimental parameter sets.

The paper uses two slightly different accounting conventions, and reverse-engineering its
numbers showed which one belongs to which figure (see README, "What the numbers say"):

  RKM_SIFTED  random key measurement + sifting + noisy preprocessing (Sec. II.A protocol).
              Entropy side: g = (1-gamma)/2 r_p + gamma r_0; EC side: only X = Y rounds are
              corrected, at error rate p + (1-2p)Q.  Reproduces the Fig. 3-5 depolarizing numbers.
  STANDARD    the key-generation protocol of Nadlinger et al. (Ref. [73]): no sifting loss,
              Eq. (B11) as printed.  Reproduces the Fig. 6 statements for Refs. [73] and [75].
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Variant:
    name: str
    key_weight: float      # sifting factor on the key-round entropy term (1/2 or 1)
    ec_model: str          # see finite_key.ec_max

    @property
    def random_key_basis(self) -> bool:
        """True: Alice and Bob each pick a random key basis and sift X != Y rounds away."""
        return self.key_weight < 1.0


RKM_SIFTED = Variant("rkm_sifted", key_weight=0.5, ec_model="sifted")
STANDARD = Variant("standard", key_weight=1.0, ec_model="printed")


@dataclass(frozen=True)
class Experiment:
    """Honest-device description of a published matter-qubit DIQKD experiment."""
    name: str
    S: float                 # CHSH value
    Q: float                 # quantum bit error rate
    rounds: float            # heralded rounds actually collected
    hours: float             # wall-clock acquisition time
    source: str
    variant: Variant = STANDARD

    @property
    def rate_per_hour(self) -> float:
        return self.rounds / self.hours


# Values below were read from the primary sources (checked while building this package).
NADLINGER_2022 = Experiment(
    "Nadlinger et al., Nature 607, 682 (ions, 2 m)", S=2.677, Q=0.0144,
    rounds=1.5e6, hours=7.9,
    source="arXiv:2109.14600: S = 2.677(6), Q = 1.44(2)%, ~1.5e6 pairs, 7.9 h wall clock")

ZHANG_2022 = Experiment(
    "Zhang et al., Nature 607, 687 (Rb atoms, 400 m)", S=2.578, Q=0.0779,
    rounds=3342, hours=75.0,
    source="arXiv:2110.00575: S = 2.578(75), Q = 0.0779(91), N = 3342 rounds over 75 h",
    variant=RKM_SIFTED)   # that experiment used the random-key-basis protocol of Schwonnek et al.

LU_2026_11KM = Experiment(
    "Lu et al., Science 391, 592 (Rb atoms, 11 km)", S=2.612, Q=0.0285,
    rounds=1.208e6, hours=624.0,
    source="arXiv:2602.09596: S = 2.612(31), Q = 0.0285(2), 1.208e6 heralded events in 624 h")

EXPERIMENTS = {"nadlinger": NADLINGER_2022, "zhang": ZHANG_2022, "lu": LU_2026_11KM}
