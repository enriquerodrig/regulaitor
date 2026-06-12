import { cn } from "@/lib/utils";
import { SEVERITY_LABEL } from "@/lib/labels";
import type { Severity } from "@/lib/types";

const CLS: Record<Severity, string> = {
  info: "bg-slate-100 text-slate-700 border-slate-200",
  low: "bg-sky-50 text-sky-700 border-sky-200",
  medium: "bg-amber-50 text-amber-700 border-amber-200",
  high: "bg-red-50 text-red-700 border-red-200",
};

export function SeverityChip({ severity }: { severity: Severity }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        CLS[severity],
      )}
    >
      {SEVERITY_LABEL[severity]}
    </span>
  );
}
