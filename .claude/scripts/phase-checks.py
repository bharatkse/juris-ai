#!/usr/bin/env python3
"""Run the phase-report checks and print the checks table + changed files.

Used by the /phase-report command. Runs, from the repo root:

  lint   make lint          (ruff)
  mypy   make type-check
  unit   make test-unit
  smoke  make test-smoke    (needs the dependency containers)
  e2e    make test-e2e      (needs the dependency containers)

and compares pass/fail counts with the previous run, stored in
.git/claude-phase-baseline.json (never shows up in git status). Full logs go
to .git/claude-phase-logs/<check>.log.

  --only lint,mypy     run a subset (the others show as "not run")
  --keep-baseline      don't overwrite the baseline with this run
"""

import argparse
import datetime
import json
import re
import subprocess
import sys
import time
from pathlib import Path

CHECKS = {
    "lint": ["make", "lint"],
    "mypy": ["make", "type-check"],
    "unit": ["make", "test-unit"],
    "smoke": ["make", "test-smoke"],
    "e2e": ["make", "test-e2e"],
}
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# Docs that must change in the same change as the code they describe
SYNCED_DOCS = [
    "docs/server/architecture/api.md",
    "server/src/agentic/orchestration/README.md",
    "server/src/agentic/README.md",
    "README.md",
]
PYTEST_KINDS = ("passed", "failed", "errors", "skipped", "xfailed", "xpassed")


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


def parse_pytest(out):
    summary = [line for line in out.splitlines() if re.match(r"=+ .* in [\d.]+s", line)]
    counts = {}
    if summary:
        for n, kind in re.findall(r"(\d+) (\w+)", summary[-1]):
            kind = "errors" if kind == "error" else kind
            if kind in PYTEST_KINDS:
                counts[kind] = int(n)
    return counts


def parse(check, out):
    if check == "lint":
        m = re.search(r"Found (\d+) errors?", out)
        return {"errors": int(m.group(1)) if m else 0}
    if check == "mypy":
        m = re.search(r"Found (\d+) errors? in \d+ files? \(checked (\d+) source", out)
        if m:
            return {"errors": int(m.group(1)), "files": int(m.group(2))}
        m = re.search(r"no issues found in (\d+) source files", out)
        return {"errors": 0, "files": int(m.group(1))} if m else {}
    return parse_pytest(out)


def describe(check, result):
    counts = result["counts"]
    if check == "lint":
        return "clean" if not counts.get("errors") else f"{counts['errors']} errors"
    if check == "mypy":
        files = f" ({counts['files']} files)" if "files" in counts else ""
        return f"{counts.get('errors', '?')} errors{files}"
    if not counts:
        return "no pytest summary (see log)"
    return ", ".join(f"{counts[k]} {k}" for k in PYTEST_KINDS if counts.get(k))


def delta(check, now, before):
    if before is None or before.get("status") == "not run":
        return "no baseline"
    keys = ("errors",) if check in ("lint", "mypy") else ("passed", "failed", "errors")
    parts = []
    for key in keys:
        diff = now["counts"].get(key, 0) - before["counts"].get(key, 0)
        if diff:
            parts.append(f"{diff:+d} {key}")
    return ", ".join(parts) or "±0"


def changed_files(root):
    tracked = git("-C", root, "diff", "HEAD", "--name-status").splitlines()
    untracked = git(
        "-C", root, "ls-files", "--others", "--exclude-standard"
    ).splitlines()
    rows = [line.split("\t", 1) for line in tracked if "\t" in line]
    rows += [["??", path] for path in untracked]
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default=",".join(CHECKS))
    parser.add_argument("--keep-baseline", action="store_true")
    opts = parser.parse_args()
    selected = [c.strip() for c in opts.only.split(",") if c.strip()]
    unknown = set(selected) - set(CHECKS)
    if unknown:
        sys.exit(f"unknown checks: {', '.join(sorted(unknown))}")

    root = git("rev-parse", "--show-toplevel").strip()
    git_dir = Path(root, git("-C", root, "rev-parse", "--git-dir").strip())
    baseline_path = git_dir / "claude-phase-baseline.json"
    log_dir = git_dir / "claude-phase-logs"
    log_dir.mkdir(exist_ok=True)
    try:
        baseline = json.loads(baseline_path.read_text())
    except (OSError, ValueError):
        baseline = None

    results = {}
    for check in CHECKS:
        if check not in selected:
            results[check] = {"status": "not run", "counts": {}}
            continue
        print(f"running {check}...", file=sys.stderr, flush=True)
        start = time.monotonic()
        proc = subprocess.run(CHECKS[check], cwd=root, capture_output=True, text=True)
        out = ANSI.sub("", proc.stdout + proc.stderr)
        (log_dir / f"{check}.log").write_text(out)
        results[check] = {
            "status": "pass" if proc.returncode == 0 else "FAIL",
            "counts": parse(check, out),
            "seconds": round(time.monotonic() - start),
        }

    base_checks = (baseline or {}).get("checks", {})
    base_label = (
        f"{baseline['taken'][:16]} @ {baseline['head'][:7]}" if baseline else "none"
    )
    print(f"### Checks (baseline: {base_label})\n")
    print("| Check | Command | Result | Counts | Δ vs baseline | Time |")
    print("|---|---|---|---|---|---|")
    for check, result in results.items():
        cmd = " ".join(CHECKS[check])
        if result["status"] == "not run":
            print(f"| {check} | `{cmd}` | not run | — | — | — |")
            continue
        print(
            f"| {check} | `{cmd}` | {result['status']} | {describe(check, result)} "
            f"| {delta(check, result, base_checks.get(check))} | {result['seconds']}s |"
        )
    failing = [c for c, r in results.items() if r["status"] == "FAIL"]
    if failing:
        logs = ", ".join(f"`.git/claude-phase-logs/{c}.log`" for c in failing)
        print(f"\nFailing: {', '.join(failing)} — logs: {logs}")

    rows = changed_files(root)
    docs = [r for r in rows if r[1].endswith(".md")]
    code = [r for r in rows if not r[1].endswith(".md")]
    print("\n### Changed files (working tree vs HEAD)\n")
    for label, group in (("Code/config", code), ("Docs", docs)):
        print(f"{label} ({len(group)}):")
        for status, path in group:
            print(f"- `{status}` {path}")
        if not group:
            print("- none")
    touched = {path for _, path in rows}
    code_touched = any(p.startswith("server/src/") for _, p in code)
    untouched = [d for d in SYNCED_DOCS if d not in touched]
    if code_touched and untouched:
        print(
            "\nDoc-sync check: server/src changed but these weren't touched — "
            "confirm each is still accurate: " + ", ".join(f"`{d}`" for d in untouched)
        )

    if not opts.keep_baseline:
        merged = dict(base_checks)
        merged.update({c: r for c, r in results.items() if r["status"] != "not run"})
        baseline_path.write_text(
            json.dumps(
                {
                    "taken": datetime.datetime.now().isoformat(timespec="minutes"),
                    "head": git("-C", root, "rev-parse", "HEAD").strip(),
                    "checks": merged,
                },
                indent=2,
            )
        )
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
