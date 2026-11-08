"""Untrusted SQL-copy shape and a deliberate, internally consistent synthetic rewrite."""

import base64
import hashlib
import json
from typing import Any


def validate_local_chain(rows: list[dict[str, Any]]) -> None:
    previous = "0" * 64
    for sequence, row in enumerate(rows, 1):
        payload = base64.b64decode(row["canonical_base64"], validate=True)
        event = json.loads(payload)
        if (
            row["sequence"] != sequence
            or event["sequence"] != sequence
            or event["id"] != row["event_id"]
            or event["previous_digest"] != previous
            or hashlib.sha256(payload).hexdigest() != row["digest"]
        ):
            raise ValueError("Invalid local chain")
        previous = row["digest"]
    if not rows:
        raise ValueError("Nonempty synthetic snapshot required")


def rewrite_copy(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    validate_local_chain(rows)
    forged: list[dict[str, Any]] = []
    previous = "0" * 64
    for index, row in enumerate(rows):
        payload = base64.b64decode(row["canonical_base64"], validate=True)
        event = json.loads(payload)
        original_previous = event["previous_digest"]
        if index == 0:
            original_result = event["snapshot"]["result"]
            if not isinstance(original_result, str):
                raise ValueError("Known synthetic result shape required")
            replacement = "E1_SYNTHETIC_COPY_ALTERED"
            event["snapshot"]["result"] = replacement
            payload = payload.replace(
                ('"result": ' + json.dumps(original_result, ensure_ascii=False)).encode(),
                ('"result": ' + json.dumps(replacement)).encode(),
                1,
            )
        event["previous_digest"] = previous
        # Preserve PostgreSQL's original JSONB text ordering/encoding; do not invent
        # another canonical format while deliberately recomputing the local chain.
        payload = payload.replace(
            ('"previous_digest": ' + json.dumps(original_previous)).encode(),
            ('"previous_digest": ' + json.dumps(previous)).encode(),
            1,
        )
        if json.loads(payload) != event:
            raise ValueError("Unexpected synthetic canonical shape")
        previous = hashlib.sha256(payload).hexdigest()
        forged.append(
            {**row, "canonical_base64": base64.b64encode(payload).decode(), "digest": previous}
        )
    validate_local_chain(forged)
    return forged
