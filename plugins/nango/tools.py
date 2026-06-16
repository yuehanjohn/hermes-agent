"""Nango tools for Hermes — registered via plugins/nango."""

from __future__ import annotations

import os

from plugins.nango.client import NangoClient, NangoError
from tools.registry import tool_error, tool_result


# ---------------------------------------------------------------------------
# Availability gate
# ---------------------------------------------------------------------------

def _check_nango_available() -> bool:
    return bool(os.getenv("NANGO_SECRET_KEY") and os.getenv("NANGO_HOST"))


def _client() -> NangoClient:
    return NangoClient()


def _resolve_connection_id(explicit_id: str | None) -> str:
    """Return connection_id in priority order: explicit arg → env var → 'default'."""
    if explicit_id:
        return explicit_id
    return os.getenv("NANGO_USER_ID", "default")


# ---------------------------------------------------------------------------
# Tool: nango_connect
# ---------------------------------------------------------------------------

NANGO_CONNECT_SCHEMA = {
    "type": "object",
    "description": (
        "Generate an OAuth authorization link for a user to connect a third-party "
        "integration via Nango. Show the returned link to the user — they open it "
        "to authorize. The link expires in 30 minutes."
    ),
    "properties": {
        "integration": {
            "type": "string",
            "description": (
                "Integration key as configured in the Nango dashboard "
                "(e.g. 'github', 'gmail', 'hubspot', 'slack')"
            ),
        },
        "connection_id": {
            "type": "string",
            "description": (
                "Stable user identifier used to store/retrieve this connection. "
                "Defaults to NANGO_USER_ID env var or 'default'."
            ),
        },
    },
    "required": ["integration"],
}


def _handle_nango_connect(integration: str, connection_id: str | None = None, **_) -> str:
    cid = _resolve_connection_id(connection_id)
    try:
        session = _client().create_session(cid, allowed_integrations=[integration])
    except NangoError as exc:
        return tool_error(str(exc), status_code=exc.status_code)
    except Exception as exc:
        return tool_error(f"Failed to create Nango session: {exc}")
    return tool_result(
        connect_link=session["connect_link"],
        expires_at=session.get("expires_at"),
        connection_id=cid,
        integration=integration,
        note="Share this link with the user to authorize the integration. It expires in 30 minutes.",
    )


# ---------------------------------------------------------------------------
# Tool: nango_call
# ---------------------------------------------------------------------------

NANGO_CALL_SCHEMA = {
    "type": "object",
    "description": (
        "Make an authenticated API call to a third-party service through Nango's proxy. "
        "Nango automatically injects the user's OAuth token — no raw credentials are "
        "ever exposed to the agent."
    ),
    "properties": {
        "integration": {
            "type": "string",
            "description": "Integration key (e.g. 'github', 'gmail', 'hubspot')",
        },
        "method": {
            "type": "string",
            "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
            "description": "HTTP method",
        },
        "endpoint": {
            "type": "string",
            "description": (
                "API path relative to the provider's base URL. "
                "Examples: '/user/repos', '/me/messages', '/crm/v3/objects/contacts'"
            ),
        },
        "connection_id": {
            "type": "string",
            "description": "User identifier. Defaults to NANGO_USER_ID env var or 'default'.",
        },
        "params": {
            "type": "object",
            "description": "Query parameters (GET requests)",
        },
        "body": {
            "type": "object",
            "description": "Request body (POST/PUT/PATCH requests)",
        },
    },
    "required": ["integration", "method", "endpoint"],
}


def _handle_nango_call(
    integration: str,
    method: str,
    endpoint: str,
    connection_id: str | None = None,
    params: dict | None = None,
    body: dict | None = None,
    **_,
) -> str:
    cid = _resolve_connection_id(connection_id)
    try:
        data = _client().proxy_request(
            method=method,
            endpoint=endpoint,
            connection_id=cid,
            integration=integration,
            params=params,
            body=body,
        )
    except NangoError as exc:
        return tool_error(str(exc), status_code=exc.status_code)
    except Exception as exc:
        return tool_error(f"Nango proxy call failed: {exc}")
    return tool_result(data)


# ---------------------------------------------------------------------------
# Tool: nango_connections
# ---------------------------------------------------------------------------

NANGO_CONNECTIONS_SCHEMA = {
    "type": "object",
    "description": (
        "List third-party integrations that a user has already authorized via Nango. "
        "Use this to check what APIs are available before calling nango_call."
    ),
    "properties": {
        "connection_id": {
            "type": "string",
            "description": "Filter by user identifier. Defaults to NANGO_USER_ID or 'default'.",
        },
    },
}


def _handle_nango_connections(connection_id: str | None = None, **_) -> str:
    cid = _resolve_connection_id(connection_id)
    try:
        connections = _client().list_connections(cid)
    except NangoError as exc:
        return tool_error(str(exc), status_code=exc.status_code)
    except Exception as exc:
        return tool_error(f"Failed to list Nango connections: {exc}")
    if not connections:
        return tool_result(
            connections=[],
            connection_id=cid,
            note=f"No integrations connected yet for '{cid}'. Use nango_connect to add one.",
        )
    return tool_result(connections=connections, connection_id=cid)
