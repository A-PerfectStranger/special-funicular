"""Verify a narrow docs-only diff before skipping builds or deployment."""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


def documentation_only(paths: list[str]) -> bool:
    return bool(paths) and all(
        path in {"README.md", "PLAN.md", "PROGRESS.md"}
        or (path.startswith("docs/runbooks/") and path.endswith(".md"))
        for path in paths
    )


def changes(base: str, head: str) -> list[str]:
    if not all(re.fullmatch(r"[0-9a-f]{40}", ref) and ref != "0" * 40 for ref in [base, head]):
        raise ValueError("Exact existing commits required")
    subprocess.run(["git", "merge-base", "--is-ancestor", base, head], check=True)
    raw = subprocess.check_output(["git", "diff", "--name-only", "-z", base, head])
    return [value.decode() for value in raw.split(b"\0") if value]


def validate_report(report: dict[str, Any], head: str) -> bool:
    if report.get("sha") != head or type(report.get("docs_only")) is not bool:
        raise ValueError("Scope artifact belongs to another candidate")
    actual = changes(report["base"], head)
    if actual != report.get("paths"):
        raise ValueError("Scope artifact does not match the committed diff")
    if report["docs_only"] and not documentation_only(actual):
        raise ValueError("Code changes cannot bypass release checks")
    return bool(report["docs_only"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["ci", "cd"])
    parser.add_argument("--base", default="")
    parser.add_argument("--head", required=True)
    parser.add_argument("--event", default="")
    parser.add_argument("--report", type=Path, default=Path("work/release-scope.json"))
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.head):
        raise ValueError("Immutable candidate required")
    if args.mode == "ci":
        paths = []
        # Dispatch, schedule and an initial branch push always require full builds.
        if args.event in {"push", "pull_request"} and args.base != "0" * 40:
            paths = changes(args.base, args.head)
        report = {
            "sha": args.head,
            "base": args.base,
            "paths": paths,
            "docs_only": documentation_only(paths),
        }
        args.report.parent.mkdir(exist_ok=True)
        args.report.write_text(json.dumps(report) + "\n")
        docs_only = report["docs_only"]
    else:
        report = json.loads(args.report.read_text())
        # Full releases include initial push/dispatch; only a proposed skip needs
        # proof of ancestry and a diff of this exact successful main candidate.
        docs_only = validate_report(report, args.head) if report.get("docs_only") else False
        if report.get("sha") != args.head or type(report.get("docs_only")) is not bool:
            raise ValueError("Invalid release scope")
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as stream:
        stream.write("docs_only=" + str(docs_only).lower() + "\n")
    print(
        "Verified documentation-only change; no software deployment"
        if docs_only
        else "Full software validation and release required"
    )


if __name__ == "__main__":
    main()
