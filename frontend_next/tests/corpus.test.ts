import { describe, expect, it } from "vitest";

import { CORPORA, CORPUS_LABELS, DOC_CORPORA, corpusLabel } from "@/lib/corpus";

describe("corpus metadata", () => {
  it("has the 9 normas + auto", () => {
    expect(CORPORA).toHaveLength(10);
    expect(CORPORA.some((c) => c.value === "auto")).toBe(true);
  });

  it("DOC_CORPORA excludes auto (the /analyze backend rejects it)", () => {
    expect(DOC_CORPORA).toHaveLength(9);
    expect(DOC_CORPORA.some((c) => c.value === "auto")).toBe(false);
  });

  it("labels cover known normas", () => {
    expect(CORPUS_LABELS.ai_act).toBe("AI Act");
    expect(CORPUS_LABELS.amlr).toBe("AMLR");
    expect(CORPUS_LABELS.mica).toBe("MiCA");
  });

  it("every accent is a 6-digit hex", () => {
    for (const c of CORPORA) {
      expect(c.color).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });

  it("corpusLabel falls back to the raw key when unknown", () => {
    expect(corpusLabel("ai_act")).toBe("AI Act");
    expect(corpusLabel("unknown_corpus")).toBe("unknown_corpus");
  });
});
