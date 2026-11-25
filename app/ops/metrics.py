"""进程内计数。评测通过率由评测脚本写到 data/reports/eval_latest.json。"""

from __future__ import annotations

import json
from threading import Lock

from app.core.config import APP_ROOT

_LOCK = Lock()
_RETRIEVAL_COUNT = 0
_RETRIEVAL_MS = 0.0
_EMPTY_RECALL = 0
_MODEL_FAILURES = 0
_QUERY_OK = 0
_QUERY_FAIL = 0


def observe_retrieval(elapsed_ms: float, *, empty: bool) -> None:
    global _RETRIEVAL_COUNT, _RETRIEVAL_MS, _EMPTY_RECALL
    with _LOCK:
        _RETRIEVAL_COUNT += 1
        _RETRIEVAL_MS += elapsed_ms
        if empty:
            _EMPTY_RECALL += 1


def observe_model_failure() -> None:
    global _MODEL_FAILURES
    with _LOCK:
        _MODEL_FAILURES += 1


def observe_query(success: bool) -> None:
    global _QUERY_OK, _QUERY_FAIL
    with _LOCK:
        if success:
            _QUERY_OK += 1
        else:
            _QUERY_FAIL += 1


def snapshot() -> dict[str, object]:
    with _LOCK:
        average = round(_RETRIEVAL_MS / _RETRIEVAL_COUNT, 1) if _RETRIEVAL_COUNT else None
        live = {
            "retrieval_count": _RETRIEVAL_COUNT,
            "retrieval_ms_avg": average,
            "empty_recall": _EMPTY_RECALL,
            "model_failures": _MODEL_FAILURES,
            "query_ok": _QUERY_OK,
            "query_fail": _QUERY_FAIL,
        }
    path = APP_ROOT / "data" / "reports" / "eval_latest.json"
    evaluation: dict[str, object] | None = None
    if path.is_file():
        evaluation = json.loads(path.read_text(encoding="utf-8"))
    return {"live": live, "evaluation": evaluation}
