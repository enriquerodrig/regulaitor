"""H8 — evaluation harness for RegulAItor.

Pure-Python harness that runs the existing H4 chat graph and H5 document
graph against a curated gold set, computes Ragas + custom metrics with a
Haiku 4.5 LLM judge, and emits a markdown report.

The harness imports backend modules directly; the H7 FastAPI surface is
not involved in evaluation runs.
"""
