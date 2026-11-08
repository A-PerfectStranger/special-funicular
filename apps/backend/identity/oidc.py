"""OIDC authorization-code adapter. Network responses and claims grant no local roles."""

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlencode, urlsplit

import boto3
import httpx
import jwt
from django.conf import settings


class IdentityRejected(Exception):
    """Deliberately carries no provider response, credential, or PII."""


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def pkce_challenge(verifier: str) -> str:
    return (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )


def https_url(value: str) -> bool:
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and not (parsed.username or parsed.password or parsed.fragment)
    )


@dataclass(frozen=True)
class VerifiedIdentity:
    issuer: str
    subject: str
    authenticated_at: int
    verified_contact: str | None = None


@dataclass(frozen=True)
class Provider:
    issuer: str
    web_client: str
    mobile_client: str
    web_redirect: str
    mobile_redirect: str
    mfa_policy: str
    pool_id: str
    region: str

    @classmethod
    def configured(cls) -> "Provider":
        values: dict[str, str] = settings.E1_OIDC
        if not all(
            values.get(key)
            for key in [
                "issuer",
                "web_client",
                "mobile_client",
                "web_redirect",
                "mobile_redirect",
                "mfa_policy",
            ]
        ):
            raise IdentityRejected()
        if not https_url(values["issuer"]) or not https_url(values["web_redirect"]):
            raise IdentityRejected()
        if values["mfa_policy"] not in {"amr_mfa", "cognito_required_totp"}:
            raise IdentityRejected()
        return cls(**values)

    def client(self, channel: str) -> str:
        return self.web_client if channel == "web" else self.mobile_client

    def redirect(self, channel: str) -> str:
        return self.web_redirect if channel == "web" else self.mobile_redirect

    def metadata(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=2, follow_redirects=False, trust_env=True) as client:
                response = client.get(self.issuer.rstrip("/") + "/.well-known/openid-configuration")
                response.raise_for_status()
                if len(response.content) > 65536:
                    raise IdentityRejected()
                data: dict[str, Any] = response.json()
            if data.get("issuer") != self.issuer or not all(
                isinstance(data.get(key), str) and https_url(data[key])
                for key in ["authorization_endpoint", "token_endpoint", "jwks_uri"]
            ):
                raise IdentityRejected()
            # Metadata is obtained only from the configured, verified issuer.
            return data
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise IdentityRejected() from exc

    def authorize_url(
        self, channel: str, state: str, nonce: str, challenge: str, require_contact: bool = False
    ) -> str:
        metadata = self.metadata()
        return (
            str(metadata["authorization_endpoint"])
            + "?"
            + urlencode(
                {
                    "client_id": self.client(channel),
                    "redirect_uri": self.redirect(channel),
                    "response_type": "code",
                    "scope": "openid email" if require_contact else "openid",
                    "state": state,
                    "nonce": nonce,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                    "prompt": "login",
                    "max_age": "0",
                }
            )
        )

    def verify_cognito_policy(self, channel: str, authorization_endpoint: str) -> None:
        """Cognito omits amr in user-pool ID tokens: require the real pool's mandatory MFA.

        No custom/federated/direct password grant is accepted. Merely having TOTP
        enrolled or a client-provided MFA claim is never sufficient.
        """
        if not self.pool_id or self.issuer != (
            f"https://cognito-idp.{self.region}.amazonaws.com/{self.pool_id}"
        ):
            raise IdentityRejected()
        cognito = boto3.client("cognito-idp", region_name=self.region)
        host = urlsplit(authorization_endpoint).hostname or ""
        suffix = f".auth.{self.region}.amazoncognito.com"
        if not host.endswith(suffix):
            raise IdentityRejected()
        domain = cognito.describe_user_pool_domain(Domain=host.removesuffix(suffix))[
            "DomainDescription"
        ]
        pool = cognito.describe_user_pool(UserPoolId=self.pool_id)["UserPool"]
        mfa = cognito.get_user_pool_mfa_config(UserPoolId=self.pool_id)
        client = cognito.describe_user_pool_client(
            UserPoolId=self.pool_id, ClientId=self.client(channel)
        )["UserPoolClient"]
        if (
            pool.get("MfaConfiguration") != "ON"
            or pool.get("UserPoolTier") != "ESSENTIALS"
            or domain.get("UserPoolId") != self.pool_id
            or domain.get("ManagedLoginVersion") != 2
            or mfa.get("MfaConfiguration") != "ON"
            or not mfa.get("SoftwareTokenMfaConfiguration", {}).get("Enabled")
            or pool.get("LambdaConfig")
            or pool.get("DeviceConfiguration")
            or mfa.get("SmsMfaConfiguration")
            or mfa.get("EmailMfaConfiguration")
            or not pool.get("AdminCreateUserConfig", {}).get("AllowAdminCreateUserOnly")
            or client.get("SupportedIdentityProviders") != ["COGNITO"]
            or client.get("AllowedOAuthFlows") != ["code"]
            or not client.get("AllowedOAuthFlowsUserPoolClient")
            or set(client.get("ExplicitAuthFlows", [])) - {"ALLOW_REFRESH_TOKEN_AUTH"}
            or client.get("CallbackURLs") != [self.redirect(channel)]
            or client.get("IdTokenValidity") != 5
            or client.get("TokenValidityUnits", {}).get("IdToken") != "minutes"
        ):
            raise IdentityRejected()

    def exchange(self, channel: str, code: str, verifier: str, nonce: str) -> VerifiedIdentity:
        try:
            metadata = self.metadata()
            with httpx.Client(timeout=2, follow_redirects=False, trust_env=True) as client:
                response = client.post(
                    metadata["token_endpoint"],
                    data={
                        "grant_type": "authorization_code",
                        "client_id": self.client(channel),
                        "redirect_uri": self.redirect(channel),
                        "code": code,
                        "code_verifier": verifier,
                    },
                )
                response.raise_for_status()
                if len(response.content) > 32768:
                    raise IdentityRejected()
                token = response.json().get("id_token")
                keys_response = client.get(metadata["jwks_uri"])
                keys_response.raise_for_status()
                if len(keys_response.content) > 65536:
                    raise IdentityRejected()
                keys = keys_response.json().get("keys", [])
            identity = self.verify_token(token, keys, channel, nonce)
            if self.mfa_policy == "cognito_required_totp":
                self.verify_cognito_policy(channel, metadata["authorization_endpoint"])
            return identity
        except IdentityRejected:
            raise
        except Exception as exc:
            # No response body or provider error ever reaches logs or clients.
            raise IdentityRejected() from exc

    def verify_token(self, token: Any, keys: Any, channel: str, nonce: str) -> VerifiedIdentity:
        try:
            if not isinstance(token, str) or len(token) > 16384 or not isinstance(keys, list):
                raise IdentityRejected()
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise IdentityRejected()
            matching = [
                key
                for key in keys
                if key.get("kid") == header["kid"]
                and key.get("kty") == "RSA"
                and key.get("use", "sig") == "sig"
                and key.get("alg", "RS256") == "RS256"
            ]
            if len(matching) != 1:
                raise IdentityRejected()
            claims = jwt.decode(
                token,
                jwt.PyJWK.from_dict(matching[0]).key,
                algorithms=["RS256"],
                audience=self.client(channel),
                issuer=self.issuer,
                leeway=30,
                options={"require": ["iss", "sub", "aud", "iat", "exp", "auth_time", "nonce"]},
            )
            now = time.time()
            amr = claims.get("amr")
            if (
                not isinstance(claims["sub"], str)
                or not 1 <= len(claims["sub"]) <= 255
                or not isinstance(claims["nonce"], str)
                or not hmac.compare_digest(claims["nonce"], nonce)
                or type(claims["auth_time"]) is not int
                or type(claims["iat"]) is not int
                or type(claims["exp"]) is not int
                or not 0 < claims["exp"] - claims["iat"] <= 300
                or not now - 300 <= claims["auth_time"] <= now + 30
                or (isinstance(claims["aud"], list) and len(claims["aud"]) != 1)
                or (claims.get("azp") is not None and claims["azp"] != self.client(channel))
                or (
                    self.mfa_policy == "amr_mfa"
                    and (
                        not isinstance(amr, list)
                        or not all(isinstance(method, str) for method in amr)
                        or "mfa" not in amr
                    )
                )
                or (self.mfa_policy == "cognito_required_totp" and claims.get("token_use") != "id")
            ):
                raise IdentityRejected()
            contact = claims.get("email")
            verified_contact = (
                contact.lower()
                if claims.get("email_verified") is True
                and isinstance(contact, str)
                and 3 <= len(contact) <= 254
                else None
            )
            return VerifiedIdentity(
                self.issuer, claims["sub"], claims["auth_time"], verified_contact
            )
        except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
            raise IdentityRejected() from exc


Channel = Literal["web", "mobile"]
