"use client";

import { FileUp, Loader2, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { PiiSummary } from "@/components/pii-summary";
import { SanitizerLog } from "@/components/sanitizer-log";
import { SegmentCard } from "@/components/segment-card";
import { VerdictBadge } from "@/components/verdict-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { ApiError, analyze } from "@/lib/api-client";
import { DOC_CORPORA } from "@/lib/corpus";
import type { AnalyzeResponse, CorpusSelector, Language } from "@/lib/types";
import { cn } from "@/lib/utils";

const SELECT_CLS =
  "h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm shadow-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none";

export default function AnalyzePage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  // Doc-mode default is a real norma: the /analyze backend path does not accept
  // the "auto" multi-corpus selector (it 415s), unlike /ask. See DOC_CORPORA.
  const [corpus, setCorpus] = useState<CorpusSelector>("ai_act");
  const [language, setLanguage] = useState<Language>("es");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);

  function onDrop(event: React.DragEvent) {
    event.preventDefault();
    setDragging(false);
    const dropped = event.dataTransfer.files?.[0];
    if (dropped) setFile(dropped);
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("corpus", corpus);
      form.append("language", language);
      setResult(await analyze(form));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo analizar el documento.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Analiza documento</h1>
        <p className="mt-1 text-muted-foreground">
          Sube un PDF o Markdown corporativo y recibe un informe estructurado con
          hallazgos y citas verificadas por segmento.
        </p>
      </div>

      <Alert>
        <Upload className="size-4 text-amber-600" aria-hidden />
        <AlertTitle>Rendimiento</AlertTitle>
        <AlertDescription>
          El análisis ejecuta el reranker BGE-M3 en CPU (~15–30 s por segmento).
          Para una respuesta ágil, usa documentos de ≤ 5 páginas.
        </AlertDescription>
      </Alert>

      <Card>
        <CardContent className="pt-6">
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="file">Documento</Label>
              <div
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                className={cn(
                  "flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 text-center transition-colors",
                  dragging ? "border-primary bg-primary/5" : "border-input",
                )}
              >
                <FileUp className="size-6 text-muted-foreground" aria-hidden />
                <p className="text-sm text-muted-foreground">
                  Arrastra un archivo aquí o
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => inputRef.current?.click()}
                >
                  Selecciona un archivo
                </Button>
                <input
                  ref={inputRef}
                  id="file"
                  type="file"
                  accept=".pdf,.md,.markdown,.txt"
                  className="sr-only"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
                {file ? (
                  <p className="text-sm font-medium text-foreground">{file.name}</p>
                ) : null}
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="corpus">Corpus</Label>
                <select
                  id="corpus"
                  className={SELECT_CLS}
                  value={corpus}
                  onChange={(event) => setCorpus(event.target.value as CorpusSelector)}
                >
                  {DOC_CORPORA.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="language">Idioma</Label>
                <select
                  id="language"
                  className={SELECT_CLS}
                  value={language}
                  onChange={(event) => setLanguage(event.target.value as Language)}
                >
                  <option value="es">Español</option>
                  <option value="en">English</option>
                </select>
              </div>
            </div>

            <Button type="submit" disabled={loading || file === null}>
              {loading ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <FileUp className="size-4" aria-hidden />
              )}
              Analizar documento
            </Button>
          </form>
        </CardContent>
      </Card>

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {result ? (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-heading text-base leading-snug font-medium">
                  Informe del documento
                </h2>
                <VerdictBadge verdict={result.document_verdict} />
              </div>
              <p className="text-xs text-muted-foreground">
                Caso {result.case_id} · {result.n_segments_total} segmentos ·{" "}
                {result.latency_ms_total} ms · {result.cost_eur_total.toFixed(4)} €
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              {result.document_reason ? (
                <p className="text-sm text-muted-foreground">{result.document_reason}</p>
              ) : null}
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
                <span>Validados: {result.n_segments_pass}</span>
                <span>Bloqueados: {result.n_segments_block}</span>
                <span>Revisión: {result.n_segments_review}</span>
                <span>Inyección bloqueada: {result.n_segments_blocked_by_injection}</span>
              </div>
              {result.pii_summary ? <PiiSummary pii={result.pii_summary} /> : null}
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-muted-foreground">
                  Sanitizador
                </h3>
                <SanitizerLog events={result.sanitizer_log} />
              </div>
            </CardContent>
          </Card>

          {result.segments.length > 0 ? (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold">Segmentos</h2>
              {result.segments.map((segment) => (
                <SegmentCard key={segment.segment_id} segment={segment} />
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
