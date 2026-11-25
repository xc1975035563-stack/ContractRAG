from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ParentChunk(Base):
    """检索命中子块后，用 parent_id 取回的章节原文。"""

    __tablename__ = "parent_chunks"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    kb_id: Mapped[str] = mapped_column(String(64))
    document_name: Mapped[str] = mapped_column(String(300))
    doc_type: Mapped[str] = mapped_column(String(50))
    section_path: Mapped[list[str]] = mapped_column(ARRAY(Text))
    content: Mapped[str] = mapped_column(Text)


class AuditLog(Base):
    """查询、入库、切换知识库、查看原文的操作记录。"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32))
    kb_id: Mapped[str] = mapped_column(String(64), default="")
    success: Mapped[bool] = mapped_column(Boolean)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
