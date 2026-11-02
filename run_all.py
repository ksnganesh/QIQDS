"""Run EVERY computation of this repository from scratch, in order, and report which steps passed.

    python scripts/run_all.py                    # everything, from scratch (about 26 minutes on one core)
    python scripts/run_all.py --list             # show the steps, their commands and typical times
    python scripts/run_all.py --dry-run          # print the commands without running them
    python scripts/run_all.py --only tests demo  # a subset (step names from --list)
    python scripts/run_all.py --skip-slow        # leave out the nine slow regression tests (about 3 minutes)
    python scripts/run_all.py --quick            # coarser plot grids (the plots are the longest part)
    python scripts/run_all.py --resume           # after an interruption: skip the steps that already passed

Run it from inside the project folder (the one that contains diqds/ and scripts/); the file itself may sit in scripts/ or
in the project folder, it finds the project either way. If files or Python packages are missing it says so and stops.

Nothing is reused from earlier runs: the plot steps use --force (every curve is recomputed), every comparison part
overwrites its results/*.json, and COMPARISON.md and PAPER_TABLES.md are rewritten from those fresh numbers.
Each step's output is saved in logs/NN_name.log (look there with `tail -f` while a step runs); a summary table is printed
at the end, and the exit status is 1 if any step failed.
"""
import argparse
import json
import os
import subprocess
import sys
import time



def find_root():
    """The project folder: the nearest folder above this file (or above the current folder) that holds diqds/ and scripts/."""
    for start in (os.path.dirname(os.path.abspath(__file__)), os.getcwd()):
        d = start
        while True:
            if os.path.isdir(os.path.join(d, "diqds")) and os.path.isdir(os.path.join(d, "scripts")):
                return d
            if os.path.dirname(d) == d:
                break
            d = os.path.dirname(d)
    sys.exit("run_all.py: cannot find the project folder (the one that contains diqds/ and scripts/).\n"
             "Run it from inside the project folder, e.g.  cd <your project folder>  and  python scripts/run_all.py")


ROOT = find_root()


# (name, arguments after the python interpreter, file that receives stdout or None, typical seconds, what it does)
STEPS = [
    ("tests", ["-m", "pytest", "-q"], None, 34, "67 fast tests"),
    ("demo", ["scripts/demo_end_to_end.py"], None, 5, "end-to-end signature run (exact simulator)"),
    ("demo-aer", ["scripts/demo_end_to_end.py", "--backend", "aer"], None, 7, "the same on qiskit-aer"),
    ("demo-standard", ["scripts/demo_end_to_end.py", "--variant", "standard", "--n", "1000000"], None, 3,
     "the no-sifting protocol variant"),
    ("fig6-claims", ["scripts/reproduce_fig6_claims.py"], None, 32, "which published experiments are feasible"),
    ("thresholds", ["scripts/reproduce_thresholds.py"], None, 87, "Fig. 5 minimum visibilities"),
    ("plot-fig3", ["scripts/plot_signature_rates.py", "--which", "fig3", "--force"], None, 90, "Fig. 3, recomputed"),
    ("plot-fig4", ["scripts/plot_signature_rates.py", "--which", "fig4", "--force"], None, 210, "Fig. 4, recomputed"),
    ("plot-fig5", ["scripts/plot_signature_rates.py", "--which", "fig5", "--force"], None, 240, "Fig. 5, recomputed"),
    ("plot-fig6", ["scripts/plot_signature_rates.py", "--which", "fig6", "--force"], None, 55, "Fig. 6, recomputed"),
    ("plot-fig7", ["scripts/plot_signature_rates.py", "--which", "fig7", "--force"], None, 290, "Fig. 7, recomputed"),
    ("figure-check", ["scripts/compare_figure_readings.py"], None, 2, "curves vs numbers read off the printed figures"),
    ("cmp-thr-1e8", ["scripts/compare_with_paper.py", "--part", "thresholds", "--n", "1e8"], None, 21, "Fig. 5, n = 1e8"),
    ("cmp-thr-1e9", ["scripts/compare_with_paper.py", "--part", "thresholds", "--n", "1e9"], None, 36, "Fig. 5, n = 1e9"),
    ("cmp-thr-1e10", ["scripts/compare_with_paper.py", "--part", "thresholds", "--n", "1e10"], None, 48, "Fig. 5, n = 1e10"),
    ("cmp-fig4a", ["scripts/compare_with_paper.py", "--part", "fig4a"], None, 48, "Fig. 4: threshold for fixed p"),
    ("cmp-fig4b", ["scripts/compare_with_paper.py", "--part", "fig4b"], None, 48, "Fig. 4: rate for fixed p"),
    ("cmp-fig3", ["scripts/compare_with_paper.py", "--part", "fig3"], None, 36, "Fig. 3: n_min and slope"),
    ("cmp-fig6", ["scripts/compare_with_paper.py", "--part", "fig6"], None, 34, "Fig. 6: the three experiments"),
    ("cmp-misc", ["scripts/compare_with_paper.py", "--part", "misc"], None, 9, "Table I, message length, completeness"),
    ("cmp-photonic", ["scripts/compare_with_paper.py", "--part", "photonic"], None, 8, "Fig. 7 consistency estimate"),
    ("cmp-report", ["scripts/compare_with_paper.py", "--report"], "COMPARISON.md", 1, "writes COMPARISON.md"),
    ("paper-tables", ["scripts/reproduce_paper_tables.py"], "PAPER_TABLES.md", 54, "writes PAPER_TABLES.md"),
    ("slow-tests", ["-m", "pytest", "-q", "-m", "slow"], None, 169, "9 slow regression tests"),
]


def preflight(steps, env):
    """Stop early, with one clear message, if the project files or the Python packages are not what the steps need."""
    missing = sorted({args[0] for _, args, _, _, _ in steps
                      if args[0].endswith(".py") and not os.path.isfile(os.path.join(ROOT, args[0]))})
    if missing:
        sys.exit("missing files: " + ", ".join(missing) + "\nUnzip QIQDS_readme_and_fixes.zip over the project folder "
                 "(or `git pull`), then run this again.")
    probe = subprocess.run([sys.executable, "-c", "import numpy, scipy, matplotlib, qiskit, pytest"],
                           cwd=ROOT, env=env, capture_output=True, text=True)
    if probe.returncode != 0:
        last = (probe.stderr.strip().splitlines() or ["import failed"])[-1]
        sys.exit(f"Python packages are missing for {sys.executable}:\n  {last}\n"
                 "Activate the virtual environment and install them:  python -m pip install -r requirements.txt")
    plot = os.path.join(ROOT, "scripts", "plot_signature_rates.py")
    if any(args[0] == "scripts/plot_signature_rates.py" for _, args, _, _, _ in steps):
        helptext = subprocess.run([sys.executable, plot, "--help"], cwd=ROOT, env=env, capture_output=True, text=True).stdout
        if "--force" not in helptext:
            sys.exit("scripts/plot_signature_rates.py is an older version (it has no --force option).\n"
                     "Unzip QIQDS_readme_and_fixes.zip over the project folder, then run this again.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--list", action="store_true", help="show the steps and exit")
    ap.add_argument("--dry-run", action="store_true", help="print the commands without running them")
    ap.add_argument("--only", nargs="+", metavar="STEP", help="run only these steps (names from --list)")
    ap.add_argument("--skip-slow", action="store_true", help="leave out the slow regression tests")
    ap.add_argument("--quick", action="store_true", help="coarser grids for the plot steps")
    ap.add_argument("--resume", action="store_true", help="skip the steps that passed in an earlier, interrupted run")
    ap.add_argument("--logdir", default="logs", help="folder for the per-step logs (default: logs)")
    a = ap.parse_args()

    steps = [list(s) for s in STEPS]
    names = [s[0] for s in steps]
    if a.only:
        unknown = [n for n in a.only if n not in names]
        if unknown:
            sys.exit(f"unknown step(s): {', '.join(unknown)}  (see --list)")
        steps = [s for s in steps if s[0] in a.only]
    if a.skip_slow:
        steps = [s for s in steps if s[0] != "slow-tests"]
    if a.quick:
        for s in steps:
            if s[0].startswith("plot-"):
                s[1] = s[1] + ["--quick"]
    n = len(steps)
    total = sum(s[3] for s in steps)

    if a.list:
        for i, (name, args, out, secs, what) in enumerate(STEPS, 1):
            print(f"{i:2d}. {name:<14} ~{secs:>3d} s  python {' '.join(args)}" + (f" > {out}" if out else "") + f"   # {what}")
        print(f"\ntotal about {sum(s[3] for s in STEPS) / 60:.0f} minutes on one core")
        return 0

    logdir = os.path.join(ROOT, a.logdir)
    state_path = os.path.join(logdir, "run_all_state.json")
    passed = set()
    if a.resume and os.path.exists(state_path):
        passed = set(json.load(open(state_path)).get("passed", []))
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    if not a.dry_run:
        preflight(steps, env)
        os.makedirs(logdir, exist_ok=True)
        print(f"{n} steps, about {total / 60:.0f} minutes on one core; logs in {a.logdir}/ "
              f"(a '.' every 30 s means the step is still running)\n", flush=True)

    results, t_all = [], time.time()
    for i, (name, args, out, secs, what) in enumerate(steps, 1):
        cmd = [sys.executable] + args
        head = f"[{i:2d}/{n}] {name:<14}"
        if a.dry_run:
            print(head, " ".join(["python"] + args) + (f" > {out}" if out else ""))
            continue
        if name in passed:
            print(head, "skipped (passed earlier, --resume)", flush=True)
            results.append((name, "skipped", 0.0, None))
            continue
        log = os.path.join(logdir, f"{i:02d}_{name}.log")
        tmp_out = os.path.join(logdir, f"{name}.stdout.tmp") if out else None
        print(head, end=" ", flush=True)
        t0 = time.time()
        with open(log, "wb") as lf:
            stdout = open(tmp_out, "wb") if out else lf
            proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=stdout, stderr=lf if out else subprocess.STDOUT)
            while True:
                try:
                    rc = proc.wait(timeout=30)
                    break
                except subprocess.TimeoutExpired:
                    print(".", end="", flush=True)
            if out:
                stdout.close()
        secs_used = time.time() - t0
        if out:
            if rc == 0:
                os.replace(tmp_out, os.path.join(ROOT, out))
            else:
                os.remove(tmp_out)
        ok = rc == 0
        print(f"{'ok' if ok else 'FAILED (exit ' + str(rc) + ')'}  {secs_used:.0f} s" + ("" if ok else f"   -> see {a.logdir}/{os.path.basename(log)}"),
              flush=True)
        results.append((name, "ok" if ok else "FAILED", secs_used, log))
        if ok:
            passed.add(name)
            json.dump({"passed": sorted(passed)}, open(state_path, "w"))

    if a.dry_run:
        return 0
    failed = [r for r in results if r[1] == "FAILED"]
    print(f"\n{len(results) - len(failed)} of {len(results)} steps ok, {len(failed)} failed, "
          f"{(time.time() - t_all) / 60:.1f} minutes")
    for name, status, secs_used, log in failed:
        print(f"  FAILED: {name}  (log: {os.path.relpath(log, ROOT)})")
    if not failed and a.only:
        print("All selected steps passed.")
    elif not failed:
        print("ALL STEPS PASSED. Results: results/*.json, results/curves/*.json, fig3_like.png ... fig7_like.png, "
              "COMPARISON.md, PAPER_TABLES.md")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
