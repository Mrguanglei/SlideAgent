"""
PPTAgent 数据库连接和会话管理

提供异步数据库连接池和会话管理功能
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.pool import NullPool

from .models import Base
from .migrations import run_migrations

logger = logging.getLogger(__name__)

# 数据库连接 URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://pptagent:pptagent_secret_2024@localhost:5432/pptagent_dev"
)

# 创建异步引擎
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,  # 生产环境设为 False
    pool_pre_ping=True,  # 连接前检查
    pool_size=10,
    max_overflow=20,
)

# 创建异步会话工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db():
    """初始化数据库 - 创建所有表并运行迁移"""
    logger.info("Initializing database...")
    try:
        # 创建所有表
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✓ Database tables created successfully")
        
        # 运行迁移（添加缺失的列）
        await run_migrations(engine)
        
    except Exception as e:
        logger.error(f"✗ Failed to initialize database: {e}")
        raise


async def close_db():
    """关闭数据库连接"""
    logger.info("Closing database connection...")
    await engine.dispose()
    logger.info("✓ Database connection closed")


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（上下文管理器）"""
    session = async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入用的数据库会话生成器"""
    async with get_db_session() as session:
        yield session
