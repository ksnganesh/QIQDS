"""The settings of scripts/plot_signature_rates.py are the ones printed in the paper's Figs. 3-7, and the robust p search works."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import plot_signature_rates as psr  # noqa: E402
from diqds.finite_key import maximize_key_length, maximize_key_length_over_p, werner_S_Q  # noqa: E402


def test_legend_values_of_figs_3_4_5():
    assert psr.FIG3_V == (1.0, 0.96, 0.92, 0.88)                       # Fig. 3 legend
    assert psr.FIG4_P == (0.0, 0.05, 0.10, 0.15)                       # Fig. 4 legend
    assert [(n, p) for n, p, _ in psr.FIG5] == [(1e10, 0.155), (1e9, 0.090), (1e8, 0.035)]   # Fig. 5 legend


def test_fig6_and_fig7_settings():
    assert [k for k, _, _ in psr.FIG6] == ["nadlinger", "zhang", "lu"]
    assert psr.FIG7_CUTS == {"ideal": {1e14: 111.46, 2e14: 126.53}, "real": {1e14: 17.82, 2e14: 28.87}}
    assert psr.FIG7_L0 == 22.0


def test_p_rule_passes_through_the_fig5_legend_points():
    for n, p in ((1e8, 0.035), (1e9, 0.090), (1e10, 0.155)):
        assert psr.p_opt_rule(n) == pytest.approx(p, abs=1e-12)
    assert psr.p_opt_rule(1e6) == 0.0 and psr.p_opt_rule(1e14) == 0.3     # clipped to [0, 0.3]


def test_outer_p_search_finds_a_key_where_p_zero_has_none():
    # n = 1e9: V_min(p = 0) = 0.8686 but V_min(optimised p) = 0.8601, so at V = 0.865 only p > 0 gives a key
    S, Q = werner_S_Q(0.865)
    kw = dict(key_weight=0.5, ec_model="sifted")
    ell0, _, _ = maximize_key_length(10 ** 9, S, Q, 0.0, **kw)
    ell, _, ex = maximize_key_length_over_p(10 ** 9, S, Q, **kw)
    assert ell0 <= 0 < ell
    assert 0.03 < ex["p"] < 0.2
