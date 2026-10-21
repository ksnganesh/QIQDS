"""
diqds - device-independent quantum digital signatures (DIQDS), reimplemented from
Fan, Bian, Li, Wen, Yin, Chen, Phys. Rev. A 114, 032617 (2026).

  finite_key      Eq. (9)/(B1-B12): finite-size secret-key length (entropy accumulation) + optimiser
  security        Eqs. (4)-(8): composable security bounds, n_s, signature rate
  presets         protocol variants + parameters of the matter-qubit experiments the paper simulates
  experiments     signature rates, minimum rounds, Fig. 6-style feasibility reports
  quantum         Qiskit models of the honest devices (Werner state, CHSH circuits; exact and Aer back ends)
  diqkd           distribution stage, steps 1-7 (acquisition ... privacy amplification)
  error_correction  Cascade reconciliation and an oracle model
  gf2, hashing    GF(2)[x] arithmetic, LFSR-based Toeplitz hash (App. A), FFT Toeplitz 2-universal hash
  messaging       messaging stage: Alice signs, Bob verifies, Charlie certifies (Fig. 2)
  photonic        App. C/D helpers (HOM visibility, heralded state, channel)
  randomness      randomness ledger (Eq. 5, Table 3 of the follow-up paper), supply check, run-time bit counter
  renyi_bound     scaffold for the tightened Renyi-accumulation bound, Eq. (2) -- not implemented
"""
__version__ = "0.1.0"
