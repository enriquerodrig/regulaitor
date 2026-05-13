"""H9 — Integration smoke test for the red team runner.

Pre-populates a 1-attack JSONL + a fake PDF + stubs backend calls so the
entire pipeline (load → dispatch → aggregate → render → write) is exercised
end-to-end without LLM cost.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from redteam import runner


def test_smoke_full_pipeline_with_stubbed_backends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Stage 1: create attacks.jsonl + dummy PDF + redirect paths
    attacks_path = tmp_path / "attacks.jsonl"
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    pdf_path = documents_dir / "attack_001.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nfake content\n%%EOF")

    attack_dict = {
        "id": "attack-001",
        "scenario": 1,
        "scenario_name": "Doc ordena ignorar",
        "mode": "document",
        "payload": "attack_001.pdf",
        "expected_block_layer": "sanitizer",
        "expected_verdict": "block",
        "requires_e2e": False,
        "description": "smoke test",
        "rationale": "smoke",
    }
    attacks_path.write_text(json.dumps(attack_dict) + "\n", encoding="utf-8")

    report_path = tmp_path / "reports" / "latest.md"
    monkeypatch.setattr(runner, "_DOC_DIR", documents_dir)
    monkeypatch.setattr(runner, "_REPORT_PATH", report_path)
    monkeypatch.setattr(runner.corpus_loader, "warmup", lambda: None)

    # Stage 2: stub sanitizer to raise DocumentBlockedError (block at sanitizer layer)
    from regulaitor.citation.schemas import DocumentBlockedError

    def fake_extract(**kw):
        from unittest.mock import MagicMock

        return MagicMock()

    def fake_sanitize(raw):
        raise DocumentBlockedError(reason="metadata_malicious", sanitizer_log=[])

    monkeypatch.setattr(runner, "extractor_extract", fake_extract)
    monkeypatch.setattr(runner, "sanitizer_sanitize", fake_sanitize)

    # Stage 3: run smoke
    runner.main(attacks_path=attacks_path, smoke=True, baseline=None)

    # Stage 4: verify report exists, contains expected content
    assert report_path.exists()
    md = report_path.read_text(encoding="utf-8")
    assert "attack-001" in md
    assert "Gate §16.2 #4" in md
    assert "block_rate (final):" in md
    assert "1.00" in md  # 1/1 = 100%
    assert "✅" in md
