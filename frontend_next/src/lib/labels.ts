// Centralised Spanish UI labels for backend enums. Presentation only.

import type { Severity, Verdict } from "@/lib/types";

export const VERDICT_LABEL: Record<Verdict, string> = {
  pass: "Validado",
  block: "Bloqueado",
  requires_human_review: "Requiere revisión humana",
};

export const SEVERITY_LABEL: Record<Severity, string> = {
  info: "Información",
  low: "Baja",
  medium: "Media",
  high: "Alta",
};

// /health check statuses (HealthCheck.status enum) — keep the UI fully Spanish.
export const HEALTH_STATUS_LABEL: Record<string, string> = {
  ok: "Operativo",
  present: "Presente",
  missing: "Ausente",
  unreachable: "Inaccesible",
  degraded: "Degradado",
};

export function healthStatusLabel(value: string): string {
  return HEALTH_STATUS_LABEL[value] ?? value;
}

/** Shared "<article>.<apartado>" reference (single source for both the citation
 *  block and the audit table, so the article/apartado format never diverges). */
export function articleRef(articulo: string, apartado: string | null): string {
  return apartado ? `${articulo}.${apartado}` : articulo;
}

export function agreementLabel(value: string): string {
  return (
    {
      unanimous: "unánime",
      majority: "mayoría",
      split: "dividido",
      degraded: "degradado",
    } as Record<string, string>
  )[value] ?? value;
}

export function triggerLabel(value: string): string {
  return (
    {
      auditor_rhr: "el Auditor pidió revisión",
      high_severity: "severidad alta",
      api_override: "forzado por API",
      not_triggered: "no activado",
    } as Record<string, string>
  )[value] ?? value;
}

export function skipLabel(value: string): string {
  return (
    {
      clean: "limpio",
      injection_blocked: "inyección bloqueada",
      internal_error: "error interno",
    } as Record<string, string>
  )[value] ?? value;
}
