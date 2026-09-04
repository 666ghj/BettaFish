# -*- coding: utf-8 -*-
"""
Alembic 迁移环境配置。
"""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# 加载 Alembic 配置
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 导入所有模型以便 autogenerate 检测
from app.database import Base
from app.models import *  # noqa

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式运行迁移（只生成 SQL 脚本）"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式运行迁移"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()