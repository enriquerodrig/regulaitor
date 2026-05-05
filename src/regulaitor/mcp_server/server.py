"""MCP server bootstrap — stdio JSON-RPC.

Bootstraps the corpus loader (with hash drift fail-closed integrity check),
warms up the reranker, registers the 3 tools, and serves on stdio.

The actual stdio loop is provided by the official `mcp` Python SDK (FastMCP).

SDK note (deviation from plan pseudocode):
  The plan referenced ``mcp.server.Server`` with ``mcp_server.tool()(fn)`` style
  registration. The low-level ``Server`` class in mcp 1.x exposes only
  ``@list_tools()`` / ``@call_tool()`` decorators — not ``.tool()``. The
  ``FastMCP`` server (also in ``mcp.server``) provides the high-level
  ``.tool()`` / ``.add_tool(fn)`` API plus ``.run_stdio_async()`` and matches
  the plan's intent (auto-derive JSON Schemas from typed signatures, then
  serve stdio). We use ``FastMCP`` and ``add_tool`` for explicit registration
  of pre-existing functions.
"""

from __future__ import annotations

import asyncio
import logging

from regulaitor.corpus import loader
from regulaitor.mcp_server import tools
from regulaitor.rag import reranker

logger = logging.getLogger("regulaitor.mcp_server")


def _warmup_dependencies() -> None:
    """Run the warmup sequence: corpus loader (integrity-checked) -> reranker.

    Loader runs first; if it raises, reranker is NOT loaded. This is the
    fail-closed posture per decisions log 2026-05-05 "Corpus loader integrity
    check: strict fail-closed".
    """
    logger.info("warming up corpus loader (with integrity check)...")
    loader.warmup()
    logger.info("warming up reranker...")
    reranker.warmup()
    logger.info("warmup complete")


def run() -> None:  # pragma: no cover - exercised by integration test (Task 11)
    """Boot the MCP server on stdio.

    1. Warm up dependencies (fail-closed).
    2. Register tools with the SDK.
    3. Serve stdio loop.
    """
    from mcp.server import FastMCP

    _warmup_dependencies()

    mcp_server: FastMCP = FastMCP("regulaitor")

    # Register the 3 tools. FastMCP auto-derives JSON Schemas from the function
    # signatures + Pydantic types.
    mcp_server.add_tool(tools.search_articles)
    mcp_server.add_tool(tools.fetch_article)
    mcp_server.add_tool(tools.validate_citation)

    asyncio.run(mcp_server.run_stdio_async())
