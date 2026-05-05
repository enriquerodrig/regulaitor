"""Error types raised inside MCP tools.

Mapped to JSON-RPC error codes by the MCP SDK dispatch layer. Keep this module
small; the SDK handles framing.
"""

from __future__ import annotations


class NotFoundError(Exception):
    """Raised when a requested article or apartado does not exist.

    Mapped to JSON-RPC custom error code -32001 ("NOT_FOUND") by the server.
    """


class IntegrityError(RuntimeError):
    """Raised by corpus.loader.warmup() on hash drift; server fails to start."""
