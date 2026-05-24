"""v0.1.21.2 — RetrievalConfig default flips (per-norma cap + top_k_auto).

Tests verify the production-default flips of retrieval configuration parameters
introduced in v0.1.11 (per-norma cap) and v0.1.12 (top_k_auto). Prior versions
allowed these via opt-in; v0.1.21.2 makes them the default.

Backward-compat: opt-out via explicit None reverts to v0.1.10/v0.1.11 behavior.
"""

from src.regulaitor.rag.retrieval import RetrievalConfig


class TestRetrievalDefaults:
    """v0.1.21.2 default flips for per-norma cap and top_k_auto."""

    def test_default_max_chunks_per_norma_is_2(self):
        """RetrievalConfig() default has max_chunks_per_norma=2 (v0.1.21.2 flip)."""
        cfg = RetrievalConfig()
        assert cfg.max_chunks_per_norma == 2, (
            "v0.1.21.2 flip: per-norma cap defaults to 2 (v0.1.11 BREAKTHROUGH) "
            "ensuring cross-corpus diversity via purity gate."
        )

    def test_default_top_k_auto_is_12(self):
        """RetrievalConfig() default has top_k_auto=12 (v0.1.21.2 flip)."""
        cfg = RetrievalConfig()
        assert cfg.top_k_auto == 12, (
            "v0.1.21.2 flip: auto-path top_k defaults to 12 (v0.1.12 spec) "
            "providing larger candidate pool before purity gate."
        )

    def test_explicit_none_opt_out_max_chunks_per_norma_restores_v0110(self):
        """RetrievalConfig(max_chunks_per_norma=None) reverts to v0.1.10 behavior."""
        cfg = RetrievalConfig(max_chunks_per_norma=None)
        assert (
            cfg.max_chunks_per_norma is None
        ), "Explicit None opt-out restores v0.1.10 behavior (no cap)."

    def test_explicit_none_opt_out_top_k_auto_restores_v0111(self):
        """RetrievalConfig(top_k_auto=None) uses cfg.top_k for auto queries."""
        cfg = RetrievalConfig(top_k_auto=None)
        assert cfg.top_k_auto is None, (
            "Explicit None opt-out restores v0.1.11 behavior "
            "(auto path uses cfg.top_k=5, same as explicit-corpus path)."
        )

    def test_default_config_summary(self):
        """Default v0.1.21.2 RetrievalConfig has best-evidence values."""
        cfg = RetrievalConfig()
        # v0.1.21.2 flips
        assert cfg.max_chunks_per_norma == 2, "v0.1.11 BREAKTHROUGH cross-corpus cap"
        assert cfg.top_k_auto == 12, "v0.1.12 spec auto-path top_k"
        # unchanged fields
        assert cfg.purity_threshold == 0.6, "unchanged; auto path only"
        assert cfg.top_k == 5, "unchanged; default explicit-corpus top_k"
        assert cfg.pre_rerank == 50, "unchanged; pre-rerank pool size"
        assert cfg.query_normalize is False, "unchanged; default no normalization"
        assert cfg.max_chunks_per_article is None, "unchanged; no per-article cap by default"

    def test_explicit_custom_max_chunks_per_norma(self):
        """Can override per-norma cap with custom value."""
        cfg = RetrievalConfig(max_chunks_per_norma=3)
        assert cfg.max_chunks_per_norma == 3

    def test_explicit_custom_top_k_auto(self):
        """Can override auto-path top_k with custom value."""
        cfg = RetrievalConfig(top_k_auto=20)
        assert cfg.top_k_auto == 20
