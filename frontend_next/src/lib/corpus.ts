// Corpus chip metadata — display labels + accent colours.
//
// Mirrors `src/regulaitor/corpus/registry.py::CORPUS_REGISTRY` (the `label` and
// `color` fields, which that registry documents as human-curated UI metadata).
// Kept in sync MANUALLY: these are presentation-only and the backend does not
// expose a `/corpora` endpoint yet. If/when it does, derive this from it.

import type { CorpusSelector } from "@/lib/types";

export interface CorpusMeta {
  value: CorpusSelector;
  label: string;
  color: string; // hex accent, used for the corpus chip
}

export const CORPORA: CorpusMeta[] = [
  { value: "ai_act", label: "AI Act", color: "#1E40AF" },
  { value: "gdpr", label: "GDPR", color: "#047857" },
  { value: "nis2", label: "NIS2", color: "#6D28D9" },
  { value: "dora", label: "DORA", color: "#B45309" },
  { value: "dora_rts_incident", label: "DORA RTS Plazos", color: "#0F766E" },
  { value: "dora_rts_class", label: "DORA RTS Clasif.", color: "#A21CAF" },
  { value: "amlr", label: "AMLR", color: "#9F1239" },
  { value: "mica", label: "MiCA", color: "#0E7490" },
  { value: "tfr", label: "TFR", color: "#4D7C0F" },
  { value: "auto", label: "Auto (multi-corpus)", color: "#475569" },
];

// Document-analysis corpus options. The /analyze backend path validates each
// corpus member against ALL_NORMAS (the 9 real normas) and has NO "auto"
// multi-corpus handling, so offering "auto" there causes a 415. /ask keeps it.
export const DOC_CORPORA: CorpusMeta[] = CORPORA.filter((c) => c.value !== "auto");

export const CORPUS_LABELS: Record<string, string> = Object.fromEntries(
  CORPORA.map((c) => [c.value, c.label]),
);

export const CORPUS_COLORS: Record<string, string> = Object.fromEntries(
  CORPORA.map((c) => [c.value, c.color]),
);

/** Human label for any corpus key the backend returns (falls back to the raw key). */
export function corpusLabel(value: string): string {
  return CORPUS_LABELS[value] ?? value;
}
