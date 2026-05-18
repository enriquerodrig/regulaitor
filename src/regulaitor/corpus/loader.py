"""Lazy in-memory singleton for corpus manifests + processed JSON.

Loaded once at process startup via :func:`warmup`. Recomputes SHA256 of each
processed-article text and validates against the hash recorded in the
manifest; on any mismatch a ``RuntimeError`` is raised so the caller (the
MCP server boot path) fails to start.

Decision log: 2026-05-05 entry "Corpus loader: lazy singleton + warmup
explicit + integrity check fail-closed". Spec §4.1, §7.

Hash format note: H1's ``corpus/ingest.py`` writes hashes as
``"sha256:<hex>"`` (see ``_sha256_hex``). The integrity check below produces
the same prefixed string before comparing, so the loader is symmetric with
the writer.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from regulaitor.corpus import manifest as manifest_mod
from regulaitor.corpus.schemas import ArticleEntry, Language, Manifest, Norma

CORPUS_ROOT = Path("corpus")
MANIFEST_DIR = CORPUS_ROOT / "manifests"
PROCESSED_DIR = CORPUS_ROOT / "processed"

CORPORA_WITH_MANIFESTS: tuple[Norma, ...] = ("ai_act", "gdpr", "nis2", "dora")

# Canonical hash prefix used by H1 ingest.py and recomputed during warmup.
# Exposed at module scope so tests share the same constant.
_HASH_PREFIX = "sha256:"

# Recovery guidance appended to integrity-failure messages so operators have
# a single, copy-pasteable remediation path.
_RECOVERY_HINT = "Run `make ingest` to refresh manifest, or restore corpus/processed/ from git-lfs."

# EUR-Lex canonical URL template keyed by CELEX. Used by get_manifest_meta to
# expose a single, citation-grade source_url per corpus.
_EURLEX_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"

# Module-level singletons. Production code never mutates these directly; the
# only writers are warmup() (populate) and reset() (test-only teardown).
_CORPUS: dict[Norma, Manifest] = {}
_PROCESSED_CACHE: dict[tuple[Norma, Language], list[dict[str, Any]]] = {}


def reset() -> None:
    """Clear singleton state. Test-only; production code never calls this."""
    _CORPUS.clear()
    _PROCESSED_CACHE.clear()


def warmup() -> None:
    """Load all manifests + processed JSON; verify hash integrity.

    Idempotent: a second call with the same files is a no-op (state already
    populated).

    Raises:
        RuntimeError: if a manifest is missing, a processed file is missing,
            a referenced articulo is absent from the processed JSON, or if
            the SHA256 of any processed article disagrees with the hash
            recorded in the manifest. The error message identifies the
            offending article and includes a recovery path
            (``make ingest`` or restore ``corpus/processed/`` from git-lfs).

    Atomic publish: state is staged in a local dict during the loop and only
    committed to the module singletons after every corpus passes integrity.
    A partial failure leaves the previous (possibly empty) singleton state
    untouched, so a retry will re-run the full loop instead of silently
    skipping unloaded corpora.
    """
    if _CORPUS:
        return

    loaded: dict[Norma, Manifest] = {}
    loaded_processed: dict[tuple[Norma, Language], list[dict[str, Any]]] = {}

    for norma in CORPORA_WITH_MANIFESTS:
        manifest_path = MANIFEST_DIR / f"{norma}.json"
        m = manifest_mod.load(manifest_path)
        if m is None:
            raise RuntimeError(
                f"manifest not found for {norma} at {manifest_path}. "
                f"Run `make ingest` to create it."
            )
        for article in m.articles:
            for lang, entry in article.languages.items():
                try:
                    processed_text = _read_article_text(
                        loaded_processed, norma, article.articulo, lang
                    )
                except FileNotFoundError as e:
                    raise RuntimeError(
                        f"processed file missing for {norma}/{lang} "
                        f"(expected at {e.filename}). {_RECOVERY_HINT}"
                    ) from e
                except KeyError as e:
                    raise RuntimeError(
                        f"processed JSON for {norma}/{lang} is missing "
                        f"articulo {article.articulo} referenced by manifest. "
                        f"{_RECOVERY_HINT}"
                    ) from e
                computed = _HASH_PREFIX + hashlib.sha256(processed_text.encode("utf-8")).hexdigest()
                if computed != entry.hash:
                    raise RuntimeError(
                        f"manifest hash drift detected on {norma} art. "
                        f"{article.articulo} {lang} (expected "
                        f"{entry.hash[:16]}..., got {computed[:16]}...). "
                        f"{_RECOVERY_HINT}"
                    )
        loaded[norma] = m

    # Atomic commit: only after every corpus has passed integrity do we
    # publish to the module-level singletons. This prevents a half-populated
    # _CORPUS from short-circuiting the early-return guard above on retry.
    _CORPUS.update(loaded)
    _PROCESSED_CACHE.update(loaded_processed)


def _read_article_text(
    cache: dict[tuple[Norma, Language], list[dict[str, Any]]],
    norma: Norma,
    articulo: str,
    language: Language,
) -> str:
    """Read article text from processed JSON, populating ``cache`` in-place.

    Used by :func:`warmup` against a *local* staging dict so unverified data
    never reaches the module singleton ``_PROCESSED_CACHE``. Raises
    ``FileNotFoundError`` if the processed file is absent and ``KeyError`` if
    the articulo is not present in the loaded JSON; :func:`warmup` wraps both
    as ``RuntimeError`` with recovery guidance.
    """
    key = (norma, language)
    if key not in cache:
        path = PROCESSED_DIR / f"{norma}_{language}.json"
        with path.open("r", encoding="utf-8") as f:
            cache[key] = json.load(f)
    for art in cache[key]:
        if art["articulo"] == articulo:
            return str(art["text"])
    raise KeyError(f"processed article not found: {norma} art. {articulo} {language}")


def get_manifest(norma: Norma) -> Manifest:
    """Return the parsed manifest for ``norma``.

    Raises:
        KeyError: if the corpus has not been warmed up yet.
    """
    if norma not in _CORPUS:
        raise KeyError(f"corpus {norma} not loaded; call warmup() first")
    return _CORPUS[norma]


def get_article(norma: Norma, articulo: str, language: Language) -> ArticleEntry:
    """Return the article entry that has ``language`` available.

    Raises:
        KeyError: if the article id or language is absent (with a hint
            listing the first few valid articulo ids).
    """
    m = get_manifest(norma)
    for a in m.articles:
        if a.articulo == articulo and language in a.languages:
            return a
    all_valid = list_articulos(norma, language)
    valid = all_valid[:10]
    suffix = "..." if len(all_valid) > 10 else ""
    raise KeyError(
        f"{norma} has no articulo {articulo} in language {language}. "
        f"Valid articulos: {valid}{suffix}"
    )


def get_paragraph(norma: Norma, articulo: str, apartado: str, language: Language) -> str:
    """Return the paragraph text from the processed JSON cache.

    The cache is populated by :func:`warmup`; calling this before warmup
    raises ``KeyError`` rather than triggering a lazy load (the MCP boot
    path must run warmup explicitly so integrity errors abort startup).

    The membership check covers both ``_CORPUS`` (manifest verified) and
    ``_PROCESSED_CACHE`` (text loaded). Gating on ``_CORPUS`` ensures
    unverified data is unreachable even if the cache was somehow populated
    out of band.

    Raises:
        KeyError: if the corpus is not loaded, the articulo is absent, or
            the apartado is absent within the articulo.
    """
    key = (norma, language)
    if norma not in _CORPUS or key not in _PROCESSED_CACHE:
        raise KeyError(f"corpus {norma}/{language} not loaded; call warmup() first")
    for art in _PROCESSED_CACHE[key]:
        if art["articulo"] == articulo:
            for p in art["paragraphs"]:
                if p["apartado"] == apartado:
                    return str(p["text"])
            valid = list_apartados(norma, articulo, language)
            raise KeyError(
                f"{norma} art. {articulo} {language} has no apartado "
                f"{apartado}. Valid apartados: {valid}."
            )
    raise KeyError(f"{norma} has no articulo {articulo} in language {language}.")


def get_manifest_meta(norma: Norma) -> dict[str, str]:
    """Return ``{'version': ..., 'source_url': ...}`` for the corpus.

    ``source_url`` is the canonical EUR-Lex URL derived from the manifest's
    CELEX identifier, so it is the same for every article and stable across
    re-ingestions of the same regulation. The EN landing page is used
    deliberately: EN is the canonical EUR-Lex URL and ES citations still
    resolve correctly via the ``?lang=es`` query parameter (future
    enhancement if per-language source_url is needed).
    """
    m = get_manifest(norma)
    return {
        "version": m.version,
        "source_url": _EURLEX_URL.format(celex=m.celex),
    }


def list_articulos(norma: Norma, language: Language) -> list[str]:
    """Sorted list of articulo ids available for ``(norma, language)``.

    Returns an empty list if the corpus has not been warmed up.
    """
    if norma not in _CORPUS:
        return []
    return sorted(a.articulo for a in _CORPUS[norma].articles if language in a.languages)


def list_apartados(norma: Norma, articulo: str, language: Language) -> list[str]:
    """Apartado ids for ``(norma, articulo, language)`` in document order.

    Returns the apartados as written in the processed JSON (no sorting):
    apartados may include non-numeric ids such as ``"considerando"`` for
    which lexical sort would be misleading.

    Returns an empty list if the corpus is not loaded or the articulo is
    absent. Gates on ``_CORPUS`` so unverified data is unreachable.
    """
    key = (norma, language)
    if norma not in _CORPUS or key not in _PROCESSED_CACHE:
        return []
    for art in _PROCESSED_CACHE[key]:
        if art["articulo"] == articulo:
            return [str(p["apartado"]) for p in art["paragraphs"]]
    return []


def get_article_text(norma: Norma, articulo: str, language: Language) -> str:
    """Return the full article text (all paragraphs joined by ``\\n\\n``).

    Used by :mod:`regulaitor.citation.validator` when no apartado is given in
    the citation. The real ``ArticleEntry`` (from the manifest) carries no
    text payload, so we reconstruct it by concatenating the processed-JSON
    paragraphs in document order.

    Raises:
        KeyError: if the corpus has not been warmed up, or the articulo is
            absent for ``(norma, language)``.
    """
    key = (norma, language)
    if norma not in _CORPUS or key not in _PROCESSED_CACHE:
        raise KeyError(f"corpus {norma}/{language} not loaded; call warmup() first")
    for art in _PROCESSED_CACHE[key]:
        if art["articulo"] == articulo:
            return "\n\n".join(str(p["text"]) for p in art["paragraphs"])
    raise KeyError(f"{norma} has no articulo {articulo} in language {language}.")
