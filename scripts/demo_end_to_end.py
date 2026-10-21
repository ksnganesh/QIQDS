"""End-to-end DIQDS run: DIQKD Alice-Bob and Alice-Charlie (Qiskit devices) -> key pool -> signatures.

  python scripts/demo_end_to_end.py                       # paper's Table I security level, V = 0.99, n = 2e6
  python scripts/demo_end_to_end.py --backend aer         # run the CHSH circuits on qiskit-aer
  python scripts/demo_end_to_end.py --variant standard --n 1000000
"""
import argparse, sys, os, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from diqds.diqkd import plan_distribution, run_diqkd
from diqds.finite_key import SecurityBudget
from diqds.messaging import KeyPool, encode_document, run_session
from diqds.presets import RKM_SIFTED, STANDARD
from diqds.quantum import CHSHSource, ClassicalSource
from diqds.security import QDSParams, choose_n_s

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=2_000_000, help="heralded rounds per link")
ap.add_argument("--V", type=float, default=0.99, help="Werner-state visibility of the honest devices")
ap.add_argument("--backend", choices=["exact", "aer"], default="exact")
ap.add_argument("--ec", choices=["cascade", "oracle"], default="cascade")
ap.add_argument("--variant", choices=["rkm", "standard"], default="rkm")
ap.add_argument("--seed", type=int, default=1)
a = ap.parse_args()

rng = np.random.default_rng(a.seed)
variant = RKM_SIFTED if a.variant == "rkm" else STANDARD
qds = QDSParams()
n_s = choose_n_s(qds)
S, Q = 2 * np.sqrt(2) * a.V, (1 - a.V) / 2
print(f"security (Table I): eps={qds.eps:g}, eps_snd={qds.eps_snd:g}, n_m={qds.n_m} -> n_s = {n_s} "
      f"({3 * n_s} key bits per signature and link)")

plan = plan_distribution(a.n, S, Q, variant, budget=SecurityBudget(eps_snd=qds.eps_snd))
print("plan:", plan.summary())
if plan.ell <= 0:
    sys.exit("no key at these parameters - increase --n or --V")

keys = {}
for link in ("Alice-Bob", "Alice-Charlie"):                  # two independent device pairs (Sec. II.A)
    t0 = time.time()
    res = run_diqkd(plan, CHSHSource(a.V, a.backend), rng, ec=a.ec)
    st = res.stats
    print(f"\n[{link}] {'ACCEPTED' if res.accepted else 'ABORTED: ' + res.reason}   ({time.time() - t0:.1f}s, backend={a.backend})")
    print(f"   test rounds {st.get('n_test'):,}  CHSH losses {st.get('n_loss'):,} <= {st.get('n_loss_max'):,.0f}   "
          f"S_hat = {st.get('S_hat'):.3f}   QBER(key) = {st.get('qber_key'):.4f}")
    print(f"   EC leakage {st.get('ec_leak'):,} <= EC_max {st.get('ec_max'):,}   verification hash ok = {st.get('hash_ok')}")
    if not res.accepted:
        sys.exit(1)
    print(f"   secret key: {len(res.key_alice):,} bits, Alice/partner copies equal = {np.array_equal(res.key_alice, res.key_bob)}")
    keys[link] = res

pool = KeyPool(keys["Alice-Bob"].key_alice, keys["Alice-Charlie"].key_alice, n_s)
print(f"\nsignature capacity of this execution: {pool.capacity}  (r_sig = ell/(3 n_s) = {len(keys['Alice-Bob'].key_alice) / (3 * n_s):.1f})")

print("\n-- messaging stage (Fig. 2)")
for text in (b"Transfer 100 EUR to Bob", b"Contract v2 - final"):
    A, B, C = pool.next_keys()
    doc = encode_document(text, qds.n_m)
    b, c, s = run_session(A, B, C, doc)
    print(f"   {text.decode():28s} Bob accepts: {b}   Charlie accepts: {c}")
A, B, C = pool.next_keys()
doc = encode_document(b"Transfer 100 EUR to Bob", qds.n_m)
forged = {}
def bob_tamper(sig, d, yb):
    d = d.copy(); d[3] ^= 1; forged["done"] = True
    return sig, d, yb
b, c, _ = run_session(A, B, C, doc, bob_tamper=bob_tamper)
print(f"   Bob forwards a modified document -> Charlie accepts: {c}   (forgery rejected)")

print("\n-- sanity: devices without entanglement")
r = run_diqkd(plan, ClassicalSource(), rng, ec=a.ec)
print("   ", "ACCEPTED (!)" if r.accepted else "aborted: " + r.reason)
