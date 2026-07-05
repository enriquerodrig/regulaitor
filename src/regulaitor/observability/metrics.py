"""In-process metrics FLOOR (roadmap P3.1).

Exposes counters a Prometheus scraper can poll at /metrics — NOT a full observability
platform (single-process counters, reset on restart; the scraper stores history +
computes rates/alerts). Deliberately no `prometheus_client` dependency: the text
exposition format is hand-rendered.

The key signal is the §6 verdict distribution — a live block-rate
`(block + requires_human_review) / total` an operator alerts on if it collapses (a
sudden all-pass would mean the Auditor stopped gating). Example alert (deploy-side):

    - alert: RegulAItorBlockRateCollapse
      expr: |
        sum(rate(regulaitor_turns_total{verdict=~"block|requires_human_review"}[15m]))
        / sum(rate(regulaitor_turns_total[15m])) < 0.05
      for: 30m

Thread-safe; counting is best-effort and MUST never break a request (all failures
swallowed). Opt-in exposure: /metrics is 404 unless REGULAITOR_ENABLE_METRICS=1
(fail-secure — usage volume is not advertised publicly; the operator scrapes it on an
internal network).
"""

from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_turns: dict[tuple[str, str], int] = {}  # (mode, verdict) -> count
_pii_queries = 0


def is_enabled() -> bool:
    """True only when REGULAITOR_ENABLE_METRICS=1 (fail-secure; /metrics 404s otherwise)."""
    return os.getenv("REGULAITOR_ENABLE_METRICS", "").strip() == "1"


def record_turn(mode: str, verdict: str) -> None:
    """Count one completed API turn by mode (chat|document) + verdict. Never raises."""
    try:
        with _lock:
            _turns[(mode, verdict)] = _turns.get((mode, verdict), 0) + 1
    except Exception as exc:  # pragma: no cover — counting must never break a request
        logger.debug("metrics record_turn failed: %s", exc)


def record_pii_query() -> None:
    """Count one query where PII was detected (advisory). Never raises."""
    global _pii_queries
    try:
        with _lock:
            _pii_queries += 1
    except Exception as exc:  # pragma: no cover
        logger.debug("metrics record_pii_query failed: %s", exc)


def reset() -> None:
    """Test helper — clear all counters."""
    global _pii_queries
    with _lock:
        _turns.clear()
        _pii_queries = 0


def render_prometheus() -> str:
    """Render current counters in Prometheus text exposition format (v0.0.4)."""
    with _lock:
        turns = dict(_turns)
        pii = _pii_queries
    lines = [
        "# HELP regulaitor_turns_total Completed API turns by mode and verdict.",
        "# TYPE regulaitor_turns_total counter",
    ]
    for (mode, verdict), n in sorted(turns.items()):
        lines.append(f'regulaitor_turns_total{{mode="{mode}",verdict="{verdict}"}} {n}')
    lines += [
        "# HELP regulaitor_pii_queries_total Queries where PII was detected (advisory).",
        "# TYPE regulaitor_pii_queries_total counter",
        f"regulaitor_pii_queries_total {pii}",
    ]
    return "\n".join(lines) + "\n"
