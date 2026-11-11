"""Provider protocol negatives, privacy and authenticated outbound transport."""

import json
import uuid

import httpx
import pytest
from django.test import Client
from notification_worker.provider import MESSAGE, ExpoPush, ProviderUnavailable


def test_expo_payload_is_generic_and_ticket_is_not_delivery() -> None:
    sent = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        if request.url.path.endswith("send"):
            return httpx.Response(200, json={"data": {"status": "ok", "id": "ticket"}})
        return httpx.Response(200, json={"data": {"ticket": {"status": "ok"}}})

    with httpx.Client(
        base_url="https://exp.host/--/api/v2/push/", transport=httpx.MockTransport(handle)
    ) as client:
        provider = ExpoPush(client)
        ident = uuid.uuid4()
        assert provider.send("ExpoPushToken[synthetic-token]", ident).ticket == "ticket"
        assert provider.receipt("ticket") == "OK"
    assert sent[0]["body"] == MESSAGE
    assert sent[0]["data"] == {"notification_id": str(ident)}
    assert not {"student", "photo", "document", "operation_id", "school"} & sent[0].keys()


@pytest.mark.parametrize(
    "status,data,expected",
    [
        (429, {}, "PROVIDER_UNAVAILABLE"),
        (503, {}, "PROVIDER_UNAVAILABLE"),
        (
            200,
            {"data": {"status": "error", "details": {"error": "DeviceNotRegistered"}}},
            "DEVICE_NOT_REGISTERED",
        ),
        (200, {"data": []}, "INVALID_RESPONSE"),
        (200, {"data": {"status": "ok"}}, "INVALID_RESPONSE"),
        (302, {}, "PROVIDER_REJECTED"),
    ],
)
def test_provider_failure_never_becomes_success(
    status: int, data: dict[str, object], expected: str
) -> None:
    with httpx.Client(
        base_url="https://exp.host/--/api/v2/push/",
        transport=httpx.MockTransport(lambda _: httpx.Response(status, json=data)),
    ) as client:
        result = ExpoPush(client).send("synthetic", uuid.uuid4())
        assert result.ticket is None and result.failure == expected


def test_unknown_receipt_and_untrusted_callbacks_never_create_delivery() -> None:
    with httpx.Client(
        base_url="https://exp.host/--/api/v2/push/",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"data": {"other-ticket": {"status": "ok"}}})
        ),
    ) as client:
        assert ExpoPush(client).receipt("ticket") == "PENDING"
    assert Client().post("/v1/notifications/callback", {"status": "ok"}).status_code == 404


def test_configuration_requires_secret_and_team_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXPO_PUSH_ACCESS_TOKEN", raising=False)
    with pytest.raises(ProviderUnavailable):
        ExpoPush.configured()
    monkeypatch.setenv("EXPO_PUSH_ACCESS_TOKEN", "synthetic-provider-secret-only")
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.delenv("EXPO_PUSH_ALLOWED_TOKEN_HASHES", raising=False)
    with pytest.raises(ProviderUnavailable):
        ExpoPush.configured()
    with httpx.Client(base_url="https://exp.host/") as client:
        result = ExpoPush(client, frozenset()).send("unknown-token", uuid.uuid4())
        assert result.ticket is None
