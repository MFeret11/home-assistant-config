"""
Master Test Suite Runner for Basement & Theater Engines
Executes all unit, simulation, and database replay suites in clean isolated processes.
Run: python3 ~/ha_config/tests/run_all_tests.py
"""
import subprocess
import sys
import os
import time
import re

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PYSCRIPT_DIR = os.path.abspath(os.path.join(TESTS_DIR, "..", "pyscript"))
if not os.path.exists(PYSCRIPT_DIR):
    PYSCRIPT_DIR = os.path.expanduser("~/ha_config/pyscript")
if not os.path.exists(TESTS_DIR):
    TESTS_DIR = os.path.expanduser("~/ha_config/tests")

TEST_SUITES = [
    {
        "name": "State Machine, Safety Locks & Story Suite",
        "file": "test_theater_basement.py",
        "desc": "Unit tests, 3x3 state matrix, Cinema Shield, and 5-hour evening story"
    },
    {
        "name": "Real Hardware Telemetry Replay Suite",
        "file": "test_historical_replay.py",
        "desc": "Replays actual Optoma current curve, 22.7s slow descent & 18.8s slow ascent from DB"
    },
    {
        "name": "24-Hour Event Stream Replay Suite",
        "file": "test_full_day_replay.py",
        "desc": "Streams 1,260+ real physical events through the state engine"
    },
    {
        "name": "Multi-Dashboard Integrity & Defect Audit",
        "file": "test_dashboard_integrity.py",
        "desc": "Validates entity bindings, action syntax, and navigation paths across all dashboards"
    },
    {
        "name": "Transit & Commute Telemetry Contract Suite",
        "file": "test_commute_contract.py",
        "desc": "Validates FastAPI attributes, packages/commute.yaml, and kitchen Jinja templates"
    },
    {
        "name": "Dashboard Physical State & View Verification Suite",
        "file": "test_dashboard_automation.py",
        "desc": "Automated verification of dashboard sports scoreboard, Cinema Shield blackout, and hardware states"
    },
    {
        "name": "Preflight Health & Resilience Audit Suite",
        "file": "test_preflight_health.py",
        "desc": "Validates continuous integrity checks, critical entity health, and hardware state reconciliation"
    }
]

def run_suite():
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PYSCRIPT_DIR}:{env.get('PYTHONPATH', '')}"

    print("\n" + "=" * 75)
    print("       BASEMENT & THEATER AUTOMATED TEST HARNESS: FULL SUITE")
    print("=" * 75)

    suite_results = []
    total_start_time = time.time()
    all_passed = True

    for idx, suite in enumerate(TEST_SUITES, 1):
        script_path = os.path.join(TESTS_DIR, suite["file"])
        if not os.path.exists(script_path):
            print(f"\n[!] Skipping {suite['file']} (File not found)")
            continue

        print(f"\n[{idx}/{len(TEST_SUITES)}] RUNNING: {suite['name']}")
        print(f"    Target: {suite['file']}")
        print(f"    Scope:  {suite['desc']}")

        start_time = time.time()
        result = subprocess.run(
            [sys.executable, script_path],
            env=env,
            capture_output=True,
            text=True
        )
        duration_ms = (time.time() - start_time) * 1000

        # Dynamically extract test count if the script reports it
        display_name = suite["name"]
        match = re.search(r"ALL (\d+)/(\d+) SIMULATION TESTS PASSED", result.stdout)
        if match:
            display_name = f"{suite['name']} ({match.group(1)} Tests)"

        if result.returncode == 0:
            print(f"    STATUS: ✓ PASSED ({duration_ms:.1f} ms)")
            suite_results.append((display_name, True, duration_ms, ""))
        else:
            print(f"    STATUS: ❌ FAILED ({duration_ms:.1f} ms)")
            print("\n" + "-" * 60)
            print(result.stdout)
            print(result.stderr)
            print("-" * 60)
            suite_results.append((display_name, False, duration_ms, result.stdout + result.stderr))
            all_passed = False

    total_duration = (time.time() - total_start_time) * 1000

    # Executive Summary Card
    print("\n" + "=" * 75)
    print("                          EXECUTIVE TEST SCORECARD")
    print("=" * 75)
    for name, passed, dur, _ in suite_results:
        status_str = "✓ PASS" if passed else "❌ FAIL"
        print(f"  {status_str:<8} | {dur:6.1f} ms | {name}")

    print("-" * 75)
    if all_passed:
        print(f"  RESULT: ALL {len(suite_results)} SUITES PASSED CLEANLY (Total Time: {total_duration:.1f} ms)")
        print("=" * 75 + "\n")
        sys.exit(0)
    else:
        print(f"  RESULT: ONE OR MORE SUITES FAILED (Total Time: {total_duration:.1f} ms)")
        print("=" * 75 + "\n")
        sys.exit(1)

if __name__ == "__main__":
    run_suite()