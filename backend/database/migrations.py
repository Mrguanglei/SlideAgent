"""
数据库迁移脚本

用于更新已存在的数据库表结构，添加新列等。
"""

import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


async def check_and_add_column(engine: AsyncEngine, table: str, column: str, column_def: str):
    """
    检查列是否存在，如果不存在则添加
    
    Args:
        engine: 数据库引擎
        table: 表名
        column: 列名
        column_def: 列定义（如 "VARCHAR(100) DEFAULT 'default_user'"）
    """
    async with engine.begin() as conn:
        # 检查列是否存在
        result = await conn.execute(text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table}' AND column_name = '{column}'
        """))
        exists = result.fetchone() is not None
        
        if not exists:
            logger.info(f"Adding column {column} to table {table}...")
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {column_def}"))
            logger.info(f"✓ Column {column} added to table {table}")
        else:
            logger.debug(f"Column {column} already exists in table {table}")


async def check_table_exists(engine: AsyncEngine, table: str) -> bool:
    """检查表是否存在"""
    async with engine.begin() as conn:
        result = await conn.execute(text(f"""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name = '{table}'
        """))
        return result.fetchone() is not None


async def check_column_exists(engine: AsyncEngine, table: str, column: str) -> bool:
    """检查列是否存在"""
    async with engine.begin() as conn:
        result = await conn.execute(text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table}' AND column_name = '{column}'
        """))
        return result.fetchone() is not None


async def drop_column_if_exists(engine: AsyncEngine, table: str, column: str):
    """
    如果列存在则删除
    
    Args:
        engine: 数据库引擎
        table: 表名
        column: 列名
    """
    if await check_column_exists(engine, table, column):
        async with engine.begin() as conn:
            logger.info(f"Dropping column {column} from table {table}...")
            await conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {column}"))
            logger.info(f"✓ Column {column} dropped from table {table}")


async def drop_not_null_constraint(engine: AsyncEngine, table: str, column: str):
    """
    删除列的 NOT NULL 约束
    
    Args:
        engine: 数据库引擎
        table: 表名
        column: 列名
    """
    if await check_column_exists(engine, table, column):
        async with engine.begin() as conn:
            logger.info(f"Dropping NOT NULL constraint on {table}.{column}...")
            await conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN {column} DROP NOT NULL"))
            logger.info(f"✓ NOT NULL constraint dropped on {table}.{column}")


async def run_migrations(engine: AsyncEngine):
    """
    运行所有数据库迁移

    在应用启动时调用，确保数据库结构是最新的。
    """
    logger.info("Running database migrations...")

    try:
        # ==================== conversations 表 ====================
        if await check_table_exists(engine, "conversations"):
            # 添加 uuid 列
            if not await check_column_exists(engine, "conversations", "uuid"):
                logger.info("Adding uuid column to conversations table...")
                async with engine.begin() as conn:
                    # 添加 uuid 列（允许 NULL）
                    await conn.execute(text("ALTER TABLE conversations ADD COLUMN uuid VARCHAR(36)"))

                    # 为现有记录生成 UUID
                    import uuid
                    result = await conn.execute(text("SELECT id FROM conversations"))
                    rows = result.fetchall()
                    for row in rows:
                        new_uuid = str(uuid.uuid4())
                        await conn.execute(
                            text("UPDATE conversations SET uuid = :uuid WHERE id = :id"),
                            {"uuid": new_uuid, "id": row[0]}
                        )

                    # 设置 NOT NULL 约束
                    await conn.execute(text("ALTER TABLE conversations ALTER COLUMN uuid SET NOT NULL"))

                    # 添加唯一约束
                    await conn.execute(text("ALTER TABLE conversations ADD CONSTRAINT conversations_uuid_key UNIQUE (uuid)"))

                    # 创建索引
                    await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_conversation_uuid ON conversations (uuid)"))

                logger.info("✓ UUID column added to conversations table")

        # ==================== 清理旧列 ====================
        # 删除旧的 knowledge_base_id 列（如果存在）
        if await check_table_exists(engine, "knowledge_documents"):
            await drop_column_if_exists(engine, "knowledge_documents", "knowledge_base_id")
        
        # ==================== knowledge_documents 表 ====================
        if await check_table_exists(engine, "knowledge_documents"):
            # 用户 ID
            await check_and_add_column(
                engine, 
                "knowledge_documents", 
                "user_id", 
                "VARCHAR(100) DEFAULT 'default_user'"
            )
            
            # 文件夹 ID
            await check_and_add_column(
                engine,
                "knowledge_documents",
                "folder_id",
                "BIGINT"
            )
            
            # 显示名称
            await check_and_add_column(
                engine,
                "knowledge_documents",
                "display_name",
                "VARCHAR(255)"
            )
            
            # 文件大小
            await check_and_add_column(
                engine,
                "knowledge_documents",
                "file_size",
                "BIGINT"
            )
            
            # 文件路径
            await check_and_add_column(
                engine,
                "knowledge_documents",
                "file_path",
                "VARCHAR(500)"
            )
            
            # 来源 URL
            await check_and_add_column(
                engine,
                "knowledge_documents",
                "source_url",
                "TEXT"
            )
            
            # 解析状态
            await check_and_add_column(
                engine,
                "knowledge_documents",
                "parse_status",
                "VARCHAR(20) DEFAULT 'pending'"
            )
            
            # 解析错误
            await check_and_add_column(
                engine,
                "knowledge_documents",
                "parse_error",
                "TEXT"
            )
            
            # 解析完成时间
            await check_and_add_column(
                engine,
                "knowledge_documents",
                "parsed_at",
                "TIMESTAMP"
            )
            
            # 原始内容
            await check_and_add_column(
                engine,
                "knowledge_documents",
                "raw_content",
                "TEXT"
            )
            
            # 分块数量
            await check_and_add_column(
                engine,
                "knowledge_documents",
                "chunk_count",
                "INTEGER DEFAULT 0"
            )
            
            # 元数据 JSON
            await check_and_add_column(
                engine,
                "knowledge_documents",
                "metadata_json",
                "JSONB"
            )
            
            # 更新时间
            await check_and_add_column(
                engine,
                "knowledge_documents",
                "updated_at",
                "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            )
        
        # ==================== knowledge_folders 表 ====================
        if await check_table_exists(engine, "knowledge_folders"):
            # 用户 ID
            await check_and_add_column(
                engine,
                "knowledge_folders",
                "user_id",
                "VARCHAR(100) DEFAULT 'default_user'"
            )
            
            # 父文件夹 ID
            await check_and_add_column(
                engine,
                "knowledge_folders",
                "parent_id",
                "BIGINT"
            )
            
            # 更新时间
            await check_and_add_column(
                engine,
                "knowledge_folders",
                "updated_at",
                "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            )
        
        # ==================== knowledge_chunks 表 ====================
        if await check_table_exists(engine, "knowledge_chunks"):
            # 分块索引
            await check_and_add_column(
                engine,
                "knowledge_chunks",
                "chunk_index",
                "INTEGER DEFAULT 0"
            )
            
            # Token 数量
            await check_and_add_column(
                engine,
                "knowledge_chunks",
                "token_count",
                "INTEGER"
            )
            
            # 向量嵌入
            await check_and_add_column(
                engine,
                "knowledge_chunks",
                "embedding_vector",
                "JSONB"
            )
        
        logger.info("✓ Database migrations completed")
        
    except Exception as e:
        logger.error(f"✗ Database migration failed: {e}")
        # 迁移失败不应该阻止应用启动，只记录错误
        # 因为表可能还不存在（首次启动）


async def drop_knowledge_tables(engine: AsyncEngine):
    """
    删除知识库相关的所有表（用于重置）
    
    警告：这会删除所有知识库数据！
    """
    logger.warning("Dropping all knowledge tables...")
    
    async with engine.begin() as conn:
        # 按依赖顺序删除
        await conn.execute(text("DROP TABLE IF EXISTS knowledge_chunks CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS knowledge_documents CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS knowledge_folders CASCADE"))
    
    logger.info("✓ Knowledge tables dropped")
