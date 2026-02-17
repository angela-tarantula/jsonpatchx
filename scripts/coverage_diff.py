from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, cast


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def _coverage_json_for_repo(
    repo: Path, out_json: Path, *, pytest_args: list[str]
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cov-run-") as tmp:
        coverage_file = Path(tmp) / ".coverage"
        env = dict(os.environ)
        env["COVERAGE_FILE"] = str(coverage_file)
        _run(["uv", "run", "pytest", "-q", *pytest_args], cwd=repo, env=env)
        _run(
            ["uv", "run", "coverage", "json", "-o", str(out_json)],
            cwd=repo,
            env=env,
        )
    return cast(dict[str, Any], json.loads(out_json.read_text()))


def _file_pct(data: dict[str, Any], path: str) -> float:
    return float(data["files"][path]["summary"]["percent_covered"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report coverage differences between current workspace and a baseline git ref."
    )
    parser.add_argument(
        "--baseline",
        default="HEAD~1",
        help="Git ref to compare against (default: HEAD~1).",
    )
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]

    try:
        with tempfile.TemporaryDirectory(prefix="cov-diff-") as tmp:
            tmp_path = Path(tmp)
            baseline_wt = tmp_path / "baseline"
            current_json = tmp_path / "current_coverage.json"
            baseline_json = tmp_path / "baseline_coverage.json"

            _run(
                ["git", "worktree", "add", "--detach", str(baseline_wt), args.baseline],
                cwd=repo,
            )
            try:
                pytest_args: list[str] = []
                cts_data = Path("tests/cts/tests.json")
                if (
                    not (repo / cts_data).exists()
                    or not (baseline_wt / cts_data).exists()
                ):
                    pytest_args.extend(
                        ["--ignore", "tests/integration/test_json_patch_rfc6902.py"]
                    )
                    print(
                        "note: skipping RFC6902 CTS integration test for coverage diff "
                        "(tests/cts/tests.json missing in at least one ref)."
                    )

                current_cov = _coverage_json_for_repo(
                    repo, current_json, pytest_args=pytest_args
                )
                baseline_cov = _coverage_json_for_repo(
                    baseline_wt, baseline_json, pytest_args=pytest_args
                )
            finally:
                _run(
                    ["git", "worktree", "remove", "--force", str(baseline_wt)],
                    cwd=repo,
                )
                shutil.rmtree(baseline_wt, ignore_errors=True)
    except subprocess.CalledProcessError as exc:
        print(
            "coverage diff could not be completed due to command failure "
            f"(exit {exc.returncode}): {' '.join(exc.cmd)}"
        )
        return

    current_total = float(current_cov["totals"]["percent_covered"])
    baseline_total = float(baseline_cov["totals"]["percent_covered"])
    total_delta = current_total - baseline_total

    print(f"baseline ref: {args.baseline}")
    print(
        f"total coverage: {baseline_total:.2f}% -> {current_total:.2f}% ({total_delta:+.2f}pp)"
    )

    base_files = set(baseline_cov["files"].keys())
    cur_files = set(current_cov["files"].keys())
    common_files = sorted(base_files & cur_files)

    drops: list[tuple[str, float]] = []
    gains: list[tuple[str, float]] = []
    for file_path in common_files:
        delta = _file_pct(current_cov, file_path) - _file_pct(baseline_cov, file_path)
        if delta < 0:
            drops.append((file_path, delta))
        elif delta > 0:
            gains.append((file_path, delta))

    if drops:
        print("\ncoverage drops:")
        for file_path, delta in sorted(drops, key=lambda x: x[1]):
            print(f"  {file_path}: {delta:+.2f}pp")
    else:
        print("\ncoverage drops: none")

    if gains:
        print("\ncoverage gains:")
        for file_path, delta in sorted(gains, key=lambda x: x[1], reverse=True):
            print(f"  {file_path}: {delta:+.2f}pp")

    added_files = sorted(cur_files - base_files)
    removed_files = sorted(base_files - cur_files)
    if added_files:
        print("\nnewly-covered files:")
        for file_path in added_files:
            print(f"  {file_path}")
    if removed_files:
        print("\nmissing-in-current files:")
        for file_path in removed_files:
            print(f"  {file_path}")


if __name__ == "__main__":
    main()
