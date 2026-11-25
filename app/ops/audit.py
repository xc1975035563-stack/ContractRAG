from sqlalchemy import select

from app.core.logging import get_logger
from app.infra.database import AsyncSessionFactory
from app.rag.models import AuditLog

logger = get_logger(__name__)


async def record_audit(
    username: str,
    action: str,
    kb_id: str,
    success: bool,
    detail: str,
) -> None:
    logger.info(
        "审计",
        username=username,
        action=action,
        kb_id=kb_id,
        success=success,
        detail=detail,
    )
    try:
        async with AsyncSessionFactory() as session:
            async with session.begin():
                session.add(
                    AuditLog(
                        username=username,
                        action=action,
                        kb_id=kb_id,
                        success=success,
                        detail=detail[:500],
                    )
                )
    except Exception:
        logger.exception("审计写入失败", username=username, action=action, kb_id=kb_id)


async def list_audit(limit: int = 50) -> list[AuditLog]:
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
        )
        return list(result.scalars().all())
