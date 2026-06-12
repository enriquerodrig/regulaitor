import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { SanitizerEventDTO } from "@/lib/types";

const SEVERITY_CLS: Record<SanitizerEventDTO["severity"], string> = {
  info: "text-slate-600",
  warning: "text-amber-700",
  critical: "text-red-700 font-medium",
};

// Document sanitizer events (§18.1). Category + severity + content hash only —
// location and raw reason are redacted upstream (SSDLC).
export function SanitizerLog({ events }: { events: SanitizerEventDTO[] }) {
  if (events.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Sin eventos del sanitizador.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Categoría</TableHead>
            <TableHead>Severidad</TableHead>
            <TableHead>Hash</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {events.map((event, i) => (
            <TableRow key={i}>
              <TableCell className="font-mono text-xs">{event.category}</TableCell>
              <TableCell className={cn("text-xs", SEVERITY_CLS[event.severity])}>
                {event.severity}
              </TableCell>
              <TableCell className="font-mono text-xs text-muted-foreground">
                {event.content_hash.slice(0, 12)}…
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
