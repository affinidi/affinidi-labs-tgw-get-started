#!/usr/bin/env python3
"""Entra bearer-token validation for the Personal Agent.

Signature (tenant JWKS), issuer, audience, expiry and scope are always verified.
There is no bypass flag and no "accept unsigned" path.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient


class EntraConfigError(RuntimeError):
    """Raised when an agent starts without a usable Entra configuration."""


class TokenError(Exception):
    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class EntraSettings:
    tenant_id: str
    audiences: tuple[str, ...]
    required_scope: str
    # When set, the token must have been issued to this client (`appid`).
    required_client: str | None = None


def load_settings(
    audience_var: str, scope_var: str, required_client: str | None = None
) -> EntraSettings:
    """Read the expected audience and scope from the named environment variables."""
    tenant_id = os.environ.get("ENTRA_TENANT_ID", "").strip()
    audience = os.environ.get(audience_var, "").strip()
    scope = os.environ.get(scope_var, "").strip()
    if not (tenant_id and audience and scope):
        raise EntraConfigError(
            f"ENTRA_TENANT_ID, {audience_var} and {scope_var} must be set in .env"
        )
    return EntraSettings(
        tenant_id=tenant_id,
        audiences=(audience,),
        required_scope=scope,
        required_client=required_client,
    )


class EntraTokenValidator:
    def __init__(self, settings: EntraSettings) -> None:
        self.settings = settings
        self._jwks = PyJWKClient(
            f"https://login.microsoftonline.com/{settings.tenant_id}/discovery/keys",
            cache_keys=True,
        )
        self._issuer = f"https://sts.windows.net/{settings.tenant_id}/"

    @staticmethod
    def extract_bearer(authorization: str | None) -> str:
        if not authorization:
            raise TokenError("missing_token", "Missing Authorization header.")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise TokenError(
                "invalid_authorization_header",
                "Authorization header must use the Bearer scheme.",
            )
        return token.strip()

    def validate(self, token: str) -> dict:
        try:
            key = self._jwks.get_signing_key_from_jwt(token)
        except Exception as error:  # noqa: BLE001
            raise TokenError(
                "unknown_signing_key", "Signing key not found in the Entra JWKS."
            ) from error
        try:
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                audience=list(self.settings.audiences),
                issuer=self._issuer,
                options={"require": ["exp", "iss", "aud"]},
                leeway=60,
            )
        except jwt.ExpiredSignatureError as error:
            raise TokenError("token_expired", "Token has expired.") from error
        except jwt.InvalidAudienceError as error:
            raise TokenError(
                "invalid_audience", "Token audience is not this agent."
            ) from error
        except jwt.InvalidIssuerError as error:
            raise TokenError("invalid_issuer", "Token issuer is not accepted.") from error
        except jwt.InvalidTokenError as error:
            raise TokenError("invalid_token", "Token failed validation.") from error

        if self.settings.required_scope not in str(claims.get("scp", "")).split():
            raise TokenError(
                "insufficient_scope",
                f"Token does not grant scope '{self.settings.required_scope}'.",
            )
        required_client = self.settings.required_client
        if required_client and claims.get("appid") != required_client:
            raise TokenError(
                "untrusted_client", "Token was not issued to the trusted calling agent."
            )
        return claims


SHOWN_CLAIMS = (
    "iss", "aud", "scp", "oid", "sub", "name", "preferred_username", "upn",
    "appid", "tid", "ver", "iat", "exp",
)


def decode_unverified(token: str) -> dict:
    """Decode without verifying. Display only - never used for a decision."""
    try:
        return jwt.decode(token, options={"verify_signature": False})
    except Exception:  # noqa: BLE001
        return {}


def summarize_claims(claims: dict) -> dict:
    return {key: claims[key] for key in SHOWN_CLAIMS if key in claims}


class PassthroughValidator:
    """No token validation: reads claims for display only.

    Use when the Agent Gateway in front of the agent does the validation.
    A missing token is passed through as an empty string.
    """

    validates = False

    @staticmethod
    def extract_bearer(authorization: str | None) -> str:
        scheme, _, token = (authorization or "").partition(" ")
        return token.strip() if scheme.lower() == "bearer" else ""

    def validate(self, token: str) -> dict:
        return decode_unverified(token) if token else {}
