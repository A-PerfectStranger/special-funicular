"""Keep ephemeral QR/session material out of E3 failure reports."""

import re
from collections.abc import Generator
from typing import Any

import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: Any, call: Any) -> Generator[None, Any, None]:
    outcome = yield
    report = outcome.get_result()
    if "test_e3_pickup.py" in str(item.fspath) and report.longrepr:
        report.longrepr = re.sub(
            r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])",
            "[REDACTED]",
            str(report.longrepr),
        )
