"""Operator CLI for GDPR data-subject requests over the opt-in audit store (P3.3).

Runs on the deployment host (which owns the audit DB). ``REGULAITOR_AUDIT_DB``
must point at the audit DB; otherwise the store is disabled and every command is
a no-op. DSR erasure is operator/DPO-mediated by design — an audit trail should
not be tenant-erasable self-service (tamper-resistance + legal-retention
exceptions). See docs/data_retention.md.

    python -m scripts.dsr export <tenant_id>        # Art. 15 access → JSON on stdout
    python -m scripts.dsr erase  <tenant_id> --yes  # Art. 17 erasure (irreversible)
    python -m scripts.dsr purge  [--days N]         # retention purge (default 365)

Tenant "default" (or "-") maps to the single-token legacy tenant (tenant_id NULL).
Summaries go to stderr; ``export`` writes JSON to stdout so it pipes cleanly.
"""

from __future__ import annotations

import argparse
import json
import sys

from regulaitor.observability import audit_store


def _tenant(arg: str) -> str | None:
    return None if arg in ("", "default", "-") else arg


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dsr", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_exp = sub.add_parser("export", help="GDPR Art. 15 access — dump a tenant's rows as JSON")
    p_exp.add_argument("tenant_id")

    p_era = sub.add_parser("erase", help="GDPR Art. 17 erasure — delete a tenant's rows")
    p_era.add_argument("tenant_id")
    p_era.add_argument("--yes", action="store_true", help="required — confirm irreversible delete")

    p_pur = sub.add_parser("purge", help="retention purge — delete rows older than --days")
    p_pur.add_argument(
        "--days", type=int, default=None, help="override retention (default env/365)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if not audit_store.is_enabled():
        print(
            "audit store disabled (REGULAITOR_AUDIT_DB unset) — nothing to do",
            file=sys.stderr,
        )
        return 0

    if args.cmd == "export":
        rows = audit_store.export_tenant(_tenant(args.tenant_id))
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        print(f"exported {len(rows)} row(s) for tenant {args.tenant_id!r}", file=sys.stderr)
        return 0

    if args.cmd == "erase":
        if not args.yes:
            print("refusing to erase without --yes (irreversible)", file=sys.stderr)
            return 2
        n = audit_store.erase_tenant(_tenant(args.tenant_id))
        print(f"erased {n} row(s) for tenant {args.tenant_id!r}", file=sys.stderr)
        return 0

    # args.cmd == "purge" (argparse guarantees one of the three subcommands)
    n = audit_store.purge_expired(args.days)
    window = args.days if args.days is not None else audit_store.retention_days()
    print(f"purged {n} row(s) older than {window} day(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
