"""Fase 6B (ADR-0041 §9) — GET /audit: the authenticated tenant's own audit trail.

Read-only. The tenant_id is ALWAYS forced from request.state.tenant (set by
verify_token); the endpoint never accepts a tenant_id from the client, so a tenant
can only ever read its OWN rows (the tenant-isolation requirement flagged in
ADR-0041 §22.22 #9). Returns an empty, `enabled=False` view when the audit trail
is not configured (REGULAITOR_AUDIT_DB unset).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from regulaitor.api.auth import verify_token
from regulaitor.api.schemas import AuditEntryDTO, AuditLogResponse
from regulaitor.observability import audit_store

router = APIRouter(tags=["meta"])

_MAX_LIMIT = 200


@router.get("/audit", response_model=AuditLogResponse)
async def audit(
    request: Request,
    limit: int = Query(default=50, ge=1, le=_MAX_LIMIT),
    _: None = Depends(verify_token),
) -> AuditLogResponse:
    """Return the calling tenant's most recent audit rows + its total turn count."""
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        # Fail CLOSED. verify_token guarantees a tenant on success, so this branch
        # is defense-in-depth only — but it must NEVER fall back to tenant_id=None,
        # because audit_store.recent(tenant_id=None) is an unscoped global SELECT.
        # For a multi-tenant compliance product the blast radius of an accidental
        # global read is total, so a missing tenant yields an empty view, not a leak.
        return AuditLogResponse(enabled=audit_store.is_enabled(), total=0, entries=[])
    # SECURITY: scope strictly to the caller's tenant — never a client-supplied id.
    tenant_id = tenant.tenant_id
    rows = audit_store.recent(limit=limit, tenant_id=tenant_id)
    entries = [
        AuditEntryDTO.model_validate({k: r.get(k) for k in AuditEntryDTO.model_fields})
        for r in rows
    ]
    return AuditLogResponse(
        enabled=audit_store.is_enabled(),
        total=audit_store.count_turns(tenant_id),
        entries=entries,
    )
