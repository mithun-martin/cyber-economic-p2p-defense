# =====================================================================
# STEP 3 — MASTER OVERNIGHT RUNNER (Runs the full suite in sequence)
# =====================================================================
# Features:
#   1. Prevents Windows Laptop from going to sleep while training.
#   2. Chains training for Conv-AE v2 (Protocol A & Protocol B),
#      and optionally FC-AE benchmark replication.
#   3. Runs compare_results.py and make_figures.py (all 16 IEEE figures).
#   4. Saves all printed outputs to Step 3/outputs/overnight_run.log
#   5. Low RAM (< 600 MB) — 100% CPU safe, no GPU needed.
#
# Usage:
#   python "Step 3\run_all.py"          # runs Conv-AE v2 (Protocol A & B) + figures (~35 mins)
#   python "Step 3\run_all.py" --full   # also includes FC-AE baseline (~50 mins)
# =====================================================================

import argparse
import ctypes
import os
import subprocess
import sys
import time

STEP3_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(STEP3_DIR, "outputs", "overnight_run.log")
os.makedirs(os.path.join(STEP3_DIR, "outputs"), exist_ok=True)

# Windows API flags to prevent sleep
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def prevent_sleep():
    """Tells Windows not to sleep while this process is executing."""
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        print("[Power] Sleep prevention ACTIVE: Windows will stay awake until finished.")
    except Exception as e:
        print(f"[Power] Note: Could not set execution state ({e}), keep lid open.")


def restore_sleep():
    """Allows Windows to return to normal sleep settings when done."""
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        print("[Power] Sleep settings restored to normal.")
    except Exception:
        pass


def run_command(cmd_args, log_f):
    script_name = cmd_args[0]
    script_path = os.path.join(STEP3_DIR, script_name)
    full_cmd = [sys.executable, "-u", script_path] + cmd_args[1:]
    cmd_str = " ".join([script_name] + cmd_args[1:])

    banner = f"\n{'=' * 75}\n[STARTING] {cmd_str} at {time.strftime('%Y-%m-%d %H:%M:%S')}\n{'=' * 75}\n"
    print(banner, flush=True)
    log_f.write(banner)
    log_f.flush()

    t0 = time.time()
    proc = subprocess.Popen(
        full_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace"
    )

    for line in proc.stdout:
        print(line, end="", flush=True)
        log_f.write(line)
        log_f.flush()

    proc.wait()
    duration = (time.time() - t0) / 60.0

    if proc.returncode != 0:
        err_msg = f"\n[ERROR] {cmd_str} failed with return code {proc.returncode} after {duration:.2f} mins.\n"
        print(err_msg, flush=True)
        log_f.write(err_msg)
        log_f.flush()
        return False

    success_msg = f"\n[FINISHED] {cmd_str} successfully in {duration:.2f} mins.\n"
    print(success_msg, flush=True)
    log_f.write(success_msg)
    log_f.flush()
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Include FC-AE benchmark model replication")
    args = parser.parse_args()

    prevent_sleep()

    commands = [
        # --- 1. Conv-AE v2 (Protocol A: Realistic temporal split) ---
        ["local_baseline_299.py", "--model", "conv2", "--protocol", "A"],
        ["federated_train_299.py", "--model", "conv2", "--protocol", "A"],
        ["centralized_train.py", "--model", "conv2", "--protocol", "A"],

        # --- 2. Conv-AE v2 (Protocol B: Benchmark-matched balanced split) ---
        ["local_baseline_299.py", "--model", "conv2", "--protocol", "B"],
        ["federated_train_299.py", "--model", "conv2", "--protocol", "B"],
        ["centralized_train.py", "--model", "conv2", "--protocol", "B"],
    ]

    if args.full:
        # --- 3. FC-AE benchmark replication (Protocol B) ---
        commands.extend([
            ["local_baseline_299.py", "--model", "fcae", "--protocol", "B"],
            ["federated_train_299.py", "--model", "fcae", "--protocol", "B"],
            ["centralized_train.py", "--model", "fcae", "--protocol", "B"],
        ])

    # --- 4. Final Evaluation & All IEEE Figures ---
    commands.extend([
        ["compare_results.py"],
        ["make_figures.py"]
    ])

    total_start = time.time()
    with open(LOG_FILE, "a", encoding="utf-8") as log_f:
        header = f"\n{'#' * 75}\nSTEP 3 PIPELINE RUN STARTED: {time.strftime('%Y-%m-%d %H:%M:%S')}\n" \
                 f"Mode: {'Full (Conv-AE v2 + FC-AE)' if args.full else 'Standard (Conv-AE v2 Protocol A & B)'}\n" \
                 f"{'#' * 75}\n"
        print(header, flush=True)
        log_f.write(header)
        log_f.flush()

        for cmd in commands:
            success = run_command(cmd, log_f)
            if not success:
                print(f"[ABORT] Execution stopped due to error in {' '.join(cmd)}.")
                break

        total_mins = (time.time() - total_start) / 60.0
        footer = f"\n{'#' * 75}\nALL STEP 3 PIPELINE JOBS COMPLETED in {total_mins:.2f} minutes!\n" \
                 f"Log saved to: {LOG_FILE}\n{'#' * 75}\n"
        print(footer, flush=True)
        log_f.write(footer)

    restore_sleep()


if __name__ == "__main__":
    main()
