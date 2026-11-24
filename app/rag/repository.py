from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.models import ParentChunk


class ParentChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, kb_id: str, parent_id: UUID) -> ParentChunk | None:
        result = await self._session.execute(
            select(ParentChunk).where(
                ParentChunk.kb_id == kb_id,
                ParentChunk.id == parent_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_many(self, kb_id: str, parent_ids: list[UUID]) -> list[ParentChunk]:
        if not parent_ids:
            return []
        result = await self._session.execute(
            select(ParentChunk).where(
                ParentChunk.kb_id == kb_id,
                ParentChunk.id.in_(parent_ids),
            )
        )
        return list(result.scalars().all())

    async def delete_by_kb(self, kb_id: str) -> None:
        await self._session.execute(delete(ParentChunk).where(ParentChunk.kb_id == kb_id))

    async def delete_by_document(self, kb_id: str, document_name: str) -> None:
        await self._session.execute(
            delete(ParentChunk).where(
                ParentChunk.kb_id == kb_id,
                ParentChunk.document_name == document_name,
            )
        )

    def add_all(self, chunks: list[ParentChunk]) -> None:
        self._session.add_all(chunks)
