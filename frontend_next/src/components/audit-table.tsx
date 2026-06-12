import { Check, X } from "lucide-react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { corpusLabel } from "@/lib/corpus";
import { articleRef } from "@/lib/labels";
import type { AuditResultDTO, CitationDTO } from "@/lib/types";

function BoolCell({ value }: { value: boolean | null }) {
  if (value === null) {
    return <span className="text-muted-foreground">—</span>;
  }
  return value ? (
    <Check className="size-4 text-emerald-600" aria-label="sí" role="img" />
  ) : (
    <X className="size-4 text-red-600" aria-label="no" role="img" />
  );
}

function reference(citation: CitationDTO): string {
  return `${corpusLabel(citation.norma)} ${articleRef(citation.articulo, citation.apartado)}`;
}

// Per-citation audit detail — the §6 enforcement made visible. The values are
// the Auditor's, rendered verbatim (the frontend derives nothing).
export function AuditTable({ results }: { results: AuditResultDTO[] }) {
  if (results.length === 0) return null;
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Cita</TableHead>
            <TableHead className="text-center">Válida</TableHead>
            <TableHead className="text-center">Artículo</TableHead>
            <TableHead className="text-center">Apartado</TableHead>
            <TableHead className="text-center">Texto</TableHead>
            <TableHead>Motivo</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {results.map((result, i) => (
            <TableRow key={i}>
              <TableCell className="font-medium">{reference(result.citation)}</TableCell>
              <TableCell className="text-center">
                <BoolCell value={result.validated} />
              </TableCell>
              <TableCell className="text-center">
                <BoolCell value={result.article_exists} />
              </TableCell>
              <TableCell className="text-center">
                <BoolCell value={result.apartado_exists} />
              </TableCell>
              <TableCell className="text-center">
                <BoolCell value={result.text_normalized_match} />
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {result.reason ?? "—"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
