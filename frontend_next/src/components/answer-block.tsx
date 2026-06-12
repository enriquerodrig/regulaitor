import { FindingCard } from "@/components/finding-card";
import type { AnswerDTO } from "@/lib/types";

export function AnswerBlock({ answer }: { answer: AnswerDTO }) {
  const isEmpty = !answer.text && answer.findings.length === 0;
  return (
    <div className="space-y-4">
      {isEmpty ? (
        <p className="text-sm text-muted-foreground">Sin contenido para mostrar.</p>
      ) : null}
      {answer.text ? (
        <p className="text-sm leading-relaxed whitespace-pre-wrap">{answer.text}</p>
      ) : null}
      {answer.findings.length > 0 ? (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-muted-foreground">
            Hallazgos ({answer.findings.length})
          </h3>
          {answer.findings.map((finding, i) => (
            <FindingCard key={i} finding={finding} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
