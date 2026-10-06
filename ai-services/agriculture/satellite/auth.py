"""
TruthChain Agriculture
Copernicus Data Space Authentication
====================================

Authentication helpers for Copernicus Data Space.

Environment variables:

    CDSE_CLIENT_ID
    CDSE_CLIENT_SECRET

or:

    CDSE_USERNAME
    CDSE_PASSWORD

Optional:

    CDSE_TOKEN_URL

Credentials are never hardcoded or printed.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any

import requests


# ============================================================
# Configuration
# ============================================================

DEFAULT_TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/"
    "auth/realms/CDSE/"
    "protocol/openid-connect/token"
)

DEFAULT_CLIENT_ID = "cdse-public"

REQUEST_TIMEOUT_SECONDS = 60

TOKEN_EXPIRY_SAFETY_SECONDS = 60


# ============================================================
# Errors
# ============================================================

class CDSEAuthError(RuntimeError):
    """Base CDSE authentication error."""


class CDSECredentialsError(CDSEAuthError):
    """Raised when required credentials are unavailable."""


class CDSETokenError(CDSEAuthError):
    """Raised when token acquisition fails."""


# ============================================================
# Token
# ============================================================

@dataclass(frozen=True)
class AccessToken:
    """
    CDSE access token.
    """

    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None
    obtained_at: float = 0.0

    def is_expired(
        self,
        safety_seconds: int = TOKEN_EXPIRY_SAFETY_SECONDS,
    ) -> bool:
        """
        Return True when the token is expired or about to expire.
        """

        if not self.access_token:
            return True

        if self.expires_in is None:
            return False

        expiry_time = (
            self.obtained_at
            + self.expires_in
            - safety_seconds
        )

        return time.time() >= expiry_time

    def authorization_header(self) -> dict[str, str]:
        """
        Return an HTTP Authorization header.
        """

        return {
            "Authorization": (
                f"{self.token_type} "
                f"{self.access_token}"
            )
        }


# ============================================================
# Environment helpers
# ============================================================

def _get_env(
    name: str,
) -> str | None:
    """
    Read and strip an environment variable.
    """

    value = os.getenv(name)

    if value is None:
        return None

    value = value.strip()

    return value or None


def get_client_id() -> str | None:
    """
    Get OAuth client ID.
    """

    return _get_env(
        "CDSE_CLIENT_ID"
    )


def get_client_secret() -> str | None:
    """
    Get OAuth client secret.
    """

    return _get_env(
        "CDSE_CLIENT_SECRET"
    )


def get_username() -> str | None:
    """
    Get CDSE username.
    """

    return _get_env(
        "CDSE_USERNAME"
    )


def get_password() -> str | None:
    """
    Get CDSE password.
    """

    return _get_env(
        "CDSE_PASSWORD"
    )


def get_token_url() -> str:
    """
    Get the configured token endpoint.
    """

    value = _get_env(
        "CDSE_TOKEN_URL"
    )

    return value or DEFAULT_TOKEN_URL


# ============================================================
# Configuration status
# ============================================================

def has_client_credentials() -> bool:
    """
    Return True when OAuth client credentials are configured.
    """

    return bool(
        get_client_id()
        and get_client_secret()
    )


def has_password_credentials() -> bool:
    """
    Return True when username/password credentials are configured.
    """

    return bool(
        get_username()
        and get_password()
    )


def authentication_status() -> dict[str, bool]:
    """
    Return safe authentication configuration status.

    Secrets are never returned.
    """

    return {
        "client_credentials_configured": (
            has_client_credentials()
        ),
        "username_password_configured": (
            has_password_credentials()
        ),
    }


# ============================================================
# HTTP response parsing
# ============================================================

def _parse_token_response(
    response: requests.Response,
) -> AccessToken:
    """
    Parse a successful CDSE OAuth token response.
    """

    try:
        payload = response.json()

    except ValueError as exc:
        raise CDSETokenError(
            "CDSE identity service returned invalid JSON."
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise CDSETokenError(
            "CDSE token response must be a JSON object."
        )

    access_token = payload.get(
        "access_token"
    )

    if not access_token:
        raise CDSETokenError(
            "CDSE token response did not contain access_token."
        )

    expires_in = payload.get(
        "expires_in"
    )

    try:
        expires_in_value = (
            int(expires_in)
            if expires_in is not None
            else None
        )

    except (
        TypeError,
        ValueError,
    ):
        expires_in_value = None

    refresh_token = payload.get(
        "refresh_token"
    )

    scope = payload.get(
        "scope"
    )

    return AccessToken(
        access_token=str(
            access_token
        ),
        token_type=str(
            payload.get(
                "token_type",
                "Bearer",
            )
        ),
        expires_in=expires_in_value,
        refresh_token=(
            str(refresh_token)
            if refresh_token
            else None
        ),
        scope=(
            str(scope)
            if scope
            else None
        ),
        obtained_at=time.time(),
    )


# ============================================================
# Client credentials authentication
# ============================================================

def request_client_credentials_token(
    *,
    client_id: str | None = None,
    client_secret: str | None = None,
    token_url: str | None = None,
) -> AccessToken:
    """
    Obtain a CDSE OAuth token using client credentials.
    """

    client_id = (
        client_id
        or get_client_id()
    )

    client_secret = (
        client_secret
        or get_client_secret()
    )

    token_url = (
        token_url
        or get_token_url()
    )

    if not client_id:
        raise CDSECredentialsError(
            "CDSE_CLIENT_ID is not configured."
        )

    if not client_secret:
        raise CDSECredentialsError(
            "CDSE_CLIENT_SECRET is not configured."
        )

    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }

    try:
        response = requests.post(
            token_url,
            data=data,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    except requests.Timeout as exc:
        raise CDSETokenError(
            "CDSE client-credentials request timed out."
        ) from exc

    except requests.ConnectionError as exc:
        raise CDSETokenError(
            "Unable to connect to the CDSE identity service."
        ) from exc

    except requests.RequestException as exc:
        raise CDSETokenError(
            f"CDSE client-credentials request failed: {exc}"
        ) from exc

    if response.status_code >= 400:
        body = response.text[:2000]

        raise CDSETokenError(
            "CDSE client-credentials authentication failed "
            f"with HTTP {response.status_code}: {body}"
        )

    return _parse_token_response(
        response
    )


# ============================================================
# Username/password authentication
# ============================================================

def request_password_token(
    *,
    username: str | None = None,
    password: str | None = None,
    token_url: str | None = None,
) -> AccessToken:
    """
    Obtain a CDSE OAuth token using username/password.
    """

    username = (
        username
        or get_username()
    )

    password = (
        password
        or get_password()
    )

    token_url = (
        token_url
        or get_token_url()
    )

    if not username:
        raise CDSECredentialsError(
            "CDSE_USERNAME is not configured."
        )

    if not password:
        raise CDSECredentialsError(
            "CDSE_PASSWORD is not configured."
        )

    data = {
        "client_id": DEFAULT_CLIENT_ID,
        "username": username,
        "password": password,
        "grant_type": "password",
    }

    try:
        response = requests.post(
            token_url,
            data=data,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    except requests.Timeout as exc:
        raise CDSETokenError(
            "CDSE username/password request timed out."
        ) from exc

    except requests.ConnectionError as exc:
        raise CDSETokenError(
            "Unable to connect to the CDSE identity service."
        ) from exc

    except requests.RequestException as exc:
        raise CDSETokenError(
            f"CDSE username/password request failed: {exc}"
        ) from exc

    if response.status_code >= 400:
        body = response.text[:2000]

        raise CDSETokenError(
            "CDSE username/password authentication failed "
            f"with HTTP {response.status_code}: {body}"
        )

    return _parse_token_response(
        response
    )


# ============================================================
# Refresh token
# ============================================================

def request_refresh_token(
    refresh_token: str,
    *,
    token_url: str | None = None,
) -> AccessToken:
    """
    Obtain a new access token using a refresh token.
    """

    if not isinstance(
        refresh_token,
        str,
    ):
        raise TypeError(
            "refresh_token must be a string."
        )

    refresh_token = refresh_token.strip()

    if not refresh_token:
        raise CDSECredentialsError(
            "refresh_token cannot be empty."
        )

    token_url = (
        token_url
        or get_token_url()
    )

    data = {
        "client_id": DEFAULT_CLIENT_ID,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    try:
        response = requests.post(
            token_url,
            data=data,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    except requests.Timeout as exc:
        raise CDSETokenError(
            "CDSE refresh-token request timed out."
        ) from exc

    except requests.ConnectionError as exc:
        raise CDSETokenError(
            "Unable to connect to the CDSE identity service."
        ) from exc

    except requests.RequestException as exc:
        raise CDSETokenError(
            f"CDSE refresh-token request failed: {exc}"
        ) from exc

    if response.status_code >= 400:
        body = response.text[:2000]

        raise CDSETokenError(
            "CDSE refresh-token request failed "
            f"with HTTP {response.status_code}: {body}"
        )

    return _parse_token_response(
        response
    )


# ============================================================
# Unified authentication
# ============================================================

def get_access_token(
    *,
    prefer_client_credentials: bool = True,
    refresh_token: str | None = None,
) -> AccessToken:
    """
    Obtain an access token.

    Default priority:

        1. client credentials
        2. supplied refresh token
        3. username/password

    If client credentials are unavailable, username/password
    can still be used.
    """

    if (
        prefer_client_credentials
        and has_client_credentials()
    ):
        return request_client_credentials_token()

    if refresh_token:
        return request_refresh_token(
            refresh_token
        )

    if has_password_credentials():
        return request_password_token()

    if has_client_credentials():
        return request_client_credentials_token()

    raise CDSECredentialsError(
        "No CDSE authentication credentials are configured. "
        "Configure CDSE_CLIENT_ID/CDSE_CLIENT_SECRET or "
        "CDSE_USERNAME/CDSE_PASSWORD."
    )


# ============================================================
# Authorization
# ============================================================

def authorization_header(
    token: AccessToken,
) -> dict[str, str]:
    """
    Build an Authorization header from an AccessToken.
    """

    if not isinstance(
        token,
        AccessToken,
    ):
        raise TypeError(
            "token must be an AccessToken."
        )

    if token.is_expired():
        raise CDSETokenError(
            "Access token has expired."
        )

    return token.authorization_header()


def token_summary(
    token: AccessToken,
) -> dict[str, Any]:
    """
    Return safe token metadata.
    """

    return {
        "token_type": token.token_type,
        "expires_in": token.expires_in,
        "has_refresh_token": bool(
            token.refresh_token
        ),
        "scope": token.scope,
        "expired": token.is_expired(),
        "configured": bool(
            token.access_token
        ),
    }


# ============================================================
# Cached token provider
# ============================================================

class CDSETokenProvider:
    """
    Thread-safe in-memory token cache.

    Prevents unnecessary token requests when the current
    token is still valid.
    """

    def __init__(
        self,
        *,
        prefer_client_credentials: bool = True,
        refresh_token: str | None = None,
    ) -> None:

        self.prefer_client_credentials = (
            prefer_client_credentials
        )

        self.refresh_token = (
            refresh_token
        )

        self._token: AccessToken | None = None

        self._lock = threading.Lock()

    def get_token(
        self,
    ) -> AccessToken:
        """
        Return a valid cached token or obtain a new one.
        """

        with self._lock:

            if (
                self._token is not None
                and not self._token.is_expired()
            ):
                return self._token

            self._token = get_access_token(
                prefer_client_credentials=(
                    self.prefer_client_credentials
                ),
                refresh_token=self.refresh_token,
            )

            if self._token.refresh_token:
                self.refresh_token = (
                    self._token.refresh_token
                )

            return self._token

    def get_headers(
        self,
    ) -> dict[str, str]:
        """
        Return Authorization headers.
        """

        return authorization_header(
            self.get_token()
        )

    def clear(self) -> None:
        """
        Clear cached token.
        """

        with self._lock:
            self._token = None


# ============================================================
# Public exports
# ============================================================

__all__ = [
    "DEFAULT_TOKEN_URL",
    "DEFAULT_CLIENT_ID",
    "REQUEST_TIMEOUT_SECONDS",
    "TOKEN_EXPIRY_SAFETY_SECONDS",
    "CDSEAuthError",
    "CDSECredentialsError",
    "CDSETokenError",
    "AccessToken",
    "get_client_id",
    "get_client_secret",
    "get_username",
    "get_password",
    "get_token_url",
    "has_client_credentials",
    "has_password_credentials",
    "authentication_status",
    "request_client_credentials_token",
    "request_password_token",
    "request_refresh_token",
    "get_access_token",
    "authorization_header",
    "token_summary",
    "CDSETokenProvider",
]