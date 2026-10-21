"""Fig. 5 / Sec. IV: minimum Werner visibility V for a positive signature, with and without noisy preprocessing.
Compares against the numbers printed in the paper.  Takes a few minutes (nested optimisation + bisection)."""
import argparse, sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from diqds.finite_key import min_visibility
from diqds.presets import RKM_SIFTED, STANDARD

PAPER = {  # n: (p = 0, optimised p)
    10 ** 8: (0.8835, 0.8799), 10 ** 9: (0.8686, 0.8608), 10 ** 10: (0.8622, 0.8508)}

ap = argparse.ArgumentParser()
ap.add_argument("--variant", choices=["rkm", "standard"], default="rkm",
                help="rkm = RKM+sifting (reproduces Fig. 3-5); standard = no-sifting protocol of Ref. [73]")
ap.add_argument("--tol", type=float, default=2e-4, help="bisection tolerance in V")
ap.add_argument("--skip-np", action="store_true", help="skip the (slower) optimised-p column")
ap.add_argument("--only", type=float, default=None, help="run a single row, e.g. --only 1e9")
a = ap.parse_args()
v = RKM_SIFTED if a.variant == "rkm" else STANDARD

print(f"variant = {v.name}  (key_weight={v.key_weight}, EC model={v.ec_model})")
print(f"{'n':>8} | {'V_min p=0':>10} {'paper':>7} {'diff':>7} | {'V_min p opt':>11} {'paper':>7} {'diff':>7}")
for n, (p0_paper, np_paper) in PAPER.items():
    if a.only is not None and int(a.only) != n:
        continue
    t0 = time.time()
    v0 = min_visibility(n, p=0.0, key_weight=v.key_weight, ec_model=v.ec_model, restarts=2, tol=a.tol)
    if a.skip_np:
        print(f"{n:8.0e} | {v0:10.4f} {p0_paper:7.4f} {v0 - p0_paper:+7.4f} |")
        continue
    vn = min_visibility(n, p=None, key_weight=v.key_weight, ec_model=v.ec_model, restarts=2, tol=a.tol)
    print(f"{n:8.0e} | {v0:10.4f} {p0_paper:7.4f} {v0 - p0_paper:+7.4f} | {vn:11.4f} {np_paper:7.4f} {vn - np_paper:+7.4f}"
          f"   [{time.time() - t0:.0f}s]")
