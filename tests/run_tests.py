"""
PhyloCraft Master Test Suite Runner.

Usage:
    python tests/run_tests.py             # Run fast core unit and defense tests
    python tests/run_tests.py --gui       # Run GUI smoke & dialog tests
    python tests/run_tests.py --all       # Run all tests (unit + gui + benchmarks)
"""

import sys
import time
import argparse
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent

UNIT_TESTS = [
    "test_gene_extractor.py",
    "test_deep_defense_audit.py",
    "test_deep_edge_cases.py",
    "test_scratch_architecture.py",
    "test_stability_bughunt.py",
]

GUI_TESTS = [
    "test_gui_smoke.py",
    "test_interactive_ui.py",
    "test_interactive_gene_dialog.py",
    "test_ncbi_gene_tab.py",
]

BENCHMARK_TESTS = [
    "test_full_taxa_benchmarks.py",
    "test_master_system_audit.py",
    "test_multi_paper_replication.py",
    "test_paper_benchmark_replication.py",
]


def run_test_file(test_file: str) -> tuple[bool, float, str]:
    target = TESTS_DIR / test_file
    if not target.exists():
        return False, 0.0, f"File not found: {target}"

    start = time.time()
    res = subprocess.run(
        [sys.executable, str(target)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = time.time() - start
    output = (res.stdout or "") + (res.stderr or "")
    return (res.returncode == 0), elapsed, output


def main():
    parser = argparse.ArgumentParser(description="PhyloCraft Test Suite Runner")
    parser.add_argument("--gui", action="store_true", help="Run GUI smoke tests")
    parser.add_argument("--benchmarks", action="store_true", help="Run long benchmark replication tests")
    parser.add_argument("--all", action="store_true", help="Run all available tests")
    args = parser.parse_args()

    selected_tests = []
    if args.all:
        selected_tests = UNIT_TESTS + GUI_TESTS + BENCHMARK_TESTS
    elif args.gui:
        selected_tests = GUI_TESTS
    elif args.benchmarks:
        selected_tests = BENCHMARK_TESTS
    else:
        # Default: fast unit & defense tests
        selected_tests = UNIT_TESTS

    print("=" * 65)
    print(f"🌿 PhyloCraft Test Suite — Running {len(selected_tests)} test modules")
    print("=" * 65)

    passed = 0
    failed = 0

    for tf in selected_tests:
        print(f"\n▶ Running: {tf} ... ", end="", flush=True)
        ok, elapsed, out = run_test_file(tf)
        if ok:
            print(f"✅ PASSED ({elapsed:.2f}s)")
            passed += 1
        else:
            print(f"❌ FAILED ({elapsed:.2f}s)")
            failed += 1
            print("-" * 50)
            print(out[-1000:])
            print("-" * 50)

    print("\n" + "=" * 65)
    if failed == 0:
        print(f"🎉 ALL {passed} TESTS PASSED SUCCESSFULLY!")
    else:
        print(f"⚠️ {failed} tests failed out of {passed + failed} total tests.")
    print("=" * 65)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
