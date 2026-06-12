import { AnswerBlock } from "@/components/answer-block";
import { AuditTable } from "@/components/audit-table";
import { VerdictBadge } from "@/components/verdict-badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { skipLabel } from "@/lib/labels";
import type { SegmentResultDTO } from "@/lib/types";

export function SegmentCard({ segment }: { segment: SegmentResultDTO }) {
  const meta = [
    `${segment.latency_ms} ms`,
    `${segment.cost_eur.toFixed(4)} €`,
    segment.skipped ? `omitido (${skipLabel(segment.skip_category)})` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  const hasBody =
    !segment.skipped && (segment.answer !== null || segment.audit_results.length > 0);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base">
            Segmento {segment.segment_id}
            {segment.title ? `: ${segment.title}` : ""}
          </CardTitle>
          {segment.verdict ? <VerdictBadge verdict={segment.verdict} /> : null}
        </div>
        <CardDescription>{meta}</CardDescription>
      </CardHeader>
      {hasBody ? (
        <CardContent className="space-y-4">
          {segment.answer ? <AnswerBlock answer={segment.answer} /> : null}
          {segment.audit_results.length > 0 ? (
            <AuditTable results={segment.audit_results} />
          ) : null}
        </CardContent>
      ) : null}
    </Card>
  );
}
