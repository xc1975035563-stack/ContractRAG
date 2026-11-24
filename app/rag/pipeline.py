from uuid import uuid4

from langchain_core.documents import Document
from langchain_milvus import Milvus
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from app.core.logging import get_logger
from app.infra.database import AsyncSessionFactory
from app.rag.documents import CorpusDocument
from app.rag.models import ParentChunk
from app.rag.repository import ParentChunkRepository

logger = get_logger(__name__)


class RAGPipeline:
    def __init__(self, vector_store: Milvus | None = None) -> None:
        self._vector_store = vector_store
        self._markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "h1"),
                ("##", "h2"),
                ("###", "h3"),
                ("####", "h4"),
            ],
            strip_headers=True,
        )
        self._child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "；", ";", "，", ","],
            keep_separator="end",
        )

    def chunk(self, markdown: str, document: CorpusDocument) -> tuple[list[ParentChunk], list[Document]]:
        sections = self._markdown_splitter.split_text(markdown)
        parent_chunks: list[ParentChunk] = []
        child_chunks: list[Document] = []

        for section in sections:
            content = section.page_content.strip()
            section_path = [str(value) for value in section.metadata.values() if value]
            if not content or not section_path:
                continue
            parent = ParentChunk(
                id=uuid4(),
                kb_id=document.kb_id,
                document_name=document.document_name,
                doc_type=document.doc_type,
                section_path=section_path,
                content=content,
            )
            parent_chunks.append(parent)

            header = "\n".join(section_path)
            prefixed = Document(
                page_content=(header + "\n" + content) if header else content,
                metadata={
                    "kb_id": document.kb_id,
                    "document_name": document.document_name,
                    "doc_type": document.doc_type,
                    "parent_id": str(parent.id),
                },
            )
            child_chunks.extend(self._child_splitter.split_documents([prefixed]))

        return parent_chunks, child_chunks

    async def ingest(self, document: CorpusDocument) -> tuple[int, int]:
        parent_chunks, child_chunks = self.chunk(document.markdown, document)
        self._save_child_chunks(document, child_chunks)
        await self._save_parent_chunks(document, parent_chunks)
        logger.info(
            "入库完成",
            kb_id=document.kb_id,
            document_name=document.document_name,
            parents=len(parent_chunks),
            children=len(child_chunks),
        )
        return len(parent_chunks), len(child_chunks)

    def _save_child_chunks(self, document: CorpusDocument, child_chunks: list[Document]) -> None:
        expr = (
            f'kb_id == "{document.kb_id}" '
            f'and document_name == "{document.document_name}"'
        )
        if self._vector_store.client.has_collection(self._vector_store.collection_name):
            self._vector_store.delete(expr=expr)
        if child_chunks:
            self._vector_store.add_documents(child_chunks)

    async def _save_parent_chunks(
        self,
        document: CorpusDocument,
        parent_chunks: list[ParentChunk],
    ) -> None:
        async with AsyncSessionFactory() as session:
            async with session.begin():
                repository = ParentChunkRepository(session)
                await repository.delete_by_document(document.kb_id, document.document_name)
                repository.add_all(parent_chunks)
