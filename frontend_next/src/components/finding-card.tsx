import { CitationBlock } from "@/components/citation-block";
import { SeverityChip } from "@/components/severity-chip";
import type { FindingDTO } from "@/lib/types";

export function FindingCard({ finding }: { finding: FindingDTO }) {
  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm leading-relaxed">{finding.text}</p>
        <SeverityChip severity={finding.severity} />
      </div>
      {finding.citations.length > 0 ? (
        <div className="space-y-2">
          {finding.citations.map((citation, i) => (
            <CitationBlock key={i} citation={citation} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
