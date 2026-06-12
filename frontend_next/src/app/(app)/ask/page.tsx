"use client";

import { Loader2, Send } from "lucide-react";
import { useState } from "react";

import { AnswerBlock } from "@/components/answer-block";
import { AuditTable } from "@/components/audit-table";
import { CouncilPanel } from "@/components/council-panel";
import { VerdictBadge } from "@/components/verdict-badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, ask } from "@/lib/api-client";
import { CORPORA } from "@/lib/corpus";
import type { AskResponse, CorpusSelector, Language } from "@/lib/types";

const SELECT_CLS =
  "h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm shadow-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none";

export default function AskPage() {
  const [query, setQuery] = useState("");
  const [corpus, setCorpus] = useState<CorpusSelector>("auto");
  const [language, setLanguage] = useState<Language>("es");
  const [council, setCouncil] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AskResponse | null>(null);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const response = await ask({ query, corpus, language, council });
      setResult(response);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo completar la consulta.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Pregunta</h1>
        <p className="mt-1 text-muted-foreground">
          Consulta normativa con respuesta razonada y citas verificadas contra el
          corpus oficial.
        </p>
      </div>

      <Card>
        <CardContent className="pt-6">
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="query">Consulta</Label>
              <Textarea
                id="query"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Ej.: ¿Qué obligaciones de transparencia impone el AI Act a un sistema de IA de alto riesgo?"
                rows={4}
                maxLength={2000}
                required
              />
              <p className="text-right text-xs text-muted-foreground" aria-hidden>
                {query.length}/2000
              </p>
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
                  {CORPORA.map((c) => (
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

            <div className="flex items-center gap-3">
              <Switch id="council" checked={council} onCheckedChange={setCouncil} />
              <Label htmlFor="council" className="cursor-pointer font-normal">
                Forzar revisión colegiada (Council)
              </Label>
            </div>

            <Button type="submit" disabled={loading || query.trim().length === 0}>
              {loading ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Send className="size-4" aria-hidden />
              )}
              Consultar
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
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-heading text-base leading-snug font-medium">Resultado</h2>
              <VerdictBadge verdict={result.verdict} />
            </div>
            <p className="text-xs text-muted-foreground">
              Caso {result.case_id} · {result.response_time_ms} ms
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            {result.council_notice ? (
              <Alert>
                <AlertDescription>{result.council_notice}</AlertDescription>
              </Alert>
            ) : null}
            {result.reason ? (
              <p className="text-sm text-muted-foreground">{result.reason}</p>
            ) : null}

            <AnswerBlock answer={result.answer} />

            {result.audit_results.length > 0 ? (
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-muted-foreground">
                  Auditoría de citas
                </h3>
                <AuditTable results={result.audit_results} />
              </div>
            ) : null}

            {/* council_notice is already surfaced once in the Alert above; the
                panel renders the judges + verdict without repeating the notice. */}
            {result.council ? <CouncilPanel council={result.council} /> : null}
          </CardContent>
        </Card>
      ) : null}
    </section>
  );
}
