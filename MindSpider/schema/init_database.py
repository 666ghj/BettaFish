"""
MindSpider 数据库初始化（SQLAlchemy 2.x 异步引擎）

此脚本创建 MindSpider 扩展表（与 MediaCrawler 原始表分离）。
支持 MySQL 与 PostgreSQL，需已有可连接的数据库实例。

数据模型定义位置：
- MindSpider/schema/models_sa.py
"""

from __future__ import annotations

import asyncio
import os
from typing import Optional

from loguru import logger

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from models_sa import Base

# 导入 models_bigdata 以确保所有表类被注册到 Base.metadata
# models_bigdata 现在也使用 models_sa 的 Base，所以所有表都在同一个 metadata 中
import models_bigdata  # noqa: F401  # 导入以注册所有表类
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config import settings

def _env(key: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(key)
    return v if v not in (None, "") else default


def _build_database_url() -> str:
    # 优先 DATABASE_URL
    database_url = settings.DATABASE_URL if hasattr(settings, "DATABASE_URL") else None
    if database_url:
        return database_url

    dialect = (settings.DB_DIALECT or "mysql").lower()
    host = settings.DB_HOST or "localhost"
    port = str(settings.DB_PORT or ("3306" if dialect == "mysql" else "5432"))
    user = settings.DB_USER or "root"
    password = settings.DB_PASSWORD or ""
    db_name = settings.DB_NAME or "mindspider"

    if dialect in ("postgresql", "postgres"):
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"

    return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{db_name}"


async def _create_views_if_needed(engine_dialect: str):
    # 视图为可选；仅当业务需要时创建。两端使用通用 SQL 聚合避免方言函数。
    # 如不需要视图，可跳过。
    engine_dialect = engine_dialect.lower()
    v_topic_crawling_stats = (
        "CREATE OR REPLACE VIEW v_topic_crawling_stats AS\n"
        "SELECT dt.topic_id, dt.topic_name, dt.extract_date, dt.processing_status,\n"
        "       COUNT(DISTINCT ct.task_id) AS total_tasks,\n"
        "       SUM(CASE WHEN ct.task_status = 'completed' THEN 1 ELSE 0 END) AS completed_tasks,\n"
        "       SUM(CASE WHEN ct.task_status = 'failed' THEN 1 ELSE 0 END) AS failed_tasks,\n"
        "       SUM(COALESCE(ct.total_crawled,0)) AS total_content_crawled,\n"
        "       SUM(COALESCE(ct.success_count,0)) AS total_success_count,\n"
        "       SUM(COALESCE(ct.error_count,0)) AS total_error_count\n"
        "FROM daily_topics dt\n"
        "LEFT JOIN crawling_tasks ct ON dt.topic_id = ct.topic_id\n"
        "GROUP BY dt.topic_id, dt.topic_name, dt.extract_date, dt.processing_status"
    )

    v_daily_summary = (
        "CREATE OR REPLACE VIEW v_daily_summary AS\n"
        "SELECT dn.crawl_date AS crawl_date,\n"
        "       COUNT(DISTINCT dn.news_id) AS total_news,\n"
        "       COUNT(DISTINCT dn.source_platform) AS platforms_covered,\n"
        "       (SELECT COUNT(*) FROM daily_topics WHERE extract_date = dn.crawl_date) AS topics_extracted,\n"
        "       (SELECT COUNT(*) FROM crawling_tasks WHERE scheduled_date = dn.crawl_date) AS tasks_created\n"
        "FROM daily_news dn\n"
        "GROUP BY dn.crawl_date\n"
        "ORDER BY dn.crawl_date DESC"
    )

    # PostgreSQL 的 CREATE OR REPLACE VIEW 也可用；两端均执行
    from sqlalchemy.ext.asyncio import AsyncEngine
    engine: AsyncEngine = create_async_engine(_build_database_url())
    async with engine.begin() as conn:
        await conn.execute(text(v_topic_crawling_stats))
        await conn.execute(text(v_daily_summary))
    await engine.dispose()


async def main() -> None:
    database_url = _build_database_url()
    engine = create_async_engine(database_url, pool_pre_ping=True, pool_recycle=1800)

    # 由于 models_bigdata 和 models_sa 现在共享同一个 Base，所有表都在同一个 metadata 中
    # 只需创建一次，SQLAlchemy 会自动处理表之间的依赖关系
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 保持原有视图创建和释放逻辑
    dialect_name = engine.url.get_backend_name()
    await _create_views_if_needed(dialect_name)

    await engine.dispose()
    logger.info("[init_database_sa] 数据表与视图创建完成")


if __name__ == "__main__":
    asyncio.run(main())


