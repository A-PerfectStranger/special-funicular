"""A failed request only proves isolation when AWS explicitly denies access."""

import pytest
from botocore.exceptions import ClientError

from scripts.verify_e1_staging import denied


@pytest.mark.parametrize(
    "code", ["AccessDenied", "AccessDeniedException", "NoSuchKey", "ThrottlingException"]
)
def test_only_explicit_access_denial_counts_as_isolation(code: str) -> None:
    def operation() -> None:
        raise ClientError({"Error": {"Code": code, "Message": "private provider detail"}}, "Probe")

    if code.startswith("AccessDenied"):
        denied(operation)
    else:
        with pytest.raises(RuntimeError, match="not established"):
            denied(operation)


def test_unexpected_permission_is_never_accepted() -> None:
    with pytest.raises(RuntimeError, match="Unexpected cloud permission"):
        denied(lambda: None)
