import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.logging import get_logger
from app.rag.models import Base

logger = get_logger(__name__)

engine = create_async_engine(settings.db.url, pool_pre_ping=True)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def ensure_database() -> None:
    """合同库不存在时，用现有账号创建。建库语句不能放在事务里。"""
    connection = await asyncpg.connect(
        host=settings.db.host,
        port=settings.db.port,
        user=settings.db.user,
        password=settings.db.password,
        database=settings.db.admin_name,
    )
    try:
        exists = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            settings.db.name,
        )
        if not exists:
            await connection.execute(f'CREATE DATABASE "{settings.db.name}"')
            logger.info("已创建数据库", database=settings.db.name)
    finally:
        await connection.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
