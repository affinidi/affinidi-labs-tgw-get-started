#!/usr/bin/env python3
"""Microsoft Entra ID bearer-token validation for the A2A v1 echo agent.

The agent trusts nothing but a cryptographically valid Entra token. Signatures
are checked against the tenant JWKS, and issuer, audience, and expiry are all
verified. There is no bypass flag and no "accept unsigned" path.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient


class EntraConfigError(RuntimeError):
    """Raised when the agent is started without a usable Entra configuration."""


class TokenError(Exception):
    """Raised when a presented bearer token is missing or not acceptable.

    `reason` is a short machine-readable code and `detail` is a caller-safe
    message. Neither ever contains the token itself.
    """

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class EntraSettings:
    tenant_id: str
    audiences: tuple[str, ...]
    issuers: tuple[str, ...]
    jwks_url: str
    required_scope: str | None = None
    required_role: str | None = None


def _split(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def load_settings() -> EntraSettings:
    """Build Entra settings from the environment, failing closed when unset."""
    tenant_id = os.environ.get("ENTRA_TENANT_ID", "").strip()
    audiences = _split(os.environ.get("ENTRA_AUDIENCE", ""))

    if not tenant_id:
        raise EntraConfigError(
            "ENTRA_TENANT_ID is not set. Copy .env.example to .env and fill in "
            "your Entra tenant and application values."
        )
    if not audiences:
        raise EntraConfigError(
            "ENTRA_AUDIENCE is not set. Set it to the application (client) ID "
            "or the Application ID URI that the token is issued for."
        )

    default_issuers = (
        f"https://login.microsoftonline.com/{tenant_id}/v2.0",
        f"https://sts.windows.net/{tenant_id}/",
    )
    issuers = _split(os.environ.get("ENTRA_ISSUER", "")) or default_issuers

    jwks_url = os.environ.get("ENTRA_JWKS_URL", "").strip() or (
        f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    )

    required_scope = os.environ.get("ENTRA_REQUIRED_SCOPE", "").strip() or None
    required_role = os.environ.get("ENTRA_REQUIRED_ROLE", "").strip() or None

    return EntraSettings(
        tenant_id=tenant_id,
        audiences=audiences,
        issuers=issuers,
        jwks_url=jwks_url,
        required_scope=required_scope,
        required_role=required_role,
    )


class EntraTokenValidator:
    """Validates Entra-issued JWTs against the tenant's published JWKS."""

    def __init__(self, settings: EntraSettings) -> None:
        self._settings = settings
        # PyJWKClient caches keys and refreshes on an unknown `kid`, so a key
        # rollover does not require an agent restart.
        self._jwk_client = PyJWKClient(settings.jwks_url, cache_keys=True)

    @property
    def settings(self) -> EntraSettings:
        return self._settings

    def extract_bearer(self, authorization: str | None) -> str:
        """Pull the raw token out of an Authorization header."""
        if not authorization:
            raise TokenError(
                "missing_token",
                "Missing Authorization header. This agent requires a Microsoft "
                "Entra ID bearer token.",
            )
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise TokenError(
                "invalid_authorization_header",
                "Authorization header must use the 'Bearer <token>' scheme.",
            )
        return token.strip()

    def validate(self, token: str) -> dict:
        """Verify signature, issuer, audience, expiry, and optional scope."""
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token)
        except Exception as error:  # noqa: BLE001 - surfaced as a 401 below
            raise TokenError(
                "unknown_signing_key",
                "Token signing key could not be resolved from the Entra JWKS.",
            ) from error

        try:
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=list(self._settings.audiences),
                issuer=list(self._settings.issuers),
                options={
                    "require": ["exp", "iss", "aud"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
                leeway=60,
            )
        except jwt.ExpiredSignatureError as error:
            raise TokenError("token_expired", "Token has expired.") from error
        except jwt.InvalidAudienceError as error:
            raise TokenError(
                "invalid_audience", "Token audience is not accepted by this agent."
            ) from error
        except jwt.InvalidIssuerError as error:
            raise TokenError(
                "invalid_issuer", "Token issuer is not accepted by this agent."
            ) from error
        except jwt.InvalidTokenError as error:
            raise TokenError(
                "invalid_token", "Token failed validation."
            ) from error

        self._check_authorization(claims)
        return claims

    def _check_authorization(self, claims: dict) -> None:
        """Apply the check that matches the flow the token came from.

        Delegated (3-legged) tokens carry `scp`; app-only (2-legged, client
        credentials) tokens carry `roles` and never `scp`, so requiring a
        delegated scope would reject every machine caller.
        """
        if is_app_only(claims):
            required = self._settings.required_role
            if not required:
                return
            if required not in set(claims.get("roles") or []):
                raise TokenError(
                    "insufficient_role",
                    f"App-only token does not grant the required app role "
                    f"'{required}'.",
                )
            return

        required = self._settings.required_scope
        if not required:
            return
        granted = set(str(claims.get("scp", "")).split())
        if required not in granted:
            raise TokenError(
                "insufficient_scope",
                f"Token does not grant the required scope '{required}'.",
            )


def is_app_only(claims: dict) -> bool:
    """True for a client-credentials (machine) token, false for a user token.

    Entra marks app-only v2 tokens with `idtyp=app`; v1 tokens have no such
    claim, so the absence of both `scp` and a user identity claim is used.
    """
    if str(claims.get("idtyp", "")).lower() == "app":
        return True
    has_user = bool(
        claims.get("upn") or claims.get(
            "preferred_username") or claims.get("name")
    )
    return not claims.get("scp") and not has_user


def describe_caller(claims: dict) -> dict[str, str]:
    """Summarise the verified caller. Only non-sensitive claims are returned."""
    app_only = is_app_only(claims)
    username = str(
        claims.get("preferred_username") or claims.get("upn") or ""
    )
    app_id = str(claims.get("appid") or claims.get("azp") or "")
    return {
        "callerType": "application" if app_only else "user",
        "flow": "client_credentials (2-legged)" if app_only else "authorization_code (3-legged)",
        "display": (f"app {app_id}" if app_only else (claims.get("name") or username))
        or str(claims.get("sub", "")),
        "subject": str(claims.get("sub", "")),
        "name": str(claims.get("name", "")),
        "username": username,
        "appId": app_id,
        "tenant": str(claims.get("tid", "")),
        "audience": str(claims.get("aud", "")),
        "scopes": str(claims.get("scp", "")),
        "roles": " ".join(claims.get("roles") or []),
    }


def token_fingerprint(token: str) -> str:
    """Stable, non-reversible id for a token, safe to put in a log."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def inspect_token(token: str) -> dict:
    """Decode a token for logging *without* verifying it.

    Used purely for observability, so a rejected token can still be inspected.
    Nothing here may influence an authorization decision -- `validate()` is the
    only path that does, and it verifies the signature.
    """
    report: dict = {"fingerprint": token_fingerprint(
        token), "length": len(token)}
    try:
        report["header"] = jwt.get_unverified_header(token)
    except Exception as error:  # noqa: BLE001 - a malformed token is still logged
        report["header_error"] = str(error)
    try:
        report["claims"] = jwt.decode(
            token, options={"verify_signature": False})
    except Exception as error:  # noqa: BLE001
        report["claims_error"] = str(error)
    return report


def format_token_log(token: str, *, include_raw: bool) -> str:
    """Render a token report for the agent log.

    The raw JWT is a live credential: it is only printed when the operator
    explicitly opts in with LOG_RAW_TOKEN=true, which must never be done
    outside a local lab.
    """
    report = inspect_token(token)
    lines = [
        f"  fingerprint : sha256:{report['fingerprint']} (len {report['length']})",
        f"  header      : {json.dumps(report.get('header', report.get('header_error')))}",
        f"  claims      : {json.dumps(report.get('claims', report.get('claims_error')), default=str)}",
    ]
    if include_raw:
        lines.append(f"  raw jwt     : {token}")
    else:
        lines.append(
            "  raw jwt     : <hidden> (set LOG_RAW_TOKEN=true to print it; lab only)"
        )
    return "\n".join(lines)
