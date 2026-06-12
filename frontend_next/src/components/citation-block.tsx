import { CorpusChip } from "@/components/corpus-chip";
import { articleRef } from "@/lib/labels";
import type { CitationDTO } from "@/lib/types";

function reference(citation: CitationDTO): string {
  return `Art. ${articleRef(citation.articulo, citation.apartado)}`;
}

export function CitationBlock({ citation }: { citation: CitationDTO }) {
  return (
    <div className="rounded-md border bg-muted/30 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <CorpusChip norma={citation.norma} />
        <span className="font-medium">{reference(citation)}</span>
        <span className="text-xs uppercase text-muted-foreground">
          {citation.language}
        </span>
      </div>
      <blockquote className="mt-2 border-l-2 border-primary/30 pl-3 text-muted-foreground italic">
        {citation.text}
      </blockquote>
    </div>
  );
}
