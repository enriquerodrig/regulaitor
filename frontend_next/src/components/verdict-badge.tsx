import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";
import type { Verdict } from "@/lib/types";

// Renders the Auditor verdict verbatim. Pure presentation: the frontend NEVER
// derives a verdict — it shows exactly what the API returned (§6 invariant).
const MAP: Record<
  Verdict,
  { label: string; cls: string; Icon: typeof CheckCircle2 }
> = {
  pass: {
    label: "Validado",
    cls: "bg-emerald-50 text-emerald-700 border-emerald-200",
    Icon: CheckCircle2,
  },
  requires_human_review: {
    label: "Requiere revisión humana",
    cls: "bg-amber-50 text-amber-700 border-amber-200",
    Icon: AlertTriangle,
  },
  block: {
    label: "Bloqueado",
    cls: "bg-red-50 text-red-700 border-red-200",
    Icon: XCircle,
  },
};

export function VerdictBadge({
  verdict,
  className,
}: {
  verdict: Verdict;
  className?: string;
}) {
  const { label, cls, Icon } = MAP[verdict];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-sm font-medium",
        cls,
        className,
      )}
    >
      <Icon className="size-4" aria-hidden />
      {label}
    </span>
  );
}
