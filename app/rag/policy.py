"""咨询边界。只查已生效合同，不起草、不给诉讼策略，废止版本不入库。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from app.core.config import APP_ROOT


@dataclass(frozen=True)
class Refusal:
    code: str
    message: str


@dataclass(frozen=True)
class RiskFlag:
    code: str
    level: str
    hint: str


@dataclass(frozen=True)
class ClosedDocument:
    document_name: str
    doc_type: str
    replaced_by: str
    reason: str


@dataclass(frozen=True)
class KnowledgeBasePolicy:
    owner_dept: str
    scene: str


def screen_question(kb_id: str, question: str) -> Refusal | None:
    text = question.strip()
    rules = _rules()
    for item in rules["refusals"]:
        if any(pattern in text for pattern in item["patterns"]):
            return Refusal(item["code"], item["message"])
    for document in closed_documents(kb_id):
        if document.document_name in text:
            return Refusal(
                "superseded",
                f"《{document.document_name}》已废止，{document.reason}。请改查《{document.replaced_by}》。",
            )
    return None


def classify_intent(question: str) -> str:
    text = question.strip()
    for item in _rules()["intents"]:
        if any(pattern in text for pattern in item["patterns"]):
            return item["name"]
    return "其他"


def risk_flags(question: str, cited_texts: list[str]) -> list[RiskFlag]:
    haystack = question + "\n" + "\n".join(cited_texts)
    flags: list[RiskFlag] = []
    for item in _rules()["risk_rules"]:
        if any(pattern in haystack for pattern in item["patterns"]):
            flags.append(RiskFlag(item["code"], item["level"], item["hint"]))
    return flags


def knowledge_base_policy(kb_id: str) -> KnowledgeBasePolicy:
    item = _rules()["knowledge_bases"].get(kb_id) or {}
    return KnowledgeBasePolicy(
        owner_dept=str(item.get("owner_dept") or "未指定部门"),
        scene=str(item.get("scene") or "合同咨询"),
    )


def closed_documents(kb_id: str) -> list[ClosedDocument]:
    return [
        ClosedDocument(
            document_name=item["document_name"],
            doc_type=item["doc_type"],
            replaced_by=item["replaced_by"],
            reason=item["reason"],
        )
        for item in _rules()["closed_documents"]
        if item["kb_id"] == kb_id
    ]


def disclaimer() -> str:
    return str(_rules()["disclaimer"])


@lru_cache(maxsize=1)
def _rules() -> dict:
    path = APP_ROOT / "data" / "business_rules.json"
    return json.loads(path.read_text(encoding="utf-8"))
