"""Nango HTTP client for Hermes.

Thin wrapper around Nango's REST API using httpx (no official Python SDK).
All methods require NANGO_HOST and NANGO_SECRET_KEY to be set in env.

The secret key is kept in memory only and never returned in errors or results.
"""

from __future__ import annotations

import os
from typing import Any

import httpx


class NangoError(Exception):
    """Raised when a Nango API call fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class NangoClient:
    def __init__(self) -> None:
        host = os.environ.get("NANGO_HOST", "").rstrip("/")
        secret = os.environ.get("NANGO_SECRET_KEY", "")
        if not host:
            raise NangoError("NANGO_HOST env var is required (set to your self-hosted Nango URL)")
        if not secret:
            raise NangoError("NANGO_SECRET_KEY env var is required")
        self._host = host
        # Headers built once; secret never leaves this object
        self._auth_headers: dict[str, str] = {
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict | None = None, extra_headers: dict | None = None) -> Any:
        headers = {**self._auth_headers, **(extra_headers or {})}
        try:
            resp = httpx.get(f"{self._host}{path}", headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            # Strip auth headers from exception context before raising
            raise NangoError(
                f"Nango API error {exc.response.status_code}: {exc.response.text[:200]}",
                status_code=exc.response.status_code,
            ) from None

    def _post(self, path: str, data: dict | None = None, extra_headers: dict | None = None) -> Any:
        headers = {**self._auth_headers, **(extra_headers or {})}
        try:
            resp = httpx.post(f"{self._host}{path}", headers=headers, json=data or {}, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise NangoError(
                f"Nango API error {exc.response.status_code}: {exc.response.text[:200]}",
                status_code=exc.response.status_code,
            ) from None

    def create_session(self, connection_id: str, allowed_integrations: list[str] | None = None) -> dict:
        """Create a connect session.

        Returns {token, connect_link, expires_at}. The connect_link is a
        short-lived URL (30 min) the user opens to authorize an integration.
        Safe to show to users — it is NOT the secret key.
        """
        payload: dict[str, Any] = {"end_user": {"id": connection_id}}
        if allowed_integrations:
            payload["allowed_integrations"] = allowed_integrations
        result = self._post("/connect/sessions", payload)
        return result["data"]

    def list_connections(self, connection_id: str | None = None) -> list[dict]:
        """List all connections, optionally filtered by connection_id."""
        params = {}
        if connection_id:
            params["connectionId"] = connection_id
        result = self._get("/connections", params=params)
        return result.get("connections", [])

    def proxy_request(
        self,
        method: str,
        endpoint: str,
        connection_id: str,
        integration: str,
        params: dict | None = None,
        body: dict | None = None,
    ) -> Any:
        """Forward a request to an external API through Nango's proxy.

        Nango injects the user's OAuth token automatically. The agent never
        sees raw credentials.
        """
        proxy_headers = {
            **self._auth_headers,
            "Connection-Id": connection_id,
            "Provider-Config-Key": integration,
            "Retries": "3",         # Nango retries on 429/503
            "Retry-On": "429,503",
        }
        url = f"{self._host}/proxy{endpoint}"
        try:
            resp = httpx.request(
                method.upper(),
                url,
                headers=proxy_headers,
                params=params,
                json=body,
                timeout=60,
            )
            resp.raise_for_status()
            # Some APIs return empty body on success (e.g. DELETE)
            if not resp.content:
                return {"status": resp.status_code}
            return resp.json()
        except httpx.HTTPStatusError as exc:
            raise NangoError(
                f"Proxy error {exc.response.status_code} calling {integration}{endpoint}: {exc.response.text[:200]}",
                status_code=exc.response.status_code,
            ) from None
