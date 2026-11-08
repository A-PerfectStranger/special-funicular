"""An archive outage must not be misreported as detection of a rewritten SQL copy."""

from typing import Any

import pytest
from archive_worker.storage import IntegrityFailure
from archive_worker.verifier import SnapshotDivergence

from scripts.verify_e1_recovery import compare_copies


@pytest.mark.parametrize("failure", [IntegrityFailure(), SnapshotDivergence()])
def test_only_copy_divergence_establishes_rewrite_detection(failure: IntegrityFailure) -> None:
    class Verifier:
        calls = 0

        def verify(self, *args: Any) -> dict[str, Any]:
            self.calls += 1
            if self.calls == 1:
                return {"passed": True, "last_sequence": 7}
            raise failure

    verifier = Verifier()
    if isinstance(failure, SnapshotDivergence):
        assert compare_copies(verifier, [], [], 7)["last_sequence"] == 7  # type: ignore[arg-type]
    else:
        with pytest.raises(IntegrityFailure):
            compare_copies(verifier, [], [], 7)  # type: ignore[arg-type]
