# tests/unit/test_harness_case_filter.py
from __future__ import annotations

from pathlib import Path

from evals.harness import load_gold_set


def test_load_gold_set_filters_by_case_ids(tmp_path: Path) -> None:
    gold = tmp_path / "g.jsonl"
    gold.write_text(
        '{"id":"chat-001","tipo":"chat","entrada":"q","corpus_esperado":"ai_act",'
        '"articulos_esperados":["1"],"severidad_esperada":null,'
        '"criterios_evaluacion":["c"],"salida_esperada":null,'
        '"requiere_revision_humana":false,"expected_verdict":"pass"}\n'
        '{"id":"nis2-001","tipo":"chat","entrada":"q","corpus_esperado":"nis2",'
        '"articulos_esperados":["1"],"severidad_esperada":null,'
        '"criterios_evaluacion":["c"],"salida_esperada":null,'
        '"requiere_revision_humana":false,"expected_verdict":"pass"}\n',
        encoding="utf-8",
    )
    chat, _doc = load_gold_set(gold_path=gold, doc_dir=tmp_path / "nope", case_ids={"chat-001"})
    assert [c.id for c in chat] == ["chat-001"]


def test_case_ids_none_returns_all(tmp_path: Path) -> None:
    gold = tmp_path / "g.jsonl"
    gold.write_text(
        '{"id":"chat-001","tipo":"chat","entrada":"q","corpus_esperado":"ai_act",'
        '"articulos_esperados":["1"],"severidad_esperada":null,'
        '"criterios_evaluacion":["c"],"salida_esperada":null,'
        '"requiere_revision_humana":false,"expected_verdict":"pass"}\n'
        '{"id":"nis2-001","tipo":"chat","entrada":"q","corpus_esperado":"nis2",'
        '"articulos_esperados":["1"],"severidad_esperada":null,'
        '"criterios_evaluacion":["c"],"salida_esperada":null,'
        '"requiere_revision_humana":false,"expected_verdict":"pass"}\n',
        encoding="utf-8",
    )
    chat, _doc = load_gold_set(gold_path=gold, doc_dir=tmp_path / "nope", case_ids=None)
    assert [c.id for c in chat] == ["chat-001", "nis2-001"]  # unchanged: all returned


def test_nonexistent_id_in_filter_is_silently_ignored(tmp_path: Path) -> None:
    gold = tmp_path / "g.jsonl"
    gold.write_text(
        '{"id":"chat-001","tipo":"chat","entrada":"q","corpus_esperado":"ai_act",'
        '"articulos_esperados":["1"],"severidad_esperada":null,'
        '"criterios_evaluacion":["c"],"salida_esperada":null,'
        '"requiere_revision_humana":false,"expected_verdict":"pass"}\n',
        encoding="utf-8",
    )
    chat, _doc = load_gold_set(
        gold_path=gold,
        doc_dir=tmp_path / "nope",
        case_ids={"chat-001", "does-not-exist"},
    )
    assert [c.id for c in chat] == ["chat-001"]  # missing id ignored, no raise
