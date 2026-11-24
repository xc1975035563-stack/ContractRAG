import json
from dataclasses import dataclass

from app.core.config import APP_ROOT


@dataclass(frozen=True)
class CatalogDocument:
    document_name: str
    doc_type: str


@dataclass(frozen=True)
class KnowledgeBase:
    kb_id: str
    kb_name: str
    documents: tuple[CatalogDocument, ...]
    prompts: tuple[str, ...]


def list_knowledge_bases() -> list[KnowledgeBase]:
    catalog = json.loads((APP_ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
    grouped: dict[str, dict] = {}
    for item in catalog:
        bucket = grouped.setdefault(
            item["kb_id"],
            {"kb_name": item["kb_name"], "documents": [], "prompts": []},
        )
        bucket["documents"].append(
            CatalogDocument(item["document_name"], item["doc_type"])
        )
        for prompt in item.get("prompts") or []:
            if prompt not in bucket["prompts"]:
                bucket["prompts"].append(prompt)
    return [
        KnowledgeBase(
            kb_id,
            bucket["kb_name"],
            tuple(bucket["documents"]),
            tuple(bucket["prompts"]),
        )
        for kb_id, bucket in grouped.items()
    ]


def find_knowledge_base(kb_id: str) -> KnowledgeBase | None:
    for base in list_knowledge_bases():
        if base.kb_id == kb_id:
            return base
    return None
