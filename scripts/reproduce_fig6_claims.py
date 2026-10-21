"""Fig. 6 / Sec. IV: minimum number of rounds and acquisition time for the three matter-qubit experiments the
paper simulates, under both protocol readings, next to the paper's statements."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from diqds.experiments import experiment_report
from diqds.presets import EXPERIMENTS, RKM_SIFTED, STANDARD
from diqds.security import choose_n_s

STATEMENTS = {
    "nadlinger": "paper: 1.5e6 rounds (~8 h) are within the acceptable range -> feasible",
    "zhang": "paper: would need 'on the order of 1e7 hours' (3342 rounds per 75 h)",
    "lu": "paper: more than the collected 1.2e6 rounds needed; positive at 2.4e6 (~1248 h)",
}
print(f"n_s = {choose_n_s()}  (Table I)")
for key, exp in EXPERIMENTS.items():
    print(f"\n{exp.name}\n   S={exp.S}, Q={exp.Q}, collected {exp.rounds:,.0f} rounds in {exp.hours:g} h\n   {STATEMENTS[key]}")
    for v in (STANDARD, RKM_SIFTED):
        r = experiment_report(exp, v)
        print(f"   [{v.name:10s}] n_min = {r['n_min']:>13,.0f}  -> {r['hours_needed']:>11,.0f} h at the experiment's rate;"
              f"  ell at collected n = {r['ell_at_collected']:>10,.0f}  ({'feasible' if r['feasible_with_collected'] else 'not enough rounds'})")
