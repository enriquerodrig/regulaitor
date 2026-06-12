import { AlertTriangle } from "lucide-react";

// Persistent legal notice (CLAUDE.md §3): the system does not replace a lawyer.
// Rendered on every surface (login footer + app shell footer).
export function LegalDisclaimer() {
  return (
    <footer className="border-t bg-muted/40">
      <div className="mx-auto flex max-w-5xl gap-2 px-4 py-4 text-xs text-muted-foreground">
        <AlertTriangle
          className="mt-0.5 size-4 shrink-0 text-amber-600"
          aria-hidden
        />
        <p>
          RegulAItor es una herramienta de apoyo al análisis de cumplimiento
          normativo.{" "}
          <strong className="font-medium text-foreground">
            No sustituye el asesoramiento jurídico profesional.
          </strong>{" "}
          Cada afirmación se respalda con una cita textual verificada contra el
          corpus normativo oficial; aun así, las decisiones legales deben
          validarse con un profesional cualificado.
        </p>
      </div>
    </footer>
  );
}
