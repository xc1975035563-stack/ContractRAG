"""整理电商目录和地产源合同，写出可入库的 Markdown 与处理报告。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.rag.source_prep import SourceSpec, prepare_sources

CATALOG_PATH = ROOT / "data" / "catalog.json"
SOURCE_DIR = ROOT / "data" / "sources"
ESTATE_DIR = ROOT / "data" / "documents" / "estate"
REPORT_PATH = ROOT / "data" / "reports" / "estate_prepare.json"
ESTATE_ID = "estate"
ESTATE_NAME = "示范小区"

ESTATE_SPECS = [
    SourceSpec("sales.txt", "商品房买卖合同", "买卖合同"),
    SourceSpec("lease.txt", "城镇房屋租赁合同", "租赁合同"),
    SourceSpec("property.txt", "山东省物业服务合同", "物业合同"),
    SourceSpec("fixtures/empty_chapter.txt", "空章节样例", "样例", required=False),
    SourceSpec("fixtures/not_a_contract.txt", "无法解析样例", "样例", required=False),
]

ESTATE_PROMPTS = {
    "城镇房屋租赁合同": ["租金逾期可以怎么处理", "押金什么时候退", "物业费由谁承担"],
    "商品房买卖合同": ["办不出房产证怎么处理", "保修期内谁维修"],
    "山东省物业服务合同": ["物业费包含哪些", "欠物业费会怎么处理"],
}


def main() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    for item in catalog:
        if item["kb_id"] == ESTATE_ID:
            continue
        target = ROOT / item["path"]
        if not target.is_file():
            raise SystemExit(f"缺少合同文件：{item['path']}")
        print(f"{item['kb_name']} / {item['document_name']} -> {item['path']}")

    report = prepare_sources(SOURCE_DIR, ESTATE_SPECS)
    ESTATE_DIR.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for document in report.documents:
        if document.doc_type == "样例":
            continue
        target = ESTATE_DIR / document.output_name
        target.write_text(document.markdown, encoding="utf-8")
        written.append(document.document_name)
        print(f"{ESTATE_NAME} / {document.document_name} -> {target.relative_to(ROOT)}")

    kept = [item for item in catalog if item["kb_id"] != ESTATE_ID]
    for document in report.documents:
        if document.doc_type == "样例":
            continue
        entry = {
            "kb_id": ESTATE_ID,
            "kb_name": ESTATE_NAME,
            "document_name": document.document_name,
            "doc_type": document.doc_type,
            "path": f"data/documents/estate/{document.output_name}",
        }
        prompts = ESTATE_PROMPTS.get(document.document_name)
        if prompts:
            entry["prompts"] = prompts
        kept.append(entry)
    CATALOG_PATH.write_text(json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    payload = {
        "written": written,
        "notes": [note.__dict__ for note in report.notes],
        "failures": [note.__dict__ for note in report.failures],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for note in report.notes:
        print(f"[{note.level}] {note.source}: {note.reason}")
    for note in report.failures:
        print(f"[fail] {note.source}: {note.reason}")
    required_failures = [note for note in report.failures if not note.reason.startswith("非必需")]
    if required_failures:
        reasons = "；".join(note.reason for note in required_failures)
        raise SystemExit(f"地产合同整理失败：{reasons}")
    if len(written) != 3:
        raise SystemExit(f"地产合同应写入 3 份，实际 {len(written)} 份")


if __name__ == "__main__":
    main()
