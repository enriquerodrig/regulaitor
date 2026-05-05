"""Unit tests for corpus/loader.py — singleton + warmup + integrity check.

Synthetic fixtures match the H1 Pydantic schema (corpus/schemas.py):
- Manifest fields: corpus, celex, version, source_format, fetched_at,
  languages, http_cache, stats, articles.
- LanguageEntry.hash format: "sha256:<hex>" (matches H1 ingest.py
  _sha256_hex). The same prefix constant ``loader._HASH_PREFIX`` is used by
  production code and these fixtures so the format stays in lockstep.

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


@pytest.fixture
def loader_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the loader at ``tmp_path`` and restrict it to ai_act only.

    Returns ``tmp_path`` so individual tests can compose paths off it. Tests
    that need multiple corpora override ``CORPORA_WITH_MANIFESTS`` directly.
    """
    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act",))
    return tmp_path


def _write_synthetic_corpus(
    tmp_path: Path,
    norma: str,
    articulo: str,
    text_es: str,
    *,
    text_en: str | None = None,
) -> None:
    """Helper: write a minimal manifest + processed JSON for a single article.

    Hash is stored in the H1 canonical format ``"sha256:<hex>"`` (uses the
    same ``loader._HASH_PREFIX`` constant as production code). Pass
    ``text_en`` to also emit an EN processed file and a manifest entry for
    the EN language (used by multi-language drift tests).
    """
    manifests = tmp_path / "manifests"
    processed = tmp_path / "processed"
    manifests.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)

    h_es = loader._HASH_PREFIX + hashlib.sha256(text_es.encode("utf-8")).hexdigest()

    languages_field: list[str] = ["es"]
    languages_entry: dict[str, dict[str, object]] = {
        "es": {
            "hash": h_es,
            "tokens": 10,
            "chunks": [],
            "embedded_at": None,
            "embedding_model": None,
            "fetched_at": "2026-05-05T00:00:00Z",
            "source_url": f"https://example.com/{norma}/{articulo}/es",
        },
    }
    if text_en is not None:
        h_en = loader._HASH_PREFIX + hashlib.sha256(text_en.encode("utf-8")).hexdigest()
        languages_field.append("en")
        languages_entry["en"] = {
            "hash": h_en,
            "tokens": 10,
            "chunks": [],
            "embedded_at": None,
            "embedding_model": None,
            "fetched_at": "2026-05-05T00:00:00Z",
            "source_url": f"https://example.com/{norma}/{articulo}/en",
        }

    manifest = {
        "corpus": norma,
        "celex": "32024R1689",
        "version": "TEST-VERSION",
        "source_format": "pdf",
        "fetched_at": "2026-05-05T00:00:00Z",
        "languages": languages_field,
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
                "languages": languages_entry,
            },
        ],
    }
    (manifests / f"{norma}.json").write_text(json.dumps(manifest), encoding="utf-8")

    processed_data_es = [
        {
            "articulo": articulo,
            "title": "Title ES",
            "text": text_es,
            "paragraphs": [{"apartado": "1", "text": text_es}],
        }
    ]
    (processed / f"{norma}_es.json").write_text(json.dumps(processed_data_es), encoding="utf-8")
    if text_en is not None:
        processed_data_en = [
            {
                "articulo": articulo,
                "title": "Title EN",
                "text": text_en,
                "paragraphs": [{"apartado": "1", "text": text_en}],
            }
        ]
        (processed / f"{norma}_en.json").write_text(json.dumps(processed_data_en), encoding="utf-8")


def test_warmup_loads_corpus(loader_paths: Path) -> None:
    _write_synthetic_corpus(loader_paths, "ai_act", "6", "Sample article text.")

    loader.warmup()

    art = loader.get_article("ai_act", "6", "es")
    assert art.articulo == "6"


def test_warmup_idempotent(loader_paths: Path) -> None:
    _write_synthetic_corpus(loader_paths, "ai_act", "6", "Sample text.")

    loader.warmup()
    loader.warmup()  # second call is no-op
    art = loader.get_article("ai_act", "6", "es")
    assert art.articulo == "6"


def test_warmup_detects_hash_drift(loader_paths: Path) -> None:
    _write_synthetic_corpus(loader_paths, "ai_act", "6", "Original text.")
    # Tamper with the processed file AFTER manifest hash was set.
    tampered = [
        {
            "articulo": "6",
            "title": "Title ES",
            "text": "TAMPERED text.",
            "paragraphs": [{"apartado": "1", "text": "TAMPERED text."}],
        }
    ]
    (loader_paths / "processed" / "ai_act_es.json").write_text(
        json.dumps(tampered), encoding="utf-8"
    )

    with pytest.raises(RuntimeError, match="hash drift"):
        loader.warmup()


def test_warmup_hash_drift_does_not_cache(loader_paths: Path) -> None:
    """Fail-closed: a hash mismatch must abort warmup before _CORPUS is
    populated, so a subsequent ``get_article`` raises 'not loaded'."""
    _write_synthetic_corpus(loader_paths, "ai_act", "6", "Original text.")
    tampered = [
        {
            "articulo": "6",
            "title": "Title ES",
            "text": "TAMPERED text.",
            "paragraphs": [{"apartado": "1", "text": "TAMPERED text."}],
        }
    ]
    (loader_paths / "processed" / "ai_act_es.json").write_text(
        json.dumps(tampered), encoding="utf-8"
    )

    with pytest.raises(RuntimeError):
        loader.warmup()

    # Fail-closed: nothing cached.
    with pytest.raises(KeyError, match="not loaded"):
        loader.get_article("ai_act", "6", "es")


def test_get_article_raises_keyerror_on_missing(loader_paths: Path) -> None:
    _write_synthetic_corpus(loader_paths, "ai_act", "6", "text.")

    loader.warmup()

    with pytest.raises(KeyError):
        loader.get_article("ai_act", "999", "es")


def test_get_paragraph_returns_text(loader_paths: Path) -> None:
    _write_synthetic_corpus(loader_paths, "ai_act", "6", "Article text.")

    loader.warmup()

    text = loader.get_paragraph("ai_act", "6", "1", "es")
    assert text == "Article text."


def test_get_paragraph_raises_on_missing_apartado(loader_paths: Path) -> None:
    _write_synthetic_corpus(loader_paths, "ai_act", "6", "Text.")

    loader.warmup()

    with pytest.raises(KeyError):
        loader.get_paragraph("ai_act", "6", "99", "es")


def test_get_manifest_meta(loader_paths: Path) -> None:
    _write_synthetic_corpus(loader_paths, "ai_act", "6", "Text.")

    loader.warmup()

    meta = loader.get_manifest_meta("ai_act")
    assert meta["version"] == "TEST-VERSION"
    # source_url is derived from the manifest's celex (canonical EUR-Lex
    # URL), so a citation always points at the official consolidated text.
    assert meta["source_url"] == (
        "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689"
    )


def test_list_articulos_sorted(loader_paths: Path) -> None:
    _write_synthetic_corpus(loader_paths, "ai_act", "6", "Text.")

    loader.warmup()

    arts = loader.list_articulos("ai_act", "es")
    assert arts == ["6"]


def test_list_apartados_document_order(loader_paths: Path) -> None:
    _write_synthetic_corpus(loader_paths, "ai_act", "6", "Text.")

    loader.warmup()

    aps = loader.list_apartados("ai_act", "6", "es")
    assert aps == ["1"]


def test_get_article_before_warmup_raises(loader_paths: Path) -> None:
    with pytest.raises(KeyError, match="not loaded"):
        loader.get_article("ai_act", "6", "es")


def test_reset_clears_state(loader_paths: Path) -> None:
    _write_synthetic_corpus(loader_paths, "ai_act", "6", "Text.")

    loader.warmup()
    loader.reset()

    with pytest.raises(KeyError, match="not loaded"):
        loader.get_article("ai_act", "6", "es")


def test_warmup_processed_file_missing_raises_runtime_error(
    loader_paths: Path,
) -> None:
    """Manifest exists, processed file deleted → RuntimeError with hint."""
    _write_synthetic_corpus(loader_paths, "ai_act", "6", "Text.")
    (loader_paths / "processed" / "ai_act_es.json").unlink()

    with pytest.raises(RuntimeError, match="processed file missing") as exc:
        loader.warmup()
    assert "make ingest" in str(exc.value)


def test_warmup_articulo_missing_in_processed(loader_paths: Path) -> None:
    """Manifest references articulo "6" but processed JSON has only "1"
    → RuntimeError with recovery guidance."""
    _write_synthetic_corpus(loader_paths, "ai_act", "6", "Text.")
    # Replace processed JSON with a different articulo id.
    other = [
        {
            "articulo": "1",
            "title": "Title ES",
            "text": "Other text.",
            "paragraphs": [{"apartado": "1", "text": "Other text."}],
        }
    ]
    (loader_paths / "processed" / "ai_act_es.json").write_text(json.dumps(other), encoding="utf-8")

    with pytest.raises(RuntimeError, match="missing articulo 6") as exc:
        loader.warmup()
    assert "make ingest" in str(exc.value)


def test_warmup_two_corpus_partial_failure_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ai_act passes, gdpr drifts → both un-cached. Fix gdpr → both load."""
    _write_synthetic_corpus(tmp_path, "ai_act", "6", "AI Act text.")
    _write_synthetic_corpus(tmp_path, "gdpr", "5", "GDPR text.")
    # Tamper gdpr's processed file so its hash drifts.
    tampered_gdpr = [
        {
            "articulo": "5",
            "title": "Title ES",
            "text": "TAMPERED GDPR.",
            "paragraphs": [{"apartado": "1", "text": "TAMPERED GDPR."}],
        }
    ]
    (tmp_path / "processed" / "gdpr_es.json").write_text(
        json.dumps(tampered_gdpr), encoding="utf-8"
    )

    monkeypatch.setattr(loader, "MANIFEST_DIR", tmp_path / "manifests")
    monkeypatch.setattr(loader, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(loader, "CORPORA_WITH_MANIFESTS", ("ai_act", "gdpr"))

    with pytest.raises(RuntimeError, match="hash drift"):
        loader.warmup()

    # Atomic publish: ai_act must NOT be cached even though it passed
    # integrity. Both corpora are unreachable on retry.
    with pytest.raises(KeyError, match="not loaded"):
        loader.get_paragraph("ai_act", "6", "1", "es")
    with pytest.raises(KeyError, match="not loaded"):
        loader.get_paragraph("gdpr", "5", "1", "es")

    # Restore gdpr's processed file so its hash matches again.
    fixed_gdpr = [
        {
            "articulo": "5",
            "title": "Title ES",
            "text": "GDPR text.",
            "paragraphs": [{"apartado": "1", "text": "GDPR text."}],
        }
    ]
    (tmp_path / "processed" / "gdpr_es.json").write_text(json.dumps(fixed_gdpr), encoding="utf-8")

    loader.warmup()
    assert loader.get_paragraph("ai_act", "6", "1", "es") == "AI Act text."
    assert loader.get_paragraph("gdpr", "5", "1", "es") == "GDPR text."


def test_warmup_multi_language_drift(loader_paths: Path) -> None:
    """Tamper with ai_act_en (not _es) → warmup detects the drift."""
    _write_synthetic_corpus(loader_paths, "ai_act", "6", "ES original.", text_en="EN original.")
    tampered_en = [
        {
            "articulo": "6",
            "title": "Title EN",
            "text": "TAMPERED EN.",
            "paragraphs": [{"apartado": "1", "text": "TAMPERED EN."}],
        }
    ]
    (loader_paths / "processed" / "ai_act_en.json").write_text(
        json.dumps(tampered_en), encoding="utf-8"
    )

    with pytest.raises(RuntimeError, match="hash drift"):
        loader.warmup()

    # Fail-closed: ES side must not be cached either.
    with pytest.raises(KeyError, match="not loaded"):
        loader.get_paragraph("ai_act", "6", "1", "es")
