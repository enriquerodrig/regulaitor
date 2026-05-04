"""Atomic load / save / diff of corpus manifests."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from regulaitor.corpus.schemas import Manifest


@dataclass(frozen=True)
class ManifestDiff:
    added_articles: list[str]
    removed_articles: list[str]
    changed_articles: list[str]
    unchanged_articles: list[str]


def load(path: Path) -> Manifest | None:
    """Load a manifest from disk, returning None if the file is absent."""
    if not path.exists():
        return None
    return Manifest.model_validate_json(path.read_text(encoding="utf-8"))


def save_atomic(path: Path, manifest: Manifest) -> None:
    """Write the manifest atomically: temp file then os.replace.

    Guarantees the target file is either the previous valid manifest or the
    new one — never a partial write. Crucial because downstream H2 reads it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    payload = manifest.model_dump_json(indent=2)
    tmp_path.write_text(payload, encoding="utf-8")
    os.replace(str(tmp_path), str(path))


def diff(old: Manifest | None, new: Manifest) -> ManifestDiff:
    """Compute per-article diff between two manifests by article_id and hash.

    An article is `changed` when its `article_id` exists in both but the union
    of language hashes differs. `unchanged` when all language hashes match.
    """
    if old is None:
        return ManifestDiff(
            added_articles=sorted(a.article_id for a in new.articles),
            removed_articles=[],
            changed_articles=[],
            unchanged_articles=[],
        )

    old_index = {a.article_id: a for a in old.articles}
    new_index = {a.article_id: a for a in new.articles}

    added = sorted(new_index.keys() - old_index.keys())
    removed = sorted(old_index.keys() - new_index.keys())

    changed: list[str] = []
    unchanged: list[str] = []
    for aid in sorted(old_index.keys() & new_index.keys()):
        old_hashes = {lang: le.hash for lang, le in old_index[aid].languages.items()}
        new_hashes = {lang: le.hash for lang, le in new_index[aid].languages.items()}
        if old_hashes == new_hashes:
            unchanged.append(aid)
        else:
            changed.append(aid)

    return ManifestDiff(
        added_articles=added,
        removed_articles=removed,
        changed_articles=changed,
        unchanged_articles=unchanged,
    )
