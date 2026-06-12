import { ShieldAlert } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type { PIISummaryDTO } from "@/lib/types";

// Advisory PII signal (§18.5). Counts + kinds only — never raw values (§18.8).
export function PiiSummary({ pii }: { pii: PIISummaryDTO }) {
  return (
    <Alert>
      <ShieldAlert className="size-4 text-amber-600" aria-hidden />
      <AlertTitle>Datos personales detectados ({pii.total})</AlertTitle>
      <AlertDescription>
        <span>
          El documento contiene posibles datos personales. Se muestran solo
          recuentos por tipo; nunca los valores. El análisis continúa igualmente.
        </span>
        <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs">
          {Object.entries(pii.counts).map(([kind, count]) => (
            <li key={kind}>
              <span className="font-medium">{kind}</span>: {count}
            </li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  );
}
