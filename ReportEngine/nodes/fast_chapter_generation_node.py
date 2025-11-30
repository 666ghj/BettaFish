from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from loguru import logger
from .base_node import BaseNode
from ..core import TemplateSection, ChapterStorage
from ..ir import IRValidator
from .stream_supervisor import StreamSupervisor
from ..prompts import (
    SYSTEM_PROMPT_CHAPTER_JSON,
    build_chapter_user_prompt
)
from ..nodes.chapter_generation_node import ChapterGenerationNode, ChapterJsonParseError


class FastChapterGenerationNode(ChapterGenerationNode):
    """
    双轨制 - 强模型自适应生成节点。

    特点：
    1. **有状态 (Stateful)**: 维护 conversation history，让模型知道前几章写了什么。
    2. **流式监管 (Supervised)**: 使用 StreamSupervisor 实时监控，防止长生成崩溃。
    3. **兼容输出**: 最终仍产出标准 Chapter JSON 落盘，适配现有 Renderer。
    """

    def __init__(
            self,
            llm_client,
            validator: IRValidator,
            storage: ChapterStorage,
            fallback_llm_clients: Optional[List[Any]] = None,
            error_log_dir: Optional[str | Path] = None,
    ):
        super().__init__(llm_client, validator, storage, fallback_llm_clients, error_log_dir)
        self.conversation_history: List[Dict[str, str]] = []  # 维护多轮对话历史

    def run_continuous(
            self,
            sections: List[TemplateSection],
            context: Dict[str, Any],
            run_dir: Path,
            stream_handler: Optional[Callable[[str, Dict[str, Any]], None]] = None,
            **kwargs
    ) -> List[Dict[str, Any]]:
        """
        连续生成所有章节。

        不同于基类的 run() 处理单章，此方法在一个 Session 中依次生成所有章节，
        并将前序章节的摘要或全文保留在 Context 中，实现"全局连贯"。
        """
        logger.info("[FastTrack] 启动强模型连续生成模式")
        generated_chapters = []

        # 初始化系统提示词（只设一次，作为对话背景）
        # 注意：这里我们复用 SYSTEM_PROMPT_CHAPTER_JSON，但在多轮对话中可能需要调整
        # 为了简单起见，我们将在每轮 user message 中强化上下文

        self.conversation_history = []

        for i, section in enumerate(sections):
            logger.info(f"[FastTrack] 正在生成第 {i + 1}/{len(sections)} 章: {section.title}")

            # 1. 构造当前章的 Prompt
            # 我们复用 _build_payload，但会注入"前情提要"
            llm_payload = self._build_payload(section, context)

            # 增强 Payload：注入前序章节的总结或内容（如果不太长）
            if generated_chapters:
                previous_summaries = []
                for prev in generated_chapters[-2:]:  # 只带最近2章，避免 context 爆炸（即使是强模型也要省）
                    prev_title = prev.get('title', 'Unknown')
                    # 简单提取前章的某些关键点，或者直接告诉模型"接上文"
                    previous_summaries.append(f"已完成章节《{prev_title}》。")

                llm_payload['globalContext']['previousContext'] = "\n".join(previous_summaries)
                llm_payload['globalContext']['instruction'] = "请保持与前文的逻辑连贯性，承接上文风格。"

            user_message = build_chapter_user_prompt(llm_payload)

            # 2. 调用 LLM (带历史记录)
            # 注意：目前的 LLMClient.stream_invoke 通常是无状态的单次调用。
            # 要实现多轮，我们需要手动把 history 拼进去，或者 LLMClient 支持 messages 列表。
            # 假设 LLMClient.stream_invoke 接受 str prompt。
            # 对于强模型，我们可以把 history 拼成 text，或者如果底层支持 list[dict]，最好传 list。
            # 这里为了兼容性，我们将"历史"作为 text 附在本次 prompt 前面，模拟多轮。

            # *更优解*：每次生成完，把 content 存入 self.conversation_history
            # 下一次 prompt = history + new_user_message

            # 但考虑到 Prompt 长度和 Token 费用，我们在 User Prompt 里包含"前情提要"可能更经济，
            # 而不是把整个对话记录发过去。强模型有 128k context，发过去也行。
            # 让我们采用：User Prompt + (Optional) Previous Chapter Content Summary

            # 3. 流式生成 + 监控
            chapter_dir = self.storage.begin_chapter(run_dir, {
                "chapterId": section.chapter_id, "slug": section.slug, "title": section.title
            })

            raw_text = self._stream_llm_with_supervisor(
                user_message,
                chapter_dir,
                stream_handler,
                section_meta={"chapterId": section.chapter_id, "title": section.title},
                **kwargs
            )

            # 4. 解析与后处理 (复用基类逻辑)
            # 强模型虽然强，也需要解析 JSON
            try:
                chapter_json = self._parse_chapter(raw_text)
                self._sanitize_chapter_blocks(chapter_json)
                # 补全元数据
                chapter_json['chapterId'] = section.chapter_id
                chapter_json['title'] = section.title

                # 落盘
                self.storage.persist_chapter(run_dir, chapter_json, chapter_json, None)
                generated_chapters.append(chapter_json)

                # 记录到历史（供下一轮参考）
                self.conversation_history.append({"role": "user", "content": user_message})
                self.conversation_history.append({"role": "assistant", "content": raw_text})

            except Exception as e:
                logger.error(f"[FastTrack] 章节 {section.title} 解析失败: {e}")
                # 强模型失败了，是否降级？
                # 这里简单处理：抛出异常，外层可能会捕获。
                # 或者回退到基类的重试逻辑。
                raise e

        return generated_chapters

    def _stream_llm_with_supervisor(
            self,
            user_message: str,
            chapter_dir: Path,
            stream_callback: Optional[Callable[[str, Dict[str, Any]], None]],
            section_meta: Dict[str, Any],
            **kwargs
    ) -> str:
        """
        带监控的流式生成。
        """
        supervisor = StreamSupervisor()
        chunks = []

        # 构造完整的 messages 列表用于强模型
        # 这里假设 LLMClient 能够处理 messages 或者我们手动拼成 prompt string
        # 简单起见，我们假设 base_url 对应的 backend 能处理长文本 prompt

        # 如果 self.conversation_history 非空，拼接到 user_message 前面？
        # 这是一个简化实现。理想情况下应修改 LLMClient 支持 messages=[] 参数。
        # 这里我们假设 user_message 包含了足够上下文。

        full_prompt = user_message
        if self.conversation_history:
            # 简易拼接历史，模拟 coherent context
            history_text = "\n\n".join(
                [f"{msg['role'].upper()}: {msg['content'][:500]}..." for msg in self.conversation_history])
            full_prompt = f"Previous conversation history:\n{history_text}\n\nCurrent Request:\n{user_message}"

        with self.storage.capture_stream(chapter_dir) as stream_fp:
            stream = self.llm_client.stream_invoke(
                SYSTEM_PROMPT_CHAPTER_JSON,  # 系统提示词
                full_prompt,
                temperature=kwargs.get("temperature", 0.2),
                top_p=kwargs.get("top_p", 0.95),
            )

            for delta in stream:
                # 1. 监控
                if not supervisor.push(delta):
                    logger.warning("[FastTrack] 监控到生成异常，尝试中断或标记（目前策略：继续但记录警告）")
                    # 在更高级实现中，这里可以 raise StopGeneration 异常并触发重试

                # 2. 落盘与回调
                stream_fp.write(delta)
                chunks.append(delta)
                if stream_callback:
                    try:
                        stream_callback(delta, section_meta)
                    except Exception:
                        pass

        return "".join(chunks)

