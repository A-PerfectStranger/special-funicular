"""Expo Push HTTPS protocol. A receipt means handed to FCM/APNs, never read."""

import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

BASE_URL = "https://exp.host/--/api/v2/push"
MESSAGE = "Hay una actualización en tu cuenta. Abre la aplicación para consultarla."


class ProviderUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class SendResult:
    ticket: str | None
    failure: str = ""
    retry_after_seconds: int = 0


def retry_after(value: str) -> int:
    try:
        seconds = (
            int(value)
            if value.isdecimal()
            else int((parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds())
        )
        return max(0, min(seconds, 2147483647))
    except (ValueError, TypeError, OverflowError):
        return 0


def failure(data: Any) -> str:
    if isinstance(data, dict) and isinstance(data.get("details"), dict):
        if data["details"].get("error") == "DeviceNotRegistered":
            return "DEVICE_NOT_REGISTERED"
    return "PROVIDER_REJECTED"


class ExpoPush:
    def __init__(self, client: httpx.Client, allowed_tokens: frozenset[str] | None = None) -> None:
        self.client = client
        self.allowed_tokens = allowed_tokens

    @classmethod
    def configured(cls) -> "ExpoPush":
        secret = os.environ.get("EXPO_PUSH_ACCESS_TOKEN", "")
        if len(secret) < 20:
            raise ProviderUnavailable("BLOCKED: Expo enhanced push security required")
        allowed = frozenset(
            filter(None, os.environ.get("EXPO_PUSH_ALLOWED_TOKEN_HASHES", "").split(","))
        )
        synthetic = os.environ.get("APP_ENV", "development") != "production"
        if synthetic and (not allowed or any(len(value) != 64 for value in allowed)):
            raise ProviderUnavailable("BLOCKED: synthetic push requires team device allowlist")
        return cls(
            httpx.Client(
                base_url=BASE_URL + "/",
                headers={"Authorization": f"Bearer {secret}", "Accept": "application/json"},
                timeout=httpx.Timeout(10, connect=3),
                follow_redirects=False,
            ),
            allowed if synthetic else None,
        )

    def send(self, token: str, notification_id: uuid.UUID) -> SendResult:
        if (
            self.allowed_tokens is not None
            and hashlib.sha256(token.encode()).hexdigest() not in self.allowed_tokens
        ):
            return SendResult(None, "PROVIDER_REJECTED")
        try:
            response = self.client.post(
                "send",
                json={
                    "to": token,
                    "title": "Retiro seguro",
                    "body": MESSAGE,
                    "data": {"notification_id": str(notification_id)},
                    "channelId": "account-updates",
                    "ttl": 3600,
                },
            )
            if response.status_code == 429 or response.status_code >= 500:
                return SendResult(
                    None,
                    "PROVIDER_UNAVAILABLE",
                    retry_after(response.headers.get("Retry-After", "")),
                )
            if response.status_code != 200 or len(response.content) > 65536:
                return SendResult(None, "PROVIDER_REJECTED")
            data = response.json().get("data")
            if not isinstance(data, dict):
                return SendResult(None, "INVALID_RESPONSE")
            if data.get("status") != "ok":
                return SendResult(None, failure(data))
            ticket = data.get("id")
            if not isinstance(ticket, str) or not 1 <= len(ticket) <= 255:
                return SendResult(None, "INVALID_RESPONSE")
            return SendResult(ticket)
        except (httpx.HTTPError, ValueError, AttributeError):
            return SendResult(None, "PROVIDER_UNAVAILABLE")

    def receipt(self, ticket: str) -> str:
        try:
            response = self.client.post("getReceipts", json={"ids": [ticket]})
            if response.status_code != 200 or len(response.content) > 65536:
                return "PROVIDER_UNAVAILABLE"
            data = response.json().get("data")
            if not isinstance(data, dict):
                return "PROVIDER_UNAVAILABLE"
            receipt = data.get(ticket)
            if receipt is None:
                return "PENDING"
            if not isinstance(receipt, dict) or receipt.get("status") not in {"ok", "error"}:
                return "PROVIDER_UNAVAILABLE"
            return "OK" if receipt["status"] == "ok" else failure(receipt)
        except (httpx.HTTPError, ValueError, AttributeError):
            return "PROVIDER_UNAVAILABLE"
