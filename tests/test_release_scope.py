"""Documentation closure cannot hide code, contracts, workflow or deployment changes."""

import subprocess
from pathlib import Path

import pytest

from scripts.release_scope import documentation_only, validate_report


def test_only_explicit_nonruntime_documents_can_skip_builds() -> None:
    assert documentation_only(["PLAN.md", "PROGRESS.md", "README.md", "docs/runbooks/e3.md"])
    for path in [
        "apps/backend/config/settings.py",
        "tests/contracts/openapi.yaml",
        "infra/environments/staging.json",
        ".github/workflows/ci.yml",
        "AGENTS.md",
        "Requerimientos_retiro_seguro_estudiantes.md",
        "docs/runbooks/command.py",
        "docs/runbooks/../app.py",
    ]:
        assert not documentation_only(["PLAN.md", path])
    assert not documentation_only([])


def test_skip_requires_the_exact_candidate_and_actual_git_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], check=True)
    subprocess.run(["git", "config", "user.name", "synthetic"], check=True)
    subprocess.run(["git", "config", "user.email", "synthetic@example.invalid"], check=True)
    Path("app.py").write_text("# original\n")
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-qm", "base"], check=True)
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    Path("PLAN.md").write_text("Verified state\n")
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-qm", "docs"], check=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    report = {"base": base, "sha": head, "paths": ["PLAN.md"], "docs_only": True}
    assert validate_report(report, head)
    for bad in [{**report, "sha": base}, {**report, "paths": []}]:
        with pytest.raises(ValueError):
            validate_report(bad, head)
    Path("app.py").write_text("# changed code\n")
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-qm", "code"], check=True)
    changed = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    with pytest.raises(ValueError, match="Code changes"):
        validate_report({**report, "sha": changed, "paths": ["PLAN.md", "app.py"]}, changed)
