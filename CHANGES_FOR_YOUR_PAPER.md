# What to change in the code for your paper

Your paper ("Tighter finite-size security and a randomness budget for DIQDS") adds three things to Fan et al.:
(1) a tightened key-length bound (Eq. 2, Rényi accumulation), (2) a failure budget linking key and signature layers
(Eqs. 3-4), (3) a randomness ledger (Eq. 5, Table 3). This file lists what the code had, what was added, and what is
still missing. Numbers below come from `scripts/reproduce_paper_tables.py` (output saved in `PAPER_TABLES.md`).

## 0. Status

| Paper element | Code | Status |
|---|---|---|
| Eq. (1), baseline bound (EAT) | `finite_key.key_length` / `maximize_key_length` | existed; reproduces Fan et al.'s thresholds within 1.1e-3 |
| **Eq. (2), tightened Rényi bound** | `renyi_bound.py` | **missing** (documented scaffold only; spec in §1) |
| Eqs. (3)-(4), n_s, budget split | `security.choose_n_s`, `experiments.budget_split_scan`, `scaled_budget` | added; Sec. 3.2 (45/46/48/51, 56) reproduced exactly |
| Eq. (5), Table 3, Sec. 3.3 | `randomness.py`; `diqkd.run_diqkd` now counts the bits it draws | added; every number in Table 3 / Sec. 3.3 reproduced |
| "Supply check" box of Fig. 2 | `randomness.supply_check` | added (bandwidth only) |
| Table 2, left column | `scripts/compare_with_paper.py` + `reproduce_paper_tables.py` | done |
| Table 2, right column; 11 km tightened cells | needs `renyi_bound` | **cannot be verified yet** |
| Threshold "ell >= 3 n_s" (Sec. 3.4) | `ell_min=` in `min_visibility`, `minimum_rounds` | added |
| Asymptotic limit check | `finite_key.asymptotic_visibility_threshold` | added: 0.8570 (p = 0), 0.8383 (optimised p) |
| Where Delta_EAT comes from | `finite_key.penalty_breakdown` | added |

## 1. The one big change: implement Eq. (2)

`diqds/renyi_bound.py` is a scaffold with the contract written out. Only the first two terms of Eq. (1) change;
`omega_threshold` (B10), `ec_max(model="sifted")`, the last four terms, the budget and the protocol code are reused.

1. `single_round_rate(omega_thr, alpha, gamma, p)`: the convex program. For CHSH the test statistic is the winning
   probability, so D(q||nu) = gamma * D_bin(omega_q || omega_nu) and the outer minimisation is one-dimensional; the inner
   object is the smallest Rényi entropy of order 1/(2-alpha) compatible with winning probability omega. This is the part that
   needs the SDP/NPA (or an exact qubit reduction); nothing in the repository can stand in for it.
2. `penalty(...)`: alpha/(alpha-1) log2(1/eps_EA) + vartheta(eps_s)/(alpha-1) + the chain-rule cost of the GREAT theorem you
   use (this replaces n*gamma and the alpha' terms). `finite_key.theta_eps` already gives vartheta.
3. An optimiser over (alpha, gamma, p, smoothing split, eps_h): copy `finite_key._decode` / `maximize_key_length` /
   `min_visibility`. There is no tangent point t, no beta, no second Rényi order, so the vector gets shorter.

Acceptance tests (the first four need no data from your paper):
- alpha -> 1, n -> infinity must give `asymptotic_visibility_threshold` (0.8570 / 0.8383) if r_alpha keeps the baseline's
  single-basis entropy. A lower asymptote means you use the true random-key-basis entropy; then part of your gain is *not*
  finite-size, and you should also compare against Tan et al.'s numerical tradeoff (Eq. 103 there).
- r_alpha <= von Neumann rate for all alpha > 1, increasing to it as alpha -> 1.
- V_min(n) decreases with n, stays above the asymptote, gap to the baseline closes with n.
- Plug an affine tradeoff into your code: it must give 0.8827 / 0.8681 / 0.8619 (p = 0; n = 1e8 / 1e9 / 1e10).
- Table 2 right column: 0.8719 / 0.8637 / 0.8600 and 0.8646 / 0.8526 / 0.8462, and the 11 km row.
Then `python scripts/reproduce_paper_tables.py --tightened your_results.json` fills the comparison columns.

Plausibility of your magnitudes (checked, not proven): your tightened values lie above the asymptote everywhere and recover
34-42 % of the baseline's finite-size excess at every n. The baseline penalty Delta_EAT is only 7 % of the gross entropy at
(V = 0.95, n = 1e9) and 10.5 % at (V = 0.87, n = 1e9), so V_min can only move by ~1e-3-1e-2 there, whereas at the 11 km link
(n = 3e6, no-sifting) it is 47 %, so a large cut in the required rounds is plausible.

## 2. Things in the paper that disagree with the code (please decide / fix)

1. **Protocol for the 11 km row.** Fan et al.'s Fig. 6 (and the 2.4e6 / 1248 h cell) corresponds, in my reading (the one that reproduces
   its statements for Refs. [73] and [75]), to the no-sifting protocol of Ref. [73]; your Sec. 2.2 describes the random-key-basis protocol with sifting. The exact baselines at the 11 km data
   (S = 2.612, Q = 0.0285, 1.208e6 events / 624 h) are: **no-sifting 2.14e6 rounds (1107 h); sifted 5.5e6 rounds (2842 h)**. Your
   1.04e6 is therefore x2.06 or x5.29 fewer rounds depending on the protocol. Replace "at most 2.4e6 / 1248 h" by the exact
   baseline of the protocol you actually bound, and say which.
2. **Ledger vs protocol.** Eq. (5) (2 + h(gamma) + (1-gamma)/2 h(p)) is the random-key-basis protocol. For the no-sifting
   protocol key rounds use fixed inputs and the cost is h(gamma) + 2 gamma + (1-gamma) h(p). At the optimiser's own parameters
   the numbers are 0.55 bit/round (ion run, gamma = 0.077), 0.46 bit/round (11 km, gamma = 0.062), both with p = 0 (noisy
   preprocessing does not help there), and 2.07 bit/round for the sifted protocol at V = 0.95, n = 1e9. The abstract's
   "2.1 to 3.0 bits per round" holds only for the sifted protocol with the illustrative (gamma, p) of Table 3.
3. **Ledger at the wrong round count.** Sec. 3.3 prices the 11 km run at the baseline's 2.4e6 rounds (6.2 Mbit, 4.5e4 x key).
   At your own 1.04e6 rounds it is 2.7 Mbit and 2.0e4 x the key; the abstract's "some 4e4" should follow.
4. **Seeds.** With Toeplitz hashing both the error-correction tag and privacy amplification need ~n-bit seeds, about two extra
   bits per round (the code counts both), not one, unless the tag uses a short-seed hash (polynomial / VHASH, as in the experiments).
5. **Threshold definitions differ.** Fan et al.'s V_min is where the continuous rate hits zero (ell > 0); yours is ell >= 3 n_s.
   The difference is negligible (the 11 km threshold is identical to three digits), but state the definition once.
6. **Baseline column is copied, not recomputed.** The code reproduces it 0.0003-0.0011 *lower* (0.8827 / 0.8788, 0.8681 / 0.8601,
   0.8619 / 0.8503). Against the code's baseline the headline gain at n = 1e10 is 0.8503 -> 0.8462 (0.0041), not 0.0046.
   For a 4-digit comparison, use one optimiser for both columns.
7. **Add the asymptote** (0.8570, 0.8383) and "share of finite-size excess recovered" (34-42 %) to Table 2: it makes your sentence
   "how much of that distance the Rényi bound recovers" quantitative.
8. **Naming.** As I read Tan et al.'s Theorem 1, max{eps_EA, eps_PA + 2 eps_s} + 2 eps_h is the *soundness* eps_cor + eps_sec, not eps_sec alone. The code
   uses it as the budget eps_snd either way, so no number changes.
9. **Budget split is shallow.** The best split is eps_snd/eps = 0.3 (n = 1e9, V = 0.95: +2 % over the Table-I split of 0.5) and 0.7
   (11 km, n = 3e6: +3 %). n_s moves only 45 -> 51 over eps_snd/eps = 0.01 -> 0.99, while at 0.01 the key layer loses a third of
   its bits (11 km: ell = 9.6e4 vs 1.42e5 at the Table-I split): support for "moving budget changes n_s only logarithmically".

## 3. Running it

    python -m pytest -q                              # 59 fast tests; "python -m" matters (see README)
    python -m pytest -q -m slow                      # paper-number regressions (~8 min)
    python scripts/reproduce_paper_tables.py         # regenerates PAPER_TABLES.md
