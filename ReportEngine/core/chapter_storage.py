"""
章节JSON的落盘与清单管理。

每一章在流式生成时会立即写入raw文件，完成校验后再写入
格式化的chapter.json，并在manifest中记录元数据，便于后续装订。
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, List, Optional


@dataclass
class ChapterRecord:
    """
    manifest中记录的章节元数据。

    该结构用于在 `manifest.json` 中追踪每章的状态、文件位置、
    以及可能的错误列表，方便前端或调试工具读取。
    """

    chapter_id: str
    slug: str
    title: str
    order: int
    status: str
    files: Dict[str, str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> Dict[str, object]:
        """将记录转换为便于写入manifest.json的序列化字典"""
        return {
            "chapterId": self.chapter_id,
            "slug": self.slug,
            "title": self.title,
            "order": self.order,
            "status": self.status,
            "files": self.files,
            "errors": self.errors,
            "updatedAt": self.updated_at,
        }


class ChapterStorage:
    """
    章节JSON写入与manifest管理器。

    负责：
        - 为每次报告创建独立run目录与manifest快照；
        - 在章节流式生成时即时写入 `stream.raw`；
        - 校验通过后持久化 `chapter.json` 并更新manifest状态。
    """

    def __init__(self, base_dir: str):
        """
        创建章节存储器。

        Args:
            base_dir: 所有输出run目录的根路径
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._manifests: Dict[str, Dict[str, object]] = {}

    # ======== 会话与清单 ========

    def start_session(self, report_id: str, metadata: Dict[str, object]) -> Path:
        """
        为本次报告创建独立的章节输出目录与manifest。

        同时把全局metadata写入 `manifest.json`，供渲染/调试查询。

        参数:
            report_id: 任务ID。
            metadata: Report元数据（标题、主题等）。

        返回:
            Path: 新建的run目录。
        """
        run_dir = self.base_dir / report_id
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "reportId": report_id,
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "metadata": metadata,
            "chapters": [],
        }
        self._manifests[self._key(run_dir)] = manifest
        self._write_manifest(run_dir, manifest)
        return run_dir

    def begin_chapter(self, run_dir: Path, chapter_meta: Dict[str, object]) -> Path:
        """
        创建章节子目录并在manifest中标记为streaming状态。

        会生成 `order-slug` 风格的子目录，并提前登记 raw 文件路径。

        参数:
            run_dir: 会话根目录。
            chapter_meta: 包含 chapterId/title/slug/order 的元数据。

        返回:
            Path: 章节目录。
        """
        slug_value = str(
            chapter_meta.get("slug") or chapter_meta.get("chapterId") or "section"
        )
        chapter_dir = self._chapter_dir(
            run_dir,
            slug_value,
            int(chapter_meta.get("order", 0)),
        )
        record = ChapterRecord(
            chapter_id=str(chapter_meta.get("chapterId")),
            slug=slug_value,
            title=str(chapter_meta.get("title")),
            order=int(chapter_meta.get("order", 0)),
            status="streaming",
            files={"raw": str(self._raw_stream_path(chapter_dir).relative_to(run_dir))},
        )
        self._upsert_record(run_dir, record)
        return chapter_dir

    def persist_chapter(
        self,
        run_dir: Path,
        chapter_meta: Dict[str, object],
        payload: Dict[str, object],
        errors: Optional[List[str]] = None,
    ) -> Path:
        """
        章节流式生成完毕后写入最终JSON并更新manifest状态。

        若校验失败，错误信息会被写入manifest，供前端展示。

        参数:
            run_dir: 会话根目录。
            chapter_meta: 章节元信息。
            payload: 校验通过的章节JSON。
            errors: 可选的错误列表，用于标记invalid状态。

        返回:
            Path: 最终的 `chapter.json` 文件路径。
        """
        slug_value = str(
            chapter_meta.get("slug") or chapter_meta.get("chapterId") or "section"
        )
        chapter_dir = self._chapter_dir(
            run_dir,
            slug_value,
            int(chapter_meta.get("order", 0)),
        )
        final_path = chapter_dir / "chapter.json"
        final_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        record = ChapterRecord(
            chapter_id=str(chapter_meta.get("chapterId")),
            slug=slug_value,
            title=str(chapter_meta.get("title")),
            order=int(chapter_meta.get("order", 0)),
            status="ready" if not errors else "invalid",
            files={
                "raw": str(self._raw_stream_path(chapter_dir).relative_to(run_dir)),
                "json": str(final_path.relative_to(run_dir)),
            },
            errors=errors or [],
        )
        self._upsert_record(run_dir, record)
        return final_path

    def load_chapters(self, run_dir: Path) -> List[Dict[str, object]]:
        """
        从指定run目录读取全部chapter.json并按order排序返回。

        常用于 DocumentComposer 将多个章节装订成整本IR。

        参数:
            run_dir: 会话根目录。

        返回:
            list[dict]: 章节payload列表。
        """
        payloads: List[Dict[str, object]] = []
        for child in sorted(run_dir.iterdir()):
            if not child.is_dir():
                continue
            chapter_path = child / "chapter.json"
            if not chapter_path.exists():
                continue
            try:
                payload = json.loads(chapter_path.read_text(encoding="utf-8"))
                payloads.append(payload)
            except json.JSONDecodeError:
                continue
        payloads.sort(key=lambda x: x.get("order", 0))
        return payloads

    # ======== 文件操作 ========

    @contextmanager
    def capture_stream(self, chapter_dir: Path) -> Generator:
        """
        将流式输出实时写入raw文件。

        通过 contextmanager 暴露文件句柄，简化章节节点的写入逻辑。

        参数:
            chapter_dir: 当前章节目录。

        返回:
            Generator[TextIO]: 作为上下文管理器使用的文件对象。
        """
        raw_path = self._raw_stream_path(chapter_dir)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        with raw_path.open("w", encoding="utf-8") as fp:
            yield fp

    # ======== 内部工具 ========

    def _chapter_dir(self, run_dir: Path, slug: str, order: int) -> Path:
        """根据slug/order生成稳定目录，确保各章分隔存盘且可排序。"""
        safe_slug = self._safe_slug(slug)
        folder = f"{order:03d}-{safe_slug}"
        path = run_dir / folder
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _safe_slug(self, slug: str) -> str:
        """移除危险字符，避免生成非法文件夹名。"""
        slug = slug.replace(" ", "-").replace("/", "-")
        return slug or "section"

    def _raw_stream_path(self, chapter_dir: Path) -> Path:
        """返回某章节流式输出对应的raw文件路径。"""
        return chapter_dir / "stream.raw"

    def _key(self, run_dir: Path) -> str:
        """将run目录解析为字典缓存的键，避免重复读取磁盘。"""
        return str(run_dir.resolve())

    def _manifest_path(self, run_dir: Path) -> Path:
        """获取manifest.json的实际文件路径。"""
        return run_dir / "manifest.json"

    def _write_manifest(self, run_dir: Path, manifest: Dict[str, object]):
        """将内存中的manifest快照全量写回磁盘。"""
        self._manifest_path(run_dir).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _read_manifest(self, run_dir: Path) -> Dict[str, object]:
        """
        从磁盘读取已有manifest。

        进程重启或多实例写盘时可借助它恢复上下文。
        """
        manifest_path = self._manifest_path(run_dir)
        if manifest_path.exists():
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        return {"reportId": run_dir.name, "chapters": []}

    def _upsert_record(self, run_dir: Path, record: ChapterRecord):
        """
        更新或追加manifest中的章节记录，保证顺序一致。

        内部会自动排序并写回缓存+磁盘。
        """
        key = self._key(run_dir)
        manifest = self._manifests.get(key) or self._read_manifest(run_dir)
        chapters: List[Dict[str, object]] = manifest.get("chapters", [])
        chapters = [c for c in chapters if c.get("chapterId") != record.chapter_id]
        chapters.append(record.to_dict())
        chapters.sort(key=lambda x: x.get("order", 0))
        manifest["chapters"] = chapters
        manifest.setdefault("updatedAt", datetime.utcnow().isoformat() + "Z")
        self._manifests[key] = manifest
        self._write_manifest(run_dir, manifest)


__all__ = ["ChapterStorage", "ChapterRecord"]
