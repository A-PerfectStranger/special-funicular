"""A local distribution cannot weaken the source pin or rewrite a mismatched wrapper."""

import hashlib
from pathlib import Path

import pytest

from scripts import gradle_archive as gradle


def test_source_pin_remains_the_approved_gradle_release() -> None:
    assert gradle.pin() == (
        "8.14.3",
        "bd71102213493060956ec229d946beee57158dbd89d0e62b91bca0fa2c5f3531",
    )


@pytest.mark.parametrize("damage", [None, "archive", "wrapper"])
def test_local_distribution_is_verified_before_generated_wrapper_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str | None
) -> None:
    payload = b"synthetic pinned archive for adapter validation only"
    expected = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(gradle, "pin", lambda: ("8.14.3", expected))
    archive = tmp_path / "gradle-8.14.3-bin.zip"
    archive.write_bytes(payload + (b"tampered" if damage == "archive" else b""))
    wrapper = tmp_path / "gradle-wrapper.properties"
    original = (
        "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.14.3-bin.zip\nnetworkTimeout=60000\ndistributionSha256Sum="
        + ("0" * 64 if damage == "wrapper" else expected)
        + "\n"
    )
    wrapper.write_text(original)
    if damage:
        with pytest.raises(ValueError):
            gradle.use(archive, wrapper)
        assert wrapper.read_text() == original
    else:
        gradle.use(archive, wrapper)
        assert archive.resolve().as_uri().replace(":", "\\:") in wrapper.read_text()
        assert "distributionSha256Sum=" + expected in wrapper.read_text()
        assert "networkTimeout=60000" in wrapper.read_text()
