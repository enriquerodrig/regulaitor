"""Contract tests for rag schemas: round-trip through Pydantic JSON."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from regulaitor.rag.schemas import Chunk, ChunkRecord

text_strategy = st.text(
    alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x7E, blacklist_characters="<>&"),
    min_size=1,
    max_size=200,
)


@given(text=text_strategy, articulo=st.integers(min_value=1, max_value=200))
@settings(max_examples=30)
def test_chunk_round_trip(text: str, articulo: int) -> None:
    c = Chunk(
        chunk_id=f"ai_act.{articulo}.es",
        article_id=f"ai_act.{articulo}",
        norma="ai_act",
        articulo=str(articulo),
        apartado=None,
        language="es",
        text=text,
        text_normalized=text.lower(),
        token_count=len(text),
        celex="32024R1689",
        version="2024-07-12",
        source_format="pdf",
        source_url="file:///x",
        hash="sha256:abc",
    )
    restored = Chunk.model_validate_json(c.model_dump_json())
    assert restored == c


@given(text=text_strategy)
@settings(max_examples=20)
def test_chunk_record_round_trip(text: str) -> None:
    cr = ChunkRecord(
        chunk_id="ai_act.1.es",
        article_id="ai_act.1",
        norma="ai_act",
        articulo="1",
        apartado=None,
        language="es",
        text=text,
        text_normalized=text.lower(),
        token_count=len(text),
        celex="32024R1689",
        version="2024-07-12",
        source_format="pdf",
        source_url="file:///x",
        hash="sha256:abc",
        embedding=[0.1] * 1024,
        embedding_model="BAAI/bge-m3@v1.0",
    )
    restored = ChunkRecord.model_validate_json(cr.model_dump_json())
    assert restored == cr


pytestmark = pytest.mark.contract
