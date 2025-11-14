"""
启动健康检查模块

在 Docker 或本地启动主应用之前，对核心依赖进行一次性可用性检测。
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests
from loguru import logger

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - OpenAI 在部分测试环境可能未安装
    OpenAI = None  # type: ignore


@dataclass
class CheckResult:
    """单项检查结果"""

    success: bool
    message: str
    critical: bool
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        return result


class HealthChecker:
    """BettaFish 关键依赖健康检查器"""

    def __init__(self, config: Any):
        self.config = config
        self.results: Dict[str, Dict[str, Any]] = {}

    def check_all(self) -> Tuple[bool, Dict[str, Dict[str, Any]]]:
        """执行所有健康检查"""

        logger.info("=" * 70)
        logger.info("🔍 正在执行启动健康检查 ...")
        logger.info("=" * 70)

        checks: List[Tuple[str, Callable[[], CheckResult]]] = [
            ("数据库连接", self._check_database),
            ("InsightEngine LLM", lambda: self._check_llm(
                "InsightEngine",
                self.config.INSIGHT_ENGINE_API_KEY,
                self.config.INSIGHT_ENGINE_BASE_URL,
                self.config.INSIGHT_ENGINE_MODEL_NAME,
            )),
            ("MediaEngine LLM", lambda: self._check_llm(
                "MediaEngine",
                self.config.MEDIA_ENGINE_API_KEY,
                self.config.MEDIA_ENGINE_BASE_URL,
                self.config.MEDIA_ENGINE_MODEL_NAME,
            )),
            ("QueryEngine LLM", lambda: self._check_llm(
                "QueryEngine",
                self.config.QUERY_ENGINE_API_KEY,
                self.config.QUERY_ENGINE_BASE_URL,
                self.config.QUERY_ENGINE_MODEL_NAME,
            )),
            ("ReportEngine LLM", lambda: self._check_llm(
                "ReportEngine",
                self.config.REPORT_ENGINE_API_KEY,
                self.config.REPORT_ENGINE_BASE_URL,
                self.config.REPORT_ENGINE_MODEL_NAME,
            )),
            ("ForumHost LLM", lambda: self._check_llm(
                "ForumHost",
                self.config.FORUM_HOST_API_KEY,
                self.config.FORUM_HOST_BASE_URL,
                self.config.FORUM_HOST_MODEL_NAME,
                critical=False,  # Forum 可选
            )),
            ("Tavily 搜索 API", self._check_tavily),
            ("Bocha 搜索 API", self._check_bocha),
        ]

        all_passed = True

        for name, check_func in checks:
            try:
                result = check_func()
            except Exception as exc:  # pragma: no cover - 兜底防御
                logger.exception(f"{name} 检查异常: {exc}")
                result = CheckResult(False, f"检查异常: {exc}", critical=True)

            self.results[name] = result.to_dict()
            status_icon = "✅" if result.success else ("🔴" if result.critical else "⚠️")

            logger.info(f"{status_icon} {name}: {result.message}")
            if not result.success and result.critical:
                all_passed = False

        if all_passed:
            logger.info("=" * 70)
            logger.info("✅ 所有关键依赖就绪，系统即将启动")
            logger.info("=" * 70)
        else:
            logger.error("=" * 70)
            logger.error("🔴 存在关键依赖不可用，系统启动被阻止")
            logger.error("=" * 70)

        return all_passed, self.results

    # --------------------------------------------------------------------- #
    # 各类检查实现
    # --------------------------------------------------------------------- #

    def _check_database(self) -> CheckResult:
        """检查数据库连接状态（影响 InsightEngine，非强制）"""

        dialect = (self.config.DB_DIALECT or "").lower()
        host = (self.config.DB_HOST or "").strip()

        if not host or host == "your_db_host":
            return CheckResult(
                success=False,
                message="未配置数据库，将禁用 InsightEngine。",
                critical=False,
            )

        try:
            if dialect in {"mysql", "mariadb"}:
                import pymysql

                connection = pymysql.connect(
                    host=self.config.DB_HOST,
                    port=int(self.config.DB_PORT),
                    user=self.config.DB_USER,
                    password=self.config.DB_PASSWORD,
                    database=self.config.DB_NAME,
                    connect_timeout=3,
                    charset=getattr(self.config, "DB_CHARSET", "utf8mb4"),
                )
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT 1")
                finally:
                    connection.close()

                return CheckResult(True, "MySQL/MariaDB 连接成功", critical=False)

            if dialect in {"postgresql", "postgres"}:
                import asyncpg
                import contextlib

                async def _check_postgres() -> None:
                    conn = await asyncpg.connect(
                        host=self.config.DB_HOST,
                        port=int(self.config.DB_PORT),
                        user=self.config.DB_USER,
                        password=self.config.DB_PASSWORD,
                        database=self.config.DB_NAME,
                        timeout=3,
                    )
                    try:
                        await conn.execute("SELECT 1")
                    finally:
                        await conn.close()

                try:
                    asyncio.run(_check_postgres())
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(_check_postgres())
                    finally:
                        with contextlib.suppress(Exception):
                            loop.close()
                return CheckResult(True, "PostgreSQL 连接成功", critical=False)

            if dialect in {"sqlite", "sqlite3"}:
                from pathlib import Path

                db_path = Path(self.config.DB_NAME)
                if db_path.exists():
                    return CheckResult(True, f"SQLite 数据库存在: {db_path}", critical=False)

                return CheckResult(
                    False,
                    f"SQLite 数据库文件不存在: {db_path}",
                    critical=False,
                )

            return CheckResult(
                False,
                f"未知数据库类型: {self.config.DB_DIALECT}",
                critical=False,
            )

        except ModuleNotFoundError as exc:
            return CheckResult(
                False,
                f"缺少数据库驱动: {exc}",
                critical=True,
            )
        except Exception as exc:
            return CheckResult(
                False,
                f"连接失败: {exc}",
                critical=True,
            )

    def _check_llm(
        self,
        name: str,
        api_key: Optional[str],
        base_url: Optional[str],
        model_name: Optional[str],
        *,
        critical: bool = True,
    ) -> CheckResult:
        """检查 OpenAI 兼容 LLM 接口"""

        if not api_key:
            return CheckResult(
                False,
                "API Key 未配置",
                critical=critical,
            )

        if OpenAI is None:
            return CheckResult(
                False,
                "openai 库未安装",
                critical=True,
            )

        try:
            client = OpenAI(api_key=api_key, base_url=base_url, timeout=10.0)
            if model_name:
                client.models.retrieve(model_name)
            else:
                client.models.list(limit=1)  # type: ignore[arg-type]

            message = f"{name} 模型可用: {model_name or '默认模型'}"
            return CheckResult(True, message, critical)

        except Exception as exc:
            return CheckResult(
                False,
                f"{name} API 不可用: {exc}",
                critical=critical,
            )

    def _check_tavily(self) -> CheckResult:
        """检查 Tavily 搜索 API（非关键）"""

        api_key = (self.config.TAVILY_API_KEY or "").strip()

        if not api_key:
            return CheckResult(
                False,
                "未配置 API Key（QueryEngine 搜索受限）",
                critical=False,
            )

        headers = {"Content-Type": "application/json", "X-API-Key": api_key}
        url = "https://api.tavily.com/tavily/api/v1/search"
        payload = {"query": "healthcheck", "search_depth": "basic", "max_results": 1}

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=8)
            if response.status_code == 200:
                return CheckResult(True, "API 可用", critical=False)

            return CheckResult(
                False,
                f"返回状态码 {response.status_code}",
                critical=False,
            )
        except requests.RequestException as exc:
            return CheckResult(
                False,
                f"请求失败: {exc}",
                critical=False,
            )

    def _check_bocha(self) -> CheckResult:
        """检查 Bocha 搜索 API（非关键）"""

        api_key = (self.config.BOCHA_WEB_SEARCH_API_KEY or "").strip()

        if not api_key:
            return CheckResult(
                False,
                "未配置 API Key（MediaEngine 搜索受限）",
                critical=False,
            )

        url = (self.config.BOCHA_BASE_URL or "").rstrip("/")
        if not url:
            return CheckResult(
                False,
                "未配置 Base URL",
                critical=False,
            )

        try:
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=8,
            )
            if 200 <= response.status_code < 400:
                return CheckResult(True, "API 可用", critical=False)

            return CheckResult(
                False,
                f"返回状态码 {response.status_code}",
                critical=False,
            )
        except requests.RequestException as exc:
            return CheckResult(
                False,
                f"请求失败: {exc}",
                critical=False,
            )


def run_health_check(force: bool = False) -> Tuple[bool, Dict[str, Dict[str, Any]]]:
    """
    执行健康检查。

    Returns:
        (是否通过, 详细结果字典)
    """

    if not force:
        skip_flag = os.getenv("BETTAFISH_SKIP_HEALTH_CHECK", "")
        if skip_flag.lower() in {"1", "true", "yes"}:
            logger.warning("⚠️ 检测到 BETTAFISH_SKIP_HEALTH_CHECK，跳过启动健康检查")
            return True, {}

    try:
        from config import settings
    except Exception as exc:  # pragma: no cover - 极端情况下加载配置失败
        logger.error(f"加载配置失败: {exc}")
        if force:
            sys.exit(1)
        return False, {}

    checker = HealthChecker(settings)
    success, results = checker.check_all()

    if force:
        sys.exit(0 if success else 1)

    return success, results


__all__ = ["HealthChecker", "CheckResult", "run_health_check"]

