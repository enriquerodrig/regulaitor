"""Unit tests for corpus/loader.py — singleton + warmup + integrity check.

Synthetic fixtures match the H1 Pydantic schema (corpus/schemas.py):
- Manifest fields: corpus, celex, version, source_format, fetched_at,
  languages, http_cache, stats, articles.
- LanguageEntry.hash format: "sha256:<hex>" (matches H1 ingest.py
  _sha256_hex).

Hash drift is exercised by writing a manifest first, then mutating
corpus/processed/<norma>_<lang>.json so warmup() recomputes a different
SHA256 than the one stored in the manifest.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from regulaitor.corpus import loader


@pytest.fixture(autouse=True)
def reset_loader_singleton() -> Iterator[None]:
    """Reset the loader singleton between tests."""
    loader.reset()
    yield
    loader.reset()


def _write_synthetic_corpus(tmp_path: Path, norma: str, articulo: str, text_es: str) -> None:
    """Helper: write a minimal manifest + processed JSON for a single article.

    Hash is stored in the H1 canonical format ``"sha256:<hex>"``.
    """
    manifests = tmp_path / "manifests"
    processed = tmp_path / "processed"
    manifests.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)

    h = "sha256:" + hashlib.sha256(text_es.encode("utf-8")).hexdigest()

    manifest = {
        "corpus": norma,
        "celex": "32024R1689",
        "version": "TEST-VERSION",
        "source_format": "pdf",
        "fetched_at": "2026-05-05T00:00:00Z",
        "languages": ["es"],
        "http_cache": {},
        "stats": {
            "articles_total": 1,
            "chunks_total": 0,
            "embedded_total": 0,
            "raw_size_bytes": len(text_es.encode("utf-8")),
        },
        "articles": [
            {
                "article_id": f"{norma}.{articulo}",
                "articulo": articulo,
                "title_es": "Title ES",
                "title_en": "Title EN",
                "languages": {
                    "es": {
                        "hash": h,
                        "tokens": 10,
                        "chunks": [],
                        "embedded_at": None,
                        "embedding_model": None,
                        "fetched_at": "2026-05-05T00:00:00Z",
                        "source_url": f"https://example.com/{norma}/{articulo}/es",
                    },
                },
            },
        ],
    }
    (manifests / f"{norma}.json").write_text(json.dumps(manifest), encoding="utf-8")

    processed_data = [
        {
            "articulo": articulo,
            "title": "Title ES",
            "text": text_es,
            "paragraphs": [{"apartado": "1", "text": text_es}],
        }
    ]
    (processed / f"{norma}_es.json").write_text(json.dumps(processed_data), encoding="utf-8")


def test_warmup_loads_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "Sample article text.")
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    loader.warmup()

    art = loader.get_article("ai_act", "6", "es")
    assert art.articulo == "6"


def test_warmup_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "Sample text.")
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    loader.warmup()
    loader.warmup()  # second call is no-op
    art = loader.get_article("ai_act", "6", "es")
    assert art.articulo == "6"


def test_warmup_detects_hash_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "Original text.")
    # Tamper with the processed file AFTER manifest hash was set.
    tampered = [
        {
            "articulo": "6",
            "title": "Title ES",
            "text": "TAMPERED text.",
            "paragraphs": [{"apartado": "1", "text": "TAMPERED text."}],
        }
    ]
    (tmp_path / "processed" / "ai_act_es.json").write_text(json.dumps(tampered), encoding="utf-8")

    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    with pytest.raises(RuntimeError, match="hash drift"):
        loader.warmup()


def test_warmup_hash_drift_does_not_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail-closed: a hash mismatch must abort warmup before _CORPUS is
    populated, so a subsequent ``get_article`` raises 'not loaded'."""
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "Original text.")
    tampered = [
        {
            "articulo": "6",
            "title": "Title ES",
            "text": "TAMPERED text.",
            "paragraphs": [{"apartado": "1", "text": "TAMPERED text."}],
        }
    ]
    (tmp_path / "processed" / "ai_act_es.json").write_text(json.dumps(tampered), encoding="utf-8")

    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    with pytest.raises(RuntimeError):
        loader.warmup()

    # Fail-closed: nothing cached.
    with pytest.raises(KeyError, match="not loaded"):
        loader.get_article("ai_act", "6", "es")


def test_get_article_raises_keyerror_on_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "text.")
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    loader.warmup()

    with pytest.raises(KeyError):
        loader.get_article("ai_act", "999", "es")


def test_get_paragraph_returns_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "Article text.")
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    loader.warmup()

    text = loader.get_paragraph("ai_act", "6", "1", "es")
    assert text == "Article text."


def test_get_paragraph_raises_on_missing_apartado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "Text.")
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    loader.warmup()

    with pytest.raises(KeyError):
        loader.get_paragraph("ai_act", "6", "99", "es")


def test_get_manifest_meta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "Text.")
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    loader.warmup()

    meta = loader.get_manifest_meta("ai_act")
    assert meta["version"] == "TEST-VERSION"
    # source_url is derived from the manifest's celex (canonical EUR-Lex
    # URL), so a citation always points at the official consolidated text.
    assert meta["source_url"] == (
        "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689"
    )


def test_list_articulos_sorted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "Text.")
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    loader.warmup()

    arts = loader.list_articulos("ai_act", "es")
    assert arts == ["6"]


def test_list_apartados_document_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "Text.")
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    loader.warmup()

    aps = loader.list_apartados("ai_act", "6", "es")
    assert aps == ["1"]


def test_get_article_before_warmup_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    with pytest.raises(KeyError, match="not loaded"):
        loader.get_article("ai_act", "6", "es")


def test_reset_clears_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "Text.")
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))

    loader.warmup()
    loader.reset()

    with pytest.raises(KeyError, match="not loaded"):
        loader.get_article("ai_act", "6", "es")
