"""Private status changes must revoke live sessions without changing bindings or children."""

import uuid

import pytest

from scripts.change_e1_fixture import change, links_fingerprint
from tests.integration.e1_support import connect, digest, login, roster

pytestmark = pytest.mark.integration


def test_private_status_revokes_unexpired_session_and_restore_never_reanimates_it() -> None:
    data = roster()
    account = str(data["accounts"]["PADRE"])
    token, _, _ = login(data["accounts"]["PADRE"])
    with connect("importer") as importer, connect() as runtime:
        before = links_fingerprint(importer)
        assert runtime.execute("SELECT e1_authenticate(%s,false)", (digest(token),)).fetchone()[0]
        with pytest.raises(RuntimeError, match="no rebinding"):
            change(importer, account, "https://idp.example", str(uuid.uuid4()), False)
        assert runtime.execute("SELECT e1_authenticate(%s,false)", (digest(token),)).fetchone()[0]
        change(importer, account, "https://idp.example", account, False)
        assert runtime.execute("SELECT e1_authenticate(%s,false)", (digest(token),)).fetchone() == (
            None,
        )
        change(importer, account, "https://idp.example", account, True)
        assert runtime.execute("SELECT e1_authenticate(%s,false)", (digest(token),)).fetchone() == (
            None,
        )
        assert links_fingerprint(importer) == before
    fresh, _, _ = login(data["accounts"]["PADRE"])
    with connect() as runtime:
        assert runtime.execute("SELECT e1_authenticate(%s,false)", (digest(fresh),)).fetchone()[0]


def test_business_credential_cannot_execute_the_private_status_command() -> None:
    with connect() as runtime, pytest.raises(RuntimeError, match="Private importer"):
        change(runtime, str(uuid.uuid4()), "https://idp.example", str(uuid.uuid4()), False)
