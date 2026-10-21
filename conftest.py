import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_HAS_QISKIT = importlib.util.find_spec("qiskit") is not None
_NEEDS_QISKIT = ["tests/test_quantum.py", "tests/test_diqkd.py", "tests/test_security_photonic.py",
                 "tests/test_randomness_budget.py"]
collect_ignore = [] if _HAS_QISKIT else _NEEDS_QISKIT


def pytest_report_header(config):
    lines = [f"python used by pytest: {sys.executable}"]
    if not _HAS_QISKIT:
        lines += ["WARNING: qiskit cannot be imported by this interpreter -> quantum/protocol tests are SKIPPED.",
                  "  Typical cause: a global `pytest` shadows the one in your virtual environment.",
                  "  Fix: run  python -m pytest  (uses the venv's python), or  python -m pip install -r requirements.txt"]
    return lines
