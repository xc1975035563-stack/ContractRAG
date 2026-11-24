import re
from dataclasses import dataclass
from uuid import UUID

from langchain_milvus import Milvus

from app.infra.database import AsyncSessionFactory
from app.rag.models import ParentChunk
from app.rag.repository import ParentChunkRepository

_KB_ID = re.compile(r"^[a-z0-9_-]{1,64}$")
CHILD_LIMIT = 8
PARENT_LIMIT = 4


@dataclass(frozen=True)
class Passage:
    number: int
    parent_id: str
    document_name: str
    doc_type: str
    section_path: list[str]
    content: str


class UnknownKnowledgeBaseError(ValueError):
    pass


def query_document(store: Milvus, kb_id: str, question: str) -> list[str]:
    """只在指定文档集里检索子块，返回去重后的 parent_id。"""
    if not _KB_ID.fullmatch(kb_id):
        raise UnknownKnowledgeBaseError(kb_id)
    hits = store.similarity_search(
        question,
        k=CHILD_LIMIT,
        expr=f'kb_id == "{kb_id}"',
    )
    parent_ids: list[str] = []
    for hit in hits:
        parent_id = str(hit.metadata.get("parent_id") or "")
        if parent_id and parent_id not in parent_ids:
            parent_ids.append(parent_id)
        if len(parent_ids) >= PARENT_LIMIT:
            break
    return parent_ids


async def load_passages(kb_id: str, parent_ids: list[str]) -> list[Passage]:
    if not parent_ids:
        return []
    async with AsyncSessionFactory() as session:
        repository = ParentChunkRepository(session)
        rows = await repository.get_many(kb_id, [UUID(item) for item in parent_ids])
    by_id = {str(row.id): row for row in rows}
    passages: list[Passage] = []
    number = 1
    for parent_id in parent_ids:
        row = by_id.get(parent_id)
        if row is None:
            continue
        passages.append(_to_passage(number, row))
        number += 1
    return passages


async def get_passage(kb_id: str, parent_id: str) -> Passage | None:
    if not _KB_ID.fullmatch(kb_id):
        raise UnknownKnowledgeBaseError(kb_id)
    try:
        parsed = UUID(parent_id)
    except ValueError:
        return None
    async with AsyncSessionFactory() as session:
        row = await ParentChunkRepository(session).get(kb_id, parsed)
    if row is None:
        return None
    return _to_passage(1, row)


def _to_passage(number: int, row: ParentChunk) -> Passage:
    return Passage(
        number=number,
        parent_id=str(row.id),
        document_name=row.document_name,
        doc_type=row.doc_type,
        section_path=list(row.section_path or []),
        content=row.content,
    )
