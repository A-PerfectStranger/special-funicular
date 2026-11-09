"""Fixed E3 synthetic episodes derived from the one-use E2 acceptance cohort."""

import copy
import uuid
from typing import Any

CASES = ["success", "timeout", "expiry", "revoke", "renew", "reject", "reschedule", "concurrency"]


def fixture_batch(cohort: dict[str, Any]) -> dict[str, Any]:
    batch: dict[str, Any] = copy.deepcopy(cohort["batch"])
    namespace = uuid.UUID(cohort["trial_id"])
    batch["id"] = str(uuid.uuid5(namespace, "e3-batch"))
    original = batch["students"][0]
    batch["students"] = []
    batch["links"] = []
    for case in CASES:
        child = {
            **copy.deepcopy(original),
            "id": str(uuid.uuid5(namespace, "e3-" + case)),
            "name": "E3 synthetic " + case,
        }
        for window in child["windows"]:
            window.update({"from": "00:00", "until": "23:59"})
        batch["students"].append(child)
        batch["links"].extend(
            {
                "student_id": child["id"],
                "parent_id": user["parent_id"],
                "principal": user["principal"],
            }
            for user in cohort["users"].values()
        )
    return batch
