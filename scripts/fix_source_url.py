"""One-time fix: replace the leaked `file:///…/corpus/raw/…` source_url in the
committed manifests + LanceDB index with the canonical EUR-Lex CELEX URL (P2.2).

The `--use-local-only` ingest path (used since H14, when EUR-Lex's WAF blocked
fetching) recorded the operator's local file URI as the provenance source_url, which
(a) leaks the dev home dir into committed artifacts and (b) is the wrong link for a
user/auditor verifying a citation. registry.canonical_source_url is now the single
source of truth; ingest.py records it going forward. This patches the existing data.

§6-safe: source_url is provenance metadata, never used by the validator/Auditor (which
match on `text`); embeddings + text are preserved untouched.

Run once: `uv run python scripts/fix_source_url.py`
"""

from __future__ import annotations

import shutil
from pathlib import Path

import lancedb
import pyarrow as pa

from regulaitor.corpus import manifest as manifest_mod
from regulaitor.corpus.registry import canonical_source_url
from regulaitor.rag.retrieval import INDEX_PATH
from regulaitor.rag.store import TABLE_NAME


def _fix_manifests() -> None:
    for path in sorted(Path("corpus/manifests").glob("*.json")):
        m = manifest_mod.load(path)
        if m is None:
            raise RuntimeError(f"failed to load manifest {path}")
        new_articles = [
            a.model_copy(
                update={
                    "languages": {
                        lang: le.model_copy(
                            update={"source_url": canonical_source_url(m.corpus, lang)}
                        )
                        for lang, le in a.languages.items()
                    }
                }
            )
            for a in m.articles
        ]
        manifest_mod.save_atomic(path, m.model_copy(update={"articles": new_articles}))
        print(f"manifest fixed: {path.name} ({len(new_articles)} articles)")


def _fix_index() -> None:
    snapshot = INDEX_PATH.with_name(INDEX_PATH.name + ".bak")
    if snapshot.exists():
        shutil.rmtree(snapshot)
    shutil.copytree(INDEX_PATH, snapshot)  # safety net
    try:
        db = lancedb.connect(str(INDEX_PATH))
        tbl = db.open_table(TABLE_NAME)
        arrow = tbl.to_arrow()
        normas = arrow.column("norma").to_pylist()
        langs = arrow.column("language").to_pylist()
        new_urls = [canonical_source_url(n, lang) for n, lang in zip(normas, langs, strict=True)]
        col_idx = arrow.schema.get_field_index("source_url")
        fixed = arrow.set_column(col_idx, "source_url", pa.array(new_urls, type=pa.string()))
        db.drop_table(TABLE_NAME)
        db.create_table(TABLE_NAME, fixed)
        # Verify: row count + no file:/// remain + embeddings preserved (dim 1024).
        check = db.open_table(TABLE_NAME).to_arrow()
        assert check.num_rows == arrow.num_rows, "row count changed"
        assert not any("file://" in u for u in check.column("source_url").to_pylist())
        assert check.column("embedding").type.list_size == 1024
        print(f"index fixed: {check.num_rows} rows, source_url canonical, embeddings intact")
    except Exception:
        shutil.rmtree(INDEX_PATH, ignore_errors=True)
        shutil.copytree(snapshot, INDEX_PATH)  # restore
        raise
    finally:
        shutil.rmtree(snapshot, ignore_errors=True)


def main() -> None:
    _fix_manifests()
    _fix_index()


if __name__ == "__main__":
    main()
