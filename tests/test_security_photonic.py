import math
import pytest
from diqds.photonic import (acquisition_hours, channel_efficiency, heralded_state, hom_visibility_local,
                            hom_visibility_remote, max_chsh, max_chsh_pure_formula)
from diqds.quantum import werner_state
from diqds.security import (QDSParams, choose_n_s, eps_forgery, eps_robustness, eps_total, num_signatures,
                            signature_rate)


def test_table_I_gives_n_s_46():
    p = QDSParams()
    ns = choose_n_s(p)
    assert ns == 46
    assert eps_forgery(ns, p.n_m, p.eps_snd) <= p.eps < eps_forgery(ns - 1, p.n_m, p.eps_snd)
    assert eps_total(ns, p) <= p.eps
    assert eps_robustness(p.eps_corr, p.eps_cl) == pytest.approx(2e-11, rel=1e-6)


def test_signature_rate_eq4():
    assert signature_rate(138_000, 46) == pytest.approx(1000.0)
    assert num_signatures(138_137, 46) == 1000 and signature_rate(-5, 46) == 0.0


def test_heralded_state_and_horodecki():
    for t in (0.5, 0.35, 0.2):
        for conv in ("printed", "derived"):
            assert max_chsh(heralded_state(t, conv)) == pytest.approx(max_chsh_pure_formula(t, conv), abs=1e-9)
    # the two readings of Eq. (D1) agree at t = 1/2 (the value used in the paper) and differ elsewhere
    assert max_chsh(heralded_state(0.5, "printed")) == pytest.approx(max_chsh(heralded_state(0.5, "derived")))
    assert max_chsh(heralded_state(0.3, "printed")) != pytest.approx(max_chsh(heralded_state(0.3, "derived")), abs=1e-3)
    assert max_chsh(werner_state(0.9)) == pytest.approx(2 * math.sqrt(2) * 0.9, abs=1e-9)


def test_hom_models_and_bookkeeping():
    assert hom_visibility_remote(1.0, 0.3, 1e-4) == pytest.approx(hom_visibility_local(1.0, 0.3), rel=1e-6)
    assert hom_visibility_remote(1.0, 0.3, 0.5) < hom_visibility_local(1.0, 0.3)
    assert acquisition_hours(1e14, 75e6) == pytest.approx(370.4, abs=0.1)     # paper: ~370 h
    assert channel_efficiency(0) == pytest.approx(0.5)
