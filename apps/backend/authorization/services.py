"""Family validation; the SQL command independently checks session, scope and versions."""

import base64
import binascii
import io
import json
import re
import warnings
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from identity.oidc import IdentityRejected
from identity.services import scalar
from PIL import Image, ImageOps, UnidentifiedImageError


class InvalidFamilyInput(ValueError):
    pass


def photograph(encoded: str) -> str:
    """Decode bounded image, discard metadata and reencode RGB JPEG. No file persistence."""
    try:
        raw = base64.b64decode(encoded, validate=True)
        if not 10 <= len(raw) <= 300000:
            raise InvalidFamilyInput()
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as original:
                if (
                    original.format not in {"PNG", "JPEG"}
                    or original.width * original.height > 4000000
                ):
                    raise InvalidFamilyInput()
                original.load()
                image = ImageOps.exif_transpose(original).convert("RGB")
                image.thumbnail((640, 640))
                output = io.BytesIO()
                image.save(output, "JPEG", quality=85)
        return base64.b64encode(output.getvalue()).decode()
    except (
        ValueError,
        OSError,
        UnidentifiedImageError,
        binascii.Error,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as exc:
        raise InvalidFamilyInput() from exc


def local_instant(day: date, clock: time, zone: ZoneInfo) -> datetime:
    local = datetime.combine(day, clock)
    first = local.replace(tzinfo=zone, fold=0)
    second = local.replace(tzinfo=zone, fold=1)
    # Missing/ambiguous civil times require a different interval, never a guessed offset.
    if (
        first.utcoffset() != second.utcoffset()
        or first.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != local
    ):
        raise InvalidFamilyInput()
    return first.astimezone(UTC)


def schedule(data: dict[str, Any], zone_name: str) -> list[dict[str, str]]:
    try:
        if set(data) != {"start_date", "end_date", "weekdays", "from", "until"}:
            raise InvalidFamilyInput()
        start, end = date.fromisoformat(data["start_date"]), date.fromisoformat(data["end_date"])
        if not 0 <= (end - start).days <= 365:
            raise InvalidFamilyInput()
        days = data["weekdays"]
        if (
            not isinstance(days, list)
            or not days
            or len(days) != len(set(days))
            or any(type(d) is not int or not 1 <= d <= 7 for d in days)
        ):
            raise InvalidFamilyInput()
        if any(
            not isinstance(data[key], str)
            or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", data[key])
            for key in ["from", "until"]
        ):
            raise InvalidFamilyInput()
        f, t = time.fromisoformat(data["from"]), time.fromisoformat(data["until"])
        if f >= t:
            raise InvalidFamilyInput()
        zone = ZoneInfo(zone_name)
        result = []
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            if day.isoweekday() in days:
                result.append(
                    {
                        "from": local_instant(day, f, zone).isoformat(),
                        "until": local_instant(day, t, zone).isoformat(),
                    }
                )
        if not result:
            raise InvalidFamilyInput()
        return result
    except (TypeError, KeyError, ValueError) as exc:
        raise InvalidFamilyInput() from exc


def command(operation: str, correlation: str, data: dict[str, Any]) -> dict[str, Any]:
    if operation in {"CREATE_CAREGIVER", "UPDATE_CAREGIVER"}:
        expected = {"student_id", "name", "document", "photo"}
        if operation == "UPDATE_CAREGIVER":
            expected |= {"id", "version"}
        if set(data) != expected:
            raise InvalidFamilyInput()
        data = {**data, "photo": photograph(data["photo"])}
    elif operation == "CREATE_AUTHORIZATION":
        if set(data) != {"student_id", "caregiver_id", "recurrence"}:
            raise InvalidFamilyInput()
        students = scalar("SELECT public.e2_students()", ())
        own = next((s for s in students if s["id"] == data["student_id"]), None)
        if not own:
            raise IdentityRejected()
        data = {
            "student_id": data["student_id"],
            "caregiver_id": data["caregiver_id"],
            "schedule": schedule(data["recurrence"], own["timezone"]),
        }
    elif set(data) != {"id", "student_id"}:
        raise InvalidFamilyInput()
    result: dict[str, Any] = scalar(
        "SELECT public.e2_family_command(%s,%s,%s::jsonb)",
        (operation, correlation, json.dumps(data)),
    )
    return result
