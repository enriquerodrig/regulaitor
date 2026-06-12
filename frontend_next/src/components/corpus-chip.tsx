import { CORPUS_COLORS, corpusLabel } from "@/lib/corpus";

// Accent colour comes from the corpus registry mirror. Inline style is allowed
// by the CSP (style-src 'unsafe-inline'); scripts stay strict.
export function CorpusChip({ norma }: { norma: string }) {
  const color = CORPUS_COLORS[norma] ?? "#475569";
  return (
    <span
      className="inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap"
      style={{ borderColor: color, color }}
    >
      {corpusLabel(norma)}
    </span>
  );
}
