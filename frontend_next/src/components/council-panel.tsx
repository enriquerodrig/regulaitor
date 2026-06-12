import { Users } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { VERDICT_LABEL, agreementLabel, triggerLabel } from "@/lib/labels";
import type { CouncilReviewDTO, JudgeVoteDTO } from "@/lib/types";

const VOTE_CLS: Record<JudgeVoteDTO["vote"], string> = {
  pass: "bg-emerald-50 text-emerald-700 border-emerald-200",
  requires_human_review: "bg-amber-50 text-amber-700 border-amber-200",
  block: "bg-red-50 text-red-700 border-red-200",
};

function VoteChip({ judge }: { judge: JudgeVoteDTO }) {
  if (!judge.ok) {
    return (
      <span className="inline-flex items-center rounded-md border bg-muted px-2 py-0.5 text-xs text-muted-foreground">
        sin respuesta{judge.error_category ? ` (${judge.error_category})` : ""}
      </span>
    );
  }
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        VOTE_CLS[judge.vote],
      )}
    >
      {VERDICT_LABEL[judge.vote]}
    </span>
  );
}

// Advisory Council record (H13). Renders only when triggered. The divergence
// notice (council_notice) is surfaced once by the caller, not here.
export function CouncilPanel({ council }: { council: CouncilReviewDTO }) {
  if (!council.triggered) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Users className="size-4 text-primary" aria-hidden />
          Revisión colegiada (Council)
        </CardTitle>
        <CardDescription>
          Veredicto del panel:{" "}
          <strong className="text-foreground">
            {VERDICT_LABEL[council.council_verdict]}
          </strong>{" "}
          · acuerdo: {agreementLabel(council.agreement)} · activado por{" "}
          {triggerLabel(council.trigger_reason)}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <ul className="space-y-2">
          {council.judges.map((judge, i) => (
            <li
              key={i}
              className="flex items-start justify-between gap-3 rounded-md border p-2 text-sm"
            >
              <div className="min-w-0">
                <div className="font-medium">
                  {judge.provider} · {judge.model_id}
                </div>
                {judge.reason ? (
                  <div className="text-xs text-muted-foreground">{judge.reason}</div>
                ) : null}
              </div>
              <VoteChip judge={judge} />
            </li>
          ))}
        </ul>
        {council.reason ? (
          <p className="text-xs text-muted-foreground">{council.reason}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
