"""E2 finite recurrence and image safety, independent of provider adapters."""

import base64
import io
from datetime import date, time
from zoneinfo import ZoneInfo

import pytest
from authorization.services import InvalidFamilyInput, local_instant, photograph, schedule
from PIL import Image


def test_recurrence_is_expanded_in_site_zone_not_device_zone() -> None:
    request = {
        "start_date": "2026-11-09",
        "end_date": "2026-11-16",
        "weekdays": [1],
        "from": "13:00",
        "until": "13:15",
    }
    assert schedule(request, "America/Bogota") == [
        {"from": "2026-11-09T18:00:00+00:00", "until": "2026-11-09T18:15:00+00:00"},
        {"from": "2026-11-16T18:00:00+00:00", "until": "2026-11-16T18:15:00+00:00"},
    ]


@pytest.mark.parametrize(
    "day,clock", [(date(2027, 3, 14), time(2, 30)), (date(2026, 11, 1), time(1, 30))]
)
def test_nonexistent_or_ambiguous_civil_time_is_never_guessed(day: date, clock: time) -> None:
    with pytest.raises(InvalidFamilyInput):
        local_instant(day, clock, ZoneInfo("America/New_York"))


@pytest.mark.parametrize(
    "change",
    [
        {"weekdays": []},
        {"weekdays": [True]},
        {"weekdays": [1, 1]},
        {"weekdays": [0]},
        {"from": "18:00", "until": "07:00"},
        {"from": "13:00:00"},
        {"end_date": "2028-11-09"},
        {"start_date": "invalid"},
    ],
)
def test_invalid_recurrences_are_rejected(change: dict[str, object]) -> None:
    data = {
        "start_date": "2026-11-09",
        "end_date": "2026-11-09",
        "weekdays": [1],
        "from": "13:00",
        "until": "13:15",
    }
    with pytest.raises(InvalidFamilyInput):
        schedule({**data, **change}, "America/Bogota")


def test_photo_is_reencoded_bounded_and_metadata_removed() -> None:
    output = io.BytesIO()
    Image.new("RGB", (1000, 700), "red").save(
        output, "JPEG", exif=b"Exif\x00\x00synthetic private metadata"
    )
    raw = base64.b64decode(photograph(base64.b64encode(output.getvalue()).decode()))
    assert b"synthetic private metadata" not in raw
    with Image.open(io.BytesIO(raw)) as result:
        assert result.format == "JPEG" and max(result.size) <= 640 and not result.getexif()
    with pytest.raises(InvalidFamilyInput):
        photograph(base64.b64encode(b"<svg>not a photo</svg>").decode())
