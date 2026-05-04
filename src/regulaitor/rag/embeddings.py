"""BGE-M3 embedder wrapper. Loads the model lazily as a module-level singleton.

The same singleton exposes the tokenizer used by `corpus/ingest.py` to count
tokens in articles (the H2 swap from tiktoken to BGE-M3 native).
"""

from __future__ import annotations

from typing import Any

from FlagEmbedding import BGEM3FlagModel

DEFAULT_MODEL = "BAAI/bge-m3"

_MODEL: Any | None = None  # BGEM3FlagModel instance after first load
_TOKENIZER: Any | None = None  # transformers.PreTrainedTokenizerFast


def _ensure_loaded(model_name: str = DEFAULT_MODEL) -> Any:
    """Load the model once and cache as a module-level singleton.

    Subsequent calls are O(1). The first call may take several seconds (model
    weights are read from `~/.cache/huggingface/`).
    """
    global _MODEL, _TOKENIZER
    if _MODEL is None:
        _MODEL = BGEM3FlagModel(model_name, use_fp16=False)
        _TOKENIZER = _MODEL.tokenizer
    return _MODEL


def embed(texts: list[str], batch_size: int = 16) -> list[list[float]]:
    """Compute BGE-M3 dense embeddings for a list of texts.

    Returns one 1024-dim vector per input, in the same order. Empty input list
    returns empty list (no model load).
    """
    if not texts:
        return []
    model = _ensure_loaded()
    out = model.encode(texts, batch_size=batch_size, return_dense=True)
    return [list(vec) for vec in out["dense_vecs"]]


def token_count(text: str) -> int:
    """Count BGE-M3 (XLM-RoBERTa) tokens in `text`. No special tokens added.

    Used by `rag.chunking` to decide split threshold and by `corpus.ingest` to
    populate the `tokens` field in manifests (replacing the H1 tiktoken proxy).
    """
    _ensure_loaded()
    assert _TOKENIZER is not None  # noqa: S101 # nosec B101  # set by _ensure_loaded
    return len(_TOKENIZER.encode(text, add_special_tokens=False))


def model_identifier(model_name: str = DEFAULT_MODEL) -> str:
    """Canonical identifier for the currently-loaded model.

    Format: 'BAAI/bge-m3@<sha256_short>' if the HF Hub commit hash is available;
    otherwise 'BAAI/bge-m3@v1.0' as a stable fallback.
    """
    model = _ensure_loaded(model_name)
    # The transformers AutoModel exposes _commit_hash on its config when loaded
    # from HF Hub. Some private builds (e.g. a re-export) won't have it.
    commit_hash: str | None = None
    try:
        commit_hash = model.model.config._commit_hash
    except AttributeError:
        commit_hash = None
    if commit_hash:
        return f"{model_name}@{commit_hash[:16]}"
    return f"{model_name}@v1.0"
