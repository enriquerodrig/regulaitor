import { AlertTriangle, Lock } from "lucide-react";

// Persistent legal + privacy notice (CLAUDE.md §3 + roadmap P2.4).
// Rendered on every surface (login footer + app shell footer).
export function LegalDisclaimer() {
  return (
    <footer className="border-t bg-muted/40">
      <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-4 text-xs text-muted-foreground">
        <div className="flex gap-2">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden />
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
        <div className="flex gap-2">
          <Lock className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden />
          <p>
            <strong className="font-medium text-foreground">Privacidad.</strong>{" "}
            La sesión usa una única cookie funcional (httpOnly, SameSite=Strict); no
            hay cookies de seguimiento ni analítica de terceros. Las consultas no se
            almacenan en texto — sólo su hash SHA-256 en la traza de auditoría opcional.
            Si detectamos datos personales en una consulta te avisamos (recuentos,
            nunca el valor).
          </p>
        </div>
      </div>
    </footer>
  );
}
