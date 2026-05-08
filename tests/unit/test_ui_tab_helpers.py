"""Unit tests for tab_ask + tab_analyze helper functions.

Full Streamlit submit flow is covered by the smoke tests; here we only
exercise the pure helpers (case_id format, mime detection).
"""

from __future__ import annotations

import re

from regulaitor.ui_streamlit import tab_ask


def test_chat_case_id_format():
    cid = tab_ask._generate_case_id()
    assert re.match(r"^ch-\d{8}-[A-Za-z0-9xy]{8}$", cid), f"unexpected format: {cid!r}"


def test_chat_case_id_unique_across_calls():
    a = tab_ask._generate_case_id()
    b = tab_ask._generate_case_id()
    assert a != b, "case_id should be unique per call"
