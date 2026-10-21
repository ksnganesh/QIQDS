# diqds — device-independent quantum digital signatures, reimplemented from the paper

Python reimplementation of **Fan, Bian, Li, Wen, Yin, Chen, "Device-independent quantum digital signatures under
realistic conditions", Phys. Rev. A 114, 032617 (2026)**, with Qiskit for the quantum devices.
The finite-size key bound was reconstructed from its sources (Tan et al., Quantum 6, 880, arXiv:2012.08714;
Ho et al., PRL 124, 230502, arXiv:2005.13015) because the PDF's math is garbled, then **validated against the numbers
printed in the paper**.

```bash
pip install -r requirements.txt
python scripts/demo_end_to_end.py            # both DIQKD links -> key pool -> signatures   (~10 s)
python scripts/demo_end_to_end.py --backend aer          # run the CHSH circuits on qiskit-aer
python -m pytest -q                          # 59 fast tests (~50 s); use `python -m pytest`, not bare `pytest`
python scripts/compare_with_paper.py --report   # side-by-side with the paper (cached results; see COMPARISON.md)
python -m pytest -q -m slow                  # regression against the paper's printed numbers (~8 min)
```
```python
from diqds.presets import RKM_SIFTED
from diqds.experiments import signature_rate_werner
signature_rate_werner(10**9, 0.95, RKM_SIFTED)   # {'ell': 2.4e8, 'n_s': 46, 'r_sig': 1.7e6, 'gamma': 0.008, ...}
```

## Map of the paper to the code

| Paper | Module | Notes |
|---|---|---|
| Sec. II.A steps 1-7 (acquisition, sifting, noisy preprocessing, EC, parameter estimation, PA) | `diqkd.py` | `plan_distribution()` fixes parameters from Eq. (9); `run_diqkd()` executes the protocol |
| Honest devices, Werner state, CHSH measurements (Sec. IV) | `quantum.py` | **Qiskit**: `QuantumCircuit` (H, CX, Ry, measure), `DensityMatrix`, `AerSimulator` + depolarizing noise model |
| Eq. (9), (B1)-(B12) | `finite_key.py` | entropy-accumulation key length + optimiser over γ, t, α, α′, β, ε-split, p |
| Error correction (step 5) | `error_correction.py` | real **Cascade** (all revealed parities counted against EC_max) or an oracle |
| Sec. II.B, Fig. 2, App. A | `messaging.py`, `hashing.py`, `gf2.py` | sign / verify / certify, LFSR-Toeplitz hash (matrix and fast forms cross-checked), GF(2)[x] arithmetic |
| Eqs. (4)-(8), Table I | `security.py` | n_s = 46 from Table I; r_sig = ℓ/(3 n_s) |
| Figs. 3-6 | `experiments.py`, `presets.py`, `scripts/` | signature rates, minimum rounds, Fig. 6 report; Fig. 3/5-like plots |
| Follow-up paper: Eq. (5), Table 3 | `randomness.py` (+ ledger inside `diqkd.run_diqkd`) | randomness ledger, supply check |
| Follow-up paper: Eq. (2) | `renyi_bound.py` | **scaffold only** (needs the Rényi convex program) |
| App. C/D | `photonic.py` | HOM visibility, heralded state (D1), channel (D2); **not** the Fig. 7 distance curves |

Qiskit is used for everything that is actually quantum (state, measurements, noise, sampling). The finite-size
bounds are classical numerics (NumPy/SciPy), as in the paper.

## Validation against the paper

**Fig. 5: minimum Werner visibility for a positive signature** (`scripts/reproduce_thresholds.py`, protocol variant `RKM_SIFTED`)

| n | V_min, p = 0 (this code / paper) | V_min, optimised p (this code / paper) |
|---|---|---|
| 10⁸  | 0.8827 / 0.8835 | 0.8788 / 0.8799 |
| 10⁹  | 0.8681 / 0.8686 | 0.8601 / 0.8608 |
| 10¹⁰ | 0.8619 / 0.8622 | 0.8503 / 0.8508 |

Largest deviation 1.1×10⁻³ (all slightly on the optimistic side, plausibly a less-converged optimiser in the paper).
The size of the noisy-preprocessing gain matches as well.

**Fig. 6: matter-qubit experiments** (`scripts/reproduce_fig6_claims.py`, protocol variant `STANDARD`; parameters read from the experiment papers)

| Experiment | Paper's statement | This code |
|---|---|---|
| Nadlinger et al. [73], S = 2.677, Q = 1.44 % | 1.5×10⁶ rounds feasible | n_min = 9.5×10⁵; ℓ = 135k bits at 1.5×10⁶ ✓ |
| Lu et al. [75], 11 km, S = 2.612, Q = 2.85 % | needs more than the 1.208×10⁶ collected rounds, positive by 2.4×10⁶ | n_min = 2.17×10⁶ ✓ |
| Zhang et al. [74], S = 2.578, Q = 7.79 % | "order of 10⁷ hours" | 5.8×10⁵ h (standard) / 1.2×10⁶ h (RKM) — **about 10× lower than the paper** |

Also reproduced: n_s = 46 and 138 key bits per signature from Table I; "≈370 h for 10¹⁴ rounds at 75 MHz";
S = 2√2·V and Q = (1−V)/2 from the Qiskit circuits (exact and Aer); Eq. (A12) (multiples of p(x) hash to 0);
the 2⁻ⁿˢ random-forgery rate; Eq. (C8) → (C7) as σ → 0. `fig3_like.png` / `fig5_like.png` show the threshold-then-linear
behaviour and the noisy-preprocessing gain.

**What to change for the follow-up paper (Rényi bound, budget split, randomness ledger): [`CHANGES_FOR_YOUR_PAPER.md`](CHANGES_FOR_YOUR_PAPER.md), tables in [`PAPER_TABLES.md`](PAPER_TABLES.md).**

**Troubleshooting:** if `pytest` says `No module named 'qiskit'` while `python scripts/...` works, a global `pytest` is
shadowing the one in your virtual environment: run `python -m pytest` (the test run now prints which Python it uses).

**Full side-by-side comparison: [`COMPARISON.md`](COMPARISON.md)** (regenerate the numbers part by part with
`scripts/compare_with_paper.py --part ...`). Caveat: the protocol reading was chosen by comparing with Figs. 5 and 6, so
those two matches are calibrations, not blind predictions; the Fig. 4/3 behaviour, completeness, message-length
insensitivity and the ΔL scaling of Fig. 7 were not tuned.

## What reverse-engineering found in the paper

1. **Eqs. (B1) and (B11) do not belong together.** (B1) halves the key-round entropy (sifting) but (B11) as printed
   charges the full EC cost with no sifting factor and no dependence on p. Taken literally they give V_min ≈ 0.91 at
   n = 10¹⁰ (paper: 0.862). The reading that reproduces Figs. 3-5 puts the same ½ factor in the EC term and uses
   Q′ = p + (1−2p)Q (`ec_model="sifted"`, Tan et al. Eq. 26). Fig. 6 instead matches the *no-sifting* protocol of
   Ref. [73] with (B11) as printed. These are the two presets `RKM_SIFTED` and `STANDARD`. If EC ignores p, noisy
   preprocessing becomes a free lunch (positive key at V = 0.80), so the paper cannot have done that.
2. The text calls r_p "an affine function of ω". It is a nonlinear convex function; the affine min-tradeoff function is
   its tangent g_t (convexity checked numerically, so the tangent is a valid lower bound).
3. ε bookkeeping: Tan et al. give soundness max{ε_EA, ε_PA+2ε_s} + 2ε_h; the paper's wording suggests +3ε_h. The
   difference is negligible. The paper's robustness bound uses ε_corr ≤ 2⁻⁶¹, so ε_h defaults to 2⁻⁶¹ (61-bit tag).
4. The polynomial-generation function f of Ref. [32] is not given. `gf2.irreducible_from_key` is a documented
   stand-in (first irreducible polynomial at or after x^n + Z); its output is not exactly uniform over irreducibles.
5. In the messaging stage as described, Bob's own X_b and Z_b are never used in verification.
6. Eq. (D1) prints the amplitude ratio √(t/(1−t)); the cited model paper (Gonzalez-Ruiz et al., Eq. 1) and a
   beam-splitter derivation give t/(1−t). They agree at t = 1/2, the only value the paper simulates
   (`photonic.heralded_state(t, convention="printed" | "derived")`).

## Not reproduced / limits

* **Fig. 7 (photonic distance curves)**: the paper does not give the heralding probability or the map from
  (V_HOM, g⁽²⁾, η_l, T, t) to the heralded state; the probability table is in the supplement of Ref. [80]. Only the
  formulas stated in App. C/D are implemented. A first-principles estimate (η_l only) overshoots the ideal-source
  distances by 45-66 km, i.e. the paper's model contains noise its text does not specify (see COMPARISON.md §3).
* The simulation shows rates and protocol behaviour for honest and unentangled devices. It does not prove security;
  the bound is a transcription of Tan et al.'s Theorem 1, so security claims rest on that proof.
* **Not production cryptography.** Randomness comes from `numpy.random.Generator` (not a CSPRNG); the protocol assumes
  trusted local randomness and storage as the paper does. Cascade is interactive and sends test-round outputs directly
  (γn bits instead of γn·h(1−ω)), which fits inside EC_max in the tested regimes.
* Rounds with equal (x, y) are simulated in batches (they are i.i.d.); `quantum.round_circuit(x, y)` gives the per-round circuit.
