"""按写死的规则核对评测集。不调用对话模型，也不把模型回答当判官。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import APP_ROOT
from app.rag.documents import CorpusDocument
from app.rag.pipeline import RAGPipeline

QUESTIONS = APP_ROOT / "data" / "eval" / "questions.json"
REPORT = APP_ROOT / "data" / "reports" / "eval_latest.json"
CITATION = re.compile(r"\[(\d+)\]")


def main() -> None:
    payload = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    corpus = _corpus()
    failures = 0
    passed = 0
    rows: list[dict[str, str]] = []
    for case in payload["cases"]:
        reason = _check(case, corpus)
        ok = reason == ""
        passed += int(ok)
        failures += int(not ok)
        rows.append({"id": case["id"], "result": "pass" if ok else "fail", "reason": reason or "通过"})
        print(f"{'PASS' if ok else 'FAIL'} {case['id']} {reason or '通过'}")

    sample_ok = 0
    for case in payload["failure_samples"]:
        reason = _check(case, corpus)
        expected = case["expect_reason"]
        ok = reason == expected
        sample_ok += int(ok)
        label = "预期失败" if ok else f"样例未按预期失败（实际：{reason or '通过'}，期望：{expected}）"
        print(f"{'SAMPLE' if ok else 'FAIL'} {case['id']} {label}")
        if not ok:
            failures += 1

    summary = {
        "judge": "rules",
        "passed": passed,
        "failed": len(payload["cases"]) - passed,
        "total": len(payload["cases"]),
        "pass_rate": round(passed / len(payload["cases"]), 4) if payload["cases"] else None,
        "failure_samples_shown": sample_ok,
        "rows": rows,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"规则评测 {passed}/{summary['total']} 通过。"
        f"失败样例 {sample_ok}/{len(payload['failure_samples'])} 条按预期失败。"
        "这不是线上准确率。"
    )
    if failures:
        raise SystemExit(1)


def _corpus() -> dict[str, list]:
    catalog = json.loads((APP_ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
    pipeline = RAGPipeline()
    grouped: dict[str, list] = {}
    for item in catalog:
        markdown = (APP_ROOT / item["path"]).read_text(encoding="utf-8")
        document = CorpusDocument(
            kb_id=item["kb_id"],
            kb_name=item["kb_name"],
            document_name=item["document_name"],
            doc_type=item["doc_type"],
            markdown=markdown,
        )
        parents, _children = pipeline.chunk(document.markdown, document)
        grouped.setdefault(item["kb_id"], []).extend(parents)
    return grouped


def _check(case: dict, corpus: dict[str, list]) -> str:
    kind = case["kind"]
    if kind == "citation":
        return _check_citation(case["answer"], int(case["passage_count"]))
    kb_id = case["kb_id"]
    if kb_id not in corpus:
        return "知识库不存在"
    phrase = " ".join(case.get("content_contains") or [])
    in_kb = _matching(corpus[kb_id], case)
    in_other = any(_contains(parent, phrase) for other, parents in corpus.items() if other != kb_id for parent in parents)
    if kind == "cite":
        if in_kb:
            return ""
        if in_other:
            return "跨库串扰"
        return "错引用"
    if kind == "abstain":
        if in_kb:
            return "该拒答却能在材料中找到"
        return ""
    if kind == "cross":
        if in_kb:
            return "跨库串扰"
        if not in_other and not any(_contains(parent, phrase) for parent in corpus.get(kb_id, [])):
            return "评测短语在全部知识库中都不存在"
        return ""
    return "未知评测类型"


def _matching(parents: list, case: dict) -> bool:
    section = case.get("section_contains") or ""
    needles = case.get("content_contains") or []
    for parent in parents:
        text = _text(parent)
        if section and section not in text:
            continue
        if all(needle in text for needle in needles):
            return True
    return False


def _contains(parent, phrase: str) -> bool:
    return bool(phrase) and phrase in _text(parent)


def _text(parent) -> str:
    return "\n".join(parent.section_path) + "\n" + parent.content


def _check_citation(answer: str, passage_count: int) -> str:
    numbers = [int(item) for item in CITATION.findall(answer)]
    if not numbers:
        return "未引用"
    if any(number < 1 or number > passage_count for number in numbers):
        return "引用编号不在材料中"
    return ""


if __name__ == "__main__":
    main()
