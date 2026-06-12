"use client";

import { Loader2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiError, getHealth } from "@/lib/api-client";
import { healthStatusLabel } from "@/lib/labels";
import type { HealthCheck, HealthResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

const CHECK_CLS: Record<HealthCheck["status"], string> = {
  ok: "text-emerald-600",
  present: "text-emerald-600",
  missing: "text-red-600",
  unreachable: "text-red-600",
  degraded: "text-amber-600",
};

export default function HealthPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setHealth(await getHealth());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo consultar el estado.");
    } finally {
      setLoading(false);
    }
  }, []);

  // Mount fetch as an async IIFE so no setState runs synchronously in the effect
  // body (react-hooks/set-state-in-effect); the unmount guard avoids a stale set.
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const data = await getHealth();
        if (active) setHealth(data);
      } catch (err) {
        if (active) {
          setError(
            err instanceof ApiError ? err.message : "No se pudo consultar el estado.",
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

  const overallOk = health?.status === "ok";

  return (
    <section className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Estado del sistema</h1>
          <p className="mt-1 text-muted-foreground">
            Comprobaciones de salud del servicio.
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

      {health ? (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-base">
                Versión {health.version}
              </CardTitle>
              <span
                className={cn(
                  "inline-flex items-center rounded-md border px-2.5 py-1 text-sm font-medium",
                  overallOk
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-amber-200 bg-amber-50 text-amber-700",
                )}
              >
                {overallOk ? "Operativo" : "Degradado"}
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Comprobación</TableHead>
                    <TableHead>Estado</TableHead>
                    <TableHead>Detalle</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {health.checks.map((check) => (
                    <TableRow key={check.name}>
                      <TableCell className="font-medium">{check.name}</TableCell>
                      <TableCell className={cn("font-medium", CHECK_CLS[check.status])}>
                        {healthStatusLabel(check.status)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {check.detail ?? "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </section>
  );
}
