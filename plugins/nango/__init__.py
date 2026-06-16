"""Nango integration plugin — bundled, auto-loaded.

Registers 3 tools (connect, call, connections) into the ``nango`` toolset.
Each tool is gated by ``_check_nango_available()`` — when NANGO_HOST and
NANGO_SECRET_KEY env vars are not set, the tools are hidden from the agent.

Once the env vars are configured, all integrations are managed entirely in
the Nango dashboard. No Hermes code changes are needed to add or remove
supported integrations.
"""

from __future__ import annotations

from plugins.nango.tools import (
    NANGO_CALL_SCHEMA,
    NANGO_CONNECT_SCHEMA,
    NANGO_CONNECTIONS_SCHEMA,
    _check_nango_available,
    _handle_nango_call,
    _handle_nango_connect,
    _handle_nango_connections,
)

_TOOLS = (
    ("nango_connect",     NANGO_CONNECT_SCHEMA,     _handle_nango_connect,     "🔌"),
    ("nango_call",        NANGO_CALL_SCHEMA,         _handle_nango_call,        "🌐"),
    ("nango_connections", NANGO_CONNECTIONS_SCHEMA,  _handle_nango_connections, "🔗"),
)


def register(ctx) -> None:
    """Register all Nango tools. Called once by the plugin loader."""
    for name, schema, handler, emoji in _TOOLS:
        ctx.register_tool(
            name=name,
            toolset="nango",
            schema=schema,
            handler=handler,
            check_fn=_check_nango_available,
            emoji=emoji,
        )
