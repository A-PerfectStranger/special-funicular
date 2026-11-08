"""AT04/AT06: real RSA signatures with adversarial claims, no live-IdP assertion."""

import json
import time
from dataclasses import replace
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from identity.oidc import IdentityRejected, Provider
from jwt.algorithms import RSAAlgorithm


@pytest.fixture
def signed_identity() -> tuple[Provider, Any, dict[str, Any], dict[str, Any]]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="test-key", use="sig", alg="RS256")
    now = int(time.time())
    claims = {
        "iss": "https://idp.example",
        "sub": "synthetic-subject",
        "aud": "mobile",
        "iat": now,
        "exp": now + 300,
        "auth_time": now,
        "nonce": "bound-nonce",
        "amr": ["mfa"],
    }
    provider = Provider(
        "https://idp.example",
        "web",
        "mobile",
        "https://app.example/auth/callback",
        "retiro-seguro-dev://auth/callback",
        "amr_mfa",
        "",
        "us-east-1",
    )
    return provider, key, jwk, claims


def token(key: Any, claims: dict[str, Any], kid: str = "test-key") -> str:
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


def test_valid_oidc_never_turns_claimed_roles_into_authorization(signed_identity: Any) -> None:
    provider, key, jwk, claims = signed_identity
    claims.update(role="ADMIN_SISTEMA", school_id="other-school", principal=True)
    verified = provider.verify_token(token(key, claims), [jwk], "mobile", "bound-nonce")
    assert verified.subject == "synthetic-subject"
    assert not hasattr(verified, "role")


@pytest.mark.parametrize(
    "override",
    [
        {"iss": "https://evil.example"},
        {"aud": "web"},
        {"nonce": "other-login"},
        {"amr": ["pwd"]},
        {"amr": []},
        {"sub": ""},
        {"exp": 1},
        {"auth_time": 1},
        {"exp": int(time.time()) + 3600},
        {"aud": ["mobile", "evil"]},
        {"azp": "evil"},
        {"auth_time": int(time.time()) + 120},
    ],
)
def test_invalid_oidc_claims_rejected(signed_identity: Any, override: dict[str, Any]) -> None:
    provider, key, jwk, claims = signed_identity
    claims.update(override)
    with pytest.raises(IdentityRejected):
        provider.verify_token(token(key, claims), [jwk], "mobile", "bound-nonce")


def test_signature_key_and_algorithm_are_pinned(signed_identity: Any) -> None:
    provider, _, jwk, claims = signed_identity
    attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(IdentityRejected):
        provider.verify_token(token(attacker, claims), [jwk], "mobile", "bound-nonce")
    forged = jwt.encode(
        claims,
        "synthetic-hmac-key-000000000000000000",
        algorithm="HS256",
        headers={"kid": "test-key"},
    )
    with pytest.raises(IdentityRejected):
        provider.verify_token(forged, [jwk], "mobile", "bound-nonce")


def test_cognito_requires_id_token_and_mandatory_pool_check(signed_identity: Any) -> None:
    provider, key, jwk, claims = signed_identity
    provider = replace(provider, mfa_policy="cognito_required_totp")
    claims.pop("amr")
    with pytest.raises(IdentityRejected):
        provider.verify_token(token(key, claims), [jwk], "mobile", "bound-nonce")
    claims["token_use"] = "id"
    assert provider.verify_token(token(key, claims), [jwk], "mobile", "bound-nonce")
