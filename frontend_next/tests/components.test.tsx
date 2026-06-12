import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnswerBlock } from "@/components/answer-block";
import { AuditTable } from "@/components/audit-table";
import { CorpusChip } from "@/components/corpus-chip";
import { CouncilPanel } from "@/components/council-panel";
import { FindingCard } from "@/components/finding-card";
import { PiiSummary } from "@/components/pii-summary";
import { SanitizerLog } from "@/components/sanitizer-log";
import { SegmentCard } from "@/components/segment-card";
import { SeverityChip } from "@/components/severity-chip";
import type {
  AuditResultDTO,
  CitationDTO,
  CouncilReviewDTO,
  FindingDTO,
  PIISummaryDTO,
  SanitizerEventDTO,
  SegmentResultDTO,
} from "@/lib/types";

const citation: CitationDTO = {
  norma: "ai_act",
  articulo: "6",
  apartado: "1",
  language: "es",
  text: "Los sistemas de IA de alto riesgo cumplirán los requisitos…",
};

const auditValid: AuditResultDTO = {
  citation,
  validated: true,
  article_exists: true,
  apartado_exists: true,
  text_normalized_match: true,
  reason: null,
};

const finding: FindingDTO = {
  text: "El documento no documenta la evaluación de impacto.",
  citations: [citation],
  severity: "high",
};

describe("CorpusChip", () => {
  it("renders the human label and accent colour", () => {
    render(<CorpusChip norma="ai_act" />);
    const chip = screen.getByText("AI Act");
    expect(chip).toHaveStyle({ color: "#1E40AF" });
  });

  it("falls back to the raw key for an unknown corpus", () => {
    render(<CorpusChip norma="weird" />);
    expect(screen.getByText("weird")).toBeInTheDocument();
  });
});

describe("SeverityChip", () => {
  it("maps high to the Spanish label", () => {
    render(<SeverityChip severity="high" />);
    expect(screen.getByText("Alta")).toBeInTheDocument();
  });
});

describe("AuditTable", () => {
  it("renders the citation reference and a positive validity mark", () => {
    render(<AuditTable results={[auditValid]} />);
    expect(screen.getByText("AI Act 6.1")).toBeInTheDocument();
    expect(screen.getAllByLabelText("sí").length).toBeGreaterThan(0);
  });

  it("shows a negative mark when a citation is invalid", () => {
    render(
      <AuditTable
        results={[{ ...auditValid, validated: false, text_normalized_match: false }]}
      />,
    );
    expect(screen.getAllByLabelText("no").length).toBeGreaterThan(0);
  });

  it("renders nothing for an empty result set", () => {
    const { container } = render(<AuditTable results={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("AnswerBlock", () => {
  it("renders a sober fallback when there is no text and no findings", () => {
    render(<AnswerBlock answer={{ text: "", findings: [] }} />);
    expect(screen.getByText("Sin contenido para mostrar.")).toBeInTheDocument();
  });

  it("does not show the fallback when there is text", () => {
    render(<AnswerBlock answer={{ text: "Hay contenido.", findings: [] }} />);
    expect(screen.queryByText("Sin contenido para mostrar.")).toBeNull();
  });
});

describe("FindingCard", () => {
  it("renders the finding text, severity and its citation", () => {
    render(<FindingCard finding={finding} />);
    expect(screen.getByText(/evaluación de impacto/)).toBeInTheDocument();
    expect(screen.getByText("Alta")).toBeInTheDocument();
    expect(screen.getByText("Art. 6.1")).toBeInTheDocument();
  });
});

describe("CouncilPanel", () => {
  const council: CouncilReviewDTO = {
    triggered: true,
    trigger_reason: "high_severity",
    judges: [
      {
        model_id: "haiku-4.5",
        provider: "anthropic",
        vote: "pass",
        reason: "La cita respalda la afirmación.",
        ok: true,
        error_category: null,
      },
    ],
    council_verdict: "pass",
    agreement: "unanimous",
    diverges_from_auditor: false,
    reason: "Panel de acuerdo.",
  };

  it("renders judges and the panel verdict when triggered", () => {
    render(<CouncilPanel council={council} />);
    expect(screen.getByText(/Revisión colegiada/)).toBeInTheDocument();
    expect(screen.getByText(/anthropic · haiku-4.5/)).toBeInTheDocument();
  });

  it("renders nothing when not triggered", () => {
    const { container } = render(
      <CouncilPanel council={{ ...council, triggered: false }} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});

describe("PiiSummary", () => {
  it("shows counts by kind but never raw values", () => {
    const pii: PIISummaryDTO = { total: 3, counts: { email: 2, phone: 1 } };
    render(<PiiSummary pii={pii} />);
    expect(screen.getByText(/Datos personales detectados \(3\)/)).toBeInTheDocument();
    expect(screen.getByText("email")).toBeInTheDocument();
  });
});

describe("SanitizerLog", () => {
  it("renders sanitizer categories", () => {
    const events: SanitizerEventDTO[] = [
      { severity: "warning", category: "metadata_stripped", content_hash: "abcdef1234567890" },
    ];
    render(<SanitizerLog events={events} />);
    expect(screen.getByText("metadata_stripped")).toBeInTheDocument();
  });

  it("shows an empty-state message with no events", () => {
    render(<SanitizerLog events={[]} />);
    expect(screen.getByText(/Sin eventos/)).toBeInTheDocument();
  });
});

describe("SegmentCard", () => {
  it("renders the segment verdict and its answer", () => {
    const segment: SegmentResultDTO = {
      segment_id: 1,
      title: "Introducción",
      skipped: false,
      skip_category: "clean",
      answer: { text: "Análisis del segmento.", findings: [finding] },
      verdict: "requires_human_review",
      audit_results: [auditValid],
      latency_ms: 1200,
      cost_eur: 0.0123,
    };
    render(<SegmentCard segment={segment} />);
    expect(screen.getByText(/Segmento 1: Introducción/)).toBeInTheDocument();
    expect(screen.getByText("Requiere revisión humana")).toBeInTheDocument();
    expect(screen.getByText(/Análisis del segmento/)).toBeInTheDocument();
  });
});
