"""把目录中的合同写入 Milvus 与 PostgreSQL，并移除已换出的文档集。"""

from __future__ import annotations

import asyncio
import json
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.prepare_documents import main as prepare_documents

from app.core.config import APP_ROOT, settings
from app.core.logging import configure_logging, get_logger
from sqlalchemy import select

from app.infra.database import AsyncSessionFactory, ensure_database
from app.rag.documents import CorpusDocument
from app.rag.models import ParentChunk
from app.rag.pipeline import RAGPipeline
from app.rag.repository import ParentChunkRepository
from app.rag.vector_store import build_vector_store

logger = get_logger(__name__)


def load_corpus() -> list[CorpusDocument]:
    catalog = json.loads((APP_ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
    documents: list[CorpusDocument] = []
    for item in catalog:
        markdown = (APP_ROOT / item["path"]).read_text(encoding="utf-8")
        documents.append(
            CorpusDocument(
                kb_id=item["kb_id"],
                kb_name=item["kb_name"],
                document_name=item["document_name"],
                doc_type=item["doc_type"],
                markdown=markdown,
            )
        )
    return documents


def service_reachable(host: str, port: int) -> bool:
    probe = socket.socket()
    probe.settimeout(3)
    try:
        probe.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        probe.close()


async def main() -> None:
    configure_logging(settings.logging_level)
    prepare_documents()
    documents = load_corpus()

    preview = RAGPipeline()
    for document in documents:
        parents, children = preview.chunk(document.markdown, document)
        logger.info(
            "切块预览",
            kb=document.kb_name,
            document=document.document_name,
            parents=len(parents),
            children=len(children),
        )

    milvus_up = service_reachable(settings.milvus.host, settings.milvus.port)
    postgres_up = service_reachable(settings.db.host, settings.db.port)
    if not milvus_up or not postgres_up:
        raise SystemExit(
            "Milvus "
            f"{settings.milvus.host}:{settings.milvus.port} {'可连接' if milvus_up else '连不上'}，"
            "PostgreSQL "
            f"{settings.db.host}:{settings.db.port} {'可连接' if postgres_up else '连不上'}。"
            "三份合同已整理好，服务恢复后重新运行 scripts/ingest.py 即可入库。"
        )

    logger.info("连接 Milvus", uri=settings.milvus.uri)
    await ensure_database()
    store = build_vector_store()
    await drop_retired_knowledge_bases(store, {item.kb_id for item in documents})
    pipeline = RAGPipeline(store)
    for document in documents:
        await pipeline.ingest(document)

    question = "家居日用类目的技术服务费按成交额收多少"
    qinghe = store.similarity_search(question, k=3, expr='kb_id == "qinghe"')
    nanhu = store.similarity_search(question, k=3, expr='kb_id == "nanhu"')
    logger.info("青禾市集检索", hits=[item.metadata.get("document_name") for item in qinghe])
    logger.info("南湖优选检索", hits=[item.metadata.get("document_name") for item in nanhu])


async def drop_retired_knowledge_bases(store, keep: set[str]) -> None:
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(ParentChunk.kb_id).distinct())
        found = {row[0] for row in result}
    for kb_id in sorted(found - keep):
        logger.info("移除已换出的文档集", kb_id=kb_id)
        if store.client.has_collection(store.collection_name):
            store.delete(expr=f'kb_id == "{kb_id}"')
        async with AsyncSessionFactory() as session:
            async with session.begin():
                await ParentChunkRepository(session).delete_by_kb(kb_id)


if __name__ == "__main__":
    asyncio.run(main())
