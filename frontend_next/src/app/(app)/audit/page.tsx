"use client";

import { Loader2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiError, getAudit } from "@/lib/api-client";
import type { AuditEntryDTO, AuditLogResponse } from "@/lib/types";

function fmtTs(ts: string): string {
  // Backend writes an ISO-8601 UTC timestamp; show a compact local form.
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toLocaleString("es-ES");
}

function citations(e: AuditEntryDTO): string {
  if (e.n_citations == null) return "—";
  return e.n_validated == null ? String(e.n_citations) : `${e.n_validated}/${e.n_citations}`;
}

export default function AuditPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AuditLogResponse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getAudit());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo consultar la auditoría.");
    } finally {
      setLoading(false);
    }
  }, []);

  // Async IIFE + unmount guard (react-hooks/set-state-in-effect), as in HealthPage.
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const d = await getAudit();
        if (active) setData(d);
      } catch (err) {
        if (active) {
          setError(
            err instanceof ApiError ? err.message : "No se pudo consultar la auditoría.",
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Traza de auditoría</h1>
          <p className="mt-1 text-muted-foreground">
            Registro de tus consultas. Sólo metadatos y el hash SHA-256 de la consulta —
            el texto original nunca se almacena.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
          {loading ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : (
            <RefreshCw className="size-4" aria-hidden />
          )}
          Actualizar
        </Button>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {data && !data.enabled ? (
        <Alert>
          <AlertDescription>
            La persistencia de auditoría no está activada en este despliegue
            (<code>REGULAITOR_AUDIT_DB</code> sin configurar).
          </AlertDescription>
        </Alert>
      ) : null}

      {data && data.enabled ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {data.total} {data.total === 1 ? "consulta registrada" : "consultas registradas"}
              {data.entries.length < data.total
                ? ` · mostrando las ${data.entries.length} más recientes`
                : null}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.entries.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aún no hay consultas registradas.</p>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Fecha</TableHead>
                      <TableHead>Modo</TableHead>
                      <TableHead>Corpus</TableHead>
                      <TableHead>Veredicto</TableHead>
                      <TableHead>Citas</TableHead>
                      <TableHead>Hash consulta</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.entries.map((e) => (
                      <TableRow key={e.case_id}>
                        <TableCell className="whitespace-nowrap text-sm">{fmtTs(e.ts)}</TableCell>
                        <TableCell className="text-sm">{e.mode}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {e.corpus ?? "—"}
                        </TableCell>
                        <TableCell className="text-sm font-medium">{e.verdict ?? "—"}</TableCell>
                        <TableCell className="text-sm">{citations(e)}</TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground">
                          {e.query_sha256 ? e.query_sha256.slice(0, 12) : "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      ) : null}
    </section>
  );
}
