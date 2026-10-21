## Sec. 3.2  signature layer: n_s from Eq. (4)  (eps = 1e-10, n_m = 1000)

| eps_snd | n_s (code) | paper | 3 n_s |
|---|---|---|---|
| 1.0e-11 | 45 | 45 | 135 |
| 5.0e-11 | 46 | 46 | 138 |
| 9.0e-11 | 48 | 48 | 144 |
| 9.9e-11 | 51 | 51 | 153 |

n_m = 1e6: n_s = 56 (paper: 56)

## Table 3  private random bits per heralded round (Eq. 5; 16-bit thresholding sampler)

| gamma | p = 0 | p = 0.05 | p = 0.10 | p = 0.05, 16-bit sampler |
|---|---|---|---|---|
| 0.01 | 2.08 | 2.22 | 2.31 | 25.9 |
| 0.05 | 2.29 | 2.42 | 2.51 | 25.6 |
| 0.1 | 2.47 | 2.60 | 2.68 | 25.2 |
| 0.3 | 2.88 | 2.98 | 3.05 | 23.6 |

At gamma = 0.1, p = 0.05: 2.60 bits/round = Alice 1.13 + Bob 1.47.

| Run | rounds | total | x the 138-bit key | bit/s |
|---|---|---|---|---|
| ion run [73] | 1.5e+06 | 3.90 Mbit | 2.8e+04 | 137.02 |
| 11 km, baseline extrapolation | 2.4e+06 | 6.23 Mbit | 4.5e+04 | 1.40 |
| 11 km, tightened (paper's 1.04e6) | 1.04e+06 | 2.70 Mbit | 2e+04 | 1.40 |

Photonic link: nu * P_H * H_round = 0.19 Mbit/s at 75 MHz, P_H = 1e-3.

## Ledger at the optimiser's own (gamma, p)  (Table 3 uses an illustrative gamma = 0.1, p = 0.05)

| operating point | protocol | gamma | p | bits/round | total for the run |
|---|---|---|---|---|---|
| ion run [73], n = 1.5e6 | standard | 0.077 | 0.000 | 0.55 | 0.82 Mbit |
| 11 km [75], n = 3e6 | standard | 0.062 | 0.000 | 0.46 | 1.37 Mbit |
| Werner V = 0.95, n = 1e9 | rkm_sifted | 0.008 | 0.000 | 2.07 | 2.07e+03 Mbit |

## Table 2  threshold visibility V_min (baseline = EAT bound of Fan et al., sifted reading)

| n | p | paper baseline | this code (baseline) | asymptote | paper tightened |
|---|---|---|---|---|---|
| 1e8 | 0 | 0.8835 | 0.8827 | 0.8570 | 0.8719 |
| 1e8 | opt | 0.8799 | 0.8788 | 0.8383 | 0.8646 |
| 1e9 | 0 | 0.8686 | 0.8681 | 0.8570 | 0.8637 |
| 1e9 | opt | 0.8608 | 0.8601 | 0.8383 | 0.8526 |
| 1e10 | 0 | 0.8622 | 0.8619 | 0.8570 | 0.8600 |
| 1e10 | opt | 0.8508 | 0.8503 | 0.8383 | 0.8462 |

(Taken at face value, the paper's tightened column recovers this share of the baseline's finite-size excess over the asymptote: n = 1e8, p = 0: 42 %, n = 1e8, p = opt: 35 %, n = 1e9, p = 0: 40 %, n = 1e9, p = opt: 34 %, n = 1e10, p = 0: 39 %, n = 1e10, p = opt: 34 %. None of its values lies below the asymptote.)

## 11 km operating point (Lu et al.: S = 2.612, Q = 0.0285, 1.208e6 events in 624 h)

| baseline protocol | rounds for ell > 0 | rounds for ell >= 3 n_s = 138 | hours at 0.538 events/s |
|---|---|---|---|
| standard | 2.14e+06 | 2.14e+06 | 1107 |
| rkm_sifted | 5.5e+06 | 5.5e+06 | 2842 |

The paper's baseline cell is 'at most 2.4e6 rounds / 1248 h' (Fan et al.'s extrapolated point, no-sifting protocol).
The paper's 1.04e6 would be x2.06 fewer than the exact no-sifting baseline, x5.29 fewer than the exact sifted (random-key-basis) baseline.

## Budget split between key layer and hashing layer (eps = 1e-10, eps_EA = eps_PA = eps_snd/5)

**Werner V = 0.95, n = 1e9 (sifted)**

| eps_snd/eps | n_s | 3 n_s | ell | r_sig |
|---|---|---|---|---|
| 0.01 | 45 | 135 | 2.364e+08 | 1.751e+06 |
| 0.1 | 45 | 135 | 2.371e+08 | 1.757e+06 |
| 0.3 | 45 | 135 | 2.375e+08 | 1.76e+06 |  <- best
| 0.5 | 46 | 138 | 2.377e+08 | 1.723e+06 |
| 0.7 | 46 | 138 | 2.378e+08 | 1.724e+06 |
| 0.9 | 48 | 144 | 2.379e+08 | 1.652e+06 |
| 0.99 | 51 | 153 | 2.38e+08 | 1.555e+06 |

**11 km link, n = 3e6 (no-sifting)**

| eps_snd/eps | n_s | 3 n_s | ell | r_sig |
|---|---|---|---|---|
| 0.01 | 45 | 135 | 9.627e+04 | 713.1 |
| 0.1 | 45 | 135 | 1.229e+05 | 910 |
| 0.3 | 45 | 135 | 1.36e+05 | 1008 |
| 0.5 | 46 | 138 | 1.423e+05 | 1031 |
| 0.7 | 46 | 138 | 1.464e+05 | 1061 |  <- best
| 0.9 | 48 | 144 | 1.496e+05 | 1039 |
| 0.99 | 51 | 153 | 1.508e+05 | 985.3 |

## Where the baseline's finite-size penalty sits (percent of the gross entropy n g(omega_thr))

| point | Delta_EAT | second-order | test register n*gamma | alpha' terms | smoothing / acceptance | EC_max |
|---|---|---|---|---|---|---|
| V = 0.95, n = 1e9 | 7.2 | 2.2 | 2.2 | 0.4 | 2.5 | 25.5 |
| V = 0.87, n = 1e9 (near threshold) | 10.5 | 3.1 | 3.0 | 0.7 | 3.7 | 87.2 |
| 11 km, n = 3e6 | 47.3 | 14.9 | 11.1 | 4.4 | 17.0 | 44.1 |
