# agno_agents/report_agent.py
# 综合报告生成 Agent
#
# 输入：3 个 agent 的分析结果（insight/media/query）+ 论坛日志 + Host 引导发言
# 输出：完整的 Markdown 报告 + 渲染好的 HTML 文件
#
# 工作流程（多阶段 + 章节并行）：
# 1. 大纲规划 → 1 次 LLM 调用
# 2. 章节并行写作 → N 次 LLM 调用（asyncio.gather）
# 3. 跨源对比验证 → 1 次 LLM 调用
# 4. 执行摘要生成 → 1 次 LLM 调用
# 5. Markdown 组装 + HTML 渲染

from __future__ import annotations

# 必须最先导入：清代理 + patch agno httpx client
from agno_team import _agno_setup  # noqa: F401

import asyncio
import json
import re
import html as html_lib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from agno.agent import Agent
from agno.models.openai import OpenAIChat

from .report_styles import REPORT_CSS, CHART_JS_LIBS
from .report_blocks import preprocess_custom_blocks


# 通用 OpenAI 客户端 role_map：兼容 DeepSeek/Qwen 等不识别 "developer" 角色的 API
_ROLE_MAP = {
    "system": "system",
    "user": "user",
    "assistant": "assistant",
    "tool": "tool",
    "model": "assistant",
}


# ===== Prompts =====

OUTLINE_PROMPT = """你是一位资深的舆情分析报告主编。你将收到三个专业 Agent 对同一主题的分析报告：
- **InsightAgent**：基于本地社交媒体数据库（微博、B站、知乎、贴吧、抖音、快手、小红书）+ 海外社区（HN、GitHub、Reddit、YouTube）的舆情挖掘
- **MediaAgent**：基于多模态网页搜索（综合搜索、图片、结构化数据卡）的媒体内容分析
- **QueryAgent**：基于新闻搜索（Tavily）的新闻深度分析与事实核查

以及一份**论坛主持人**对三 Agent 讨论过程的引导记录。

你的任务：**为最终的综合报告设计一个专业、完整、有深度的章节大纲**。

**要求：**
1. 章节数量：5-7 章（不含执行摘要、跨源验证、附录）
2. 每章必须有明确的分析角度，避免主题重复
3. 章节顺序遵循：宏观背景 → 现象描述 → 数据分析 → 深层解读 → 影响评估 → 趋势预测
4. 每章标注：title（标题）、focus（核心问题）、source_agents（应主要参考哪些 agent，可多选）、target_words（目标字数 1500-2500）

**输出格式（严格 JSON，不要任何解释）**：
```json
{
  "report_title": "报告主标题（吸引人，专业，不超过30字）",
  "report_subtitle": "副标题（一句话说明报告核心价值）",
  "chapters": [
    {
      "id": "ch1",
      "title": "章节标题",
      "focus": "本章要回答的核心问题",
      "source_agents": ["insight", "media", "query"],
      "target_words": 2000
    }
  ]
}
```

**输入数据预览：**
{input_preview}

只返回 JSON，不要任何额外文字。"""


CHAPTER_PROMPT = """你是一位资深的舆情分析报告主笔。现在请你撰写综合报告中的一章。

**报告主题**：{query}
**章节标题**：{chapter_title}
**核心问题**：{chapter_focus}
**目标字数**：{target_words} 字

**可用素材（来自三个分析 Agent 的原始报告）**：

{source_materials}

**论坛主持人的相关引导**：
{host_hints}

## 📊 可视化组件（本章必须使用至少 2-3 个）

除了 Markdown 正文，你可以嵌入以下专业组件提升报告的专业度和信息密度。**每一章都必须至少使用 2-3 个可视化组件**。

### 1. KPI 数据卡片（用于突出关键数据）
格式：
```
<kpi-grid>
[
  {{"label": "话题阅读量", "value": "5.2", "unit": "亿", "delta": "+23%", "tone": "up"}},
  {{"label": "正面情感占比", "value": "62", "unit": "%", "delta": "+8pp", "tone": "up"}},
  {{"label": "主要平台数", "value": "7", "tone": "neutral"}},
  {{"label": "负面争议数", "value": "1.2", "unit": "K+", "delta": "+45%", "tone": "down"}}
]
</kpi-grid>
```
tone 只能是 "up"（正向/增长）/ "down"（负向/下降）/ "neutral"（中性）。

### 2. 图表卡片（用于数据对比/趋势/分布）
支持 Chart.js 所有图表类型：bar / line / pie / doughnut / radar。

**示例 1 - 柱状图（平台情感对比）**：
```
<chart-card title="各平台情感分布对比">
{{
  "type": "bar",
  "data": {{
    "labels": ["微博", "B站", "知乎", "抖音", "小红书"],
    "datasets": [
      {{"label": "正面%", "data": [62, 71, 58, 55, 66]}},
      {{"label": "负面%", "data": [23, 18, 27, 30, 19]}},
      {{"label": "中性%", "data": [15, 11, 15, 15, 15]}}
    ]
  }}
}}
</chart-card>
```

**示例 2 - 饼图（情感分布）**：
```
<chart-card title="总体情感占比">
{{
  "type": "doughnut",
  "data": {{
    "labels": ["正面", "负面", "中性"],
    "datasets": [{{"data": [62, 23, 15]}}]
  }}
}}
</chart-card>
```

**示例 3 - 折线图（趋势）**：
```
<chart-card title="话题热度 7 日趋势">
{{
  "type": "line",
  "data": {{
    "labels": ["2/1", "2/2", "2/3", "2/4", "2/5", "2/6", "2/7"],
    "datasets": [{{"label": "阅读量(万)", "data": [120, 180, 340, 520, 780, 650, 590]}}]
  }}
}}
</chart-card>
```

**数据要求**：图表里的数据**必须来自素材中真实提到的数字**。如果素材里没有量化数据，就用定性描述生成估算值，但要在图表标题中标注"估算"字样。不要编造完全不存在的数据维度。

### 3. 信息源矩阵（用于跨源对比章节）
```
<info-matrix title="三 Agent 数据覆盖矩阵">
{{
  "headers": ["维度", "InsightAgent", "MediaAgent", "QueryAgent"],
  "rows": [
    {{"dimension": "社交媒体热度", "insightagent": "primary", "mediaagent": "secondary", "queryagent": "none"}},
    {{"dimension": "主流媒体报道", "insightagent": "none", "mediaagent": "primary", "queryagent": "primary"}},
    {{"dimension": "图片视觉数据", "insightagent": "weak", "mediaagent": "primary", "queryagent": "none"}}
  ]
}}
</info-matrix>
```
每个 cell 值：`primary`（★★★主力）/ `secondary`（★★部分）/ `weak`（★弱）/ `none`（—无）。

### 4. Callout 提示框（用于强调关键洞察/风险）
```
<callout type="insight" title="核心洞察">
**程序员社区对 Claude Code 的评价呈现明显的"两极化"**：技术爱好者高度推崇其命令行体验，但中小团队因定价产生强烈反弹。
</callout>
```
type：`info` / `insight` / `warning` / `danger` / `success`。

### 5. 时间线（用于事件演变章节）
```
<timeline title="Claude Code 关键事件时间线">
[
  {{"date": "2025-02", "event": "Claude Code 首次发布", "type": "release"}},
  {{"date": "2025-03", "event": "Pro 订阅定价引发争议", "type": "crisis", "detail": "月费从免费试用切换到20美元"}},
  {{"date": "2025-04", "event": "推出学生折扣方案", "type": "update"}}
]
</timeline>
```
type：`default` / `release`（绿色）/ `crisis`（红色）/ `update`（橙色）。

### 6. 用户原声卡片（突出典型用户评论）
```
<quote-card source="微博" author="码农日记" likes="12453">
用 Claude Code 重构了一个 5000 行的老项目，效率提升至少 10 倍。Anthropic 牛逼
</quote-card>
```

---

## 写作要求

1. **结构化呈现**：使用清晰的 H2/H3 二级三级标题组织内容
2. **数据密集**：每段至少 1-2 个具体数据点（数字、引用、案例）
3. **可视化优先**：能用组件的尽量用组件，不要都堆在 Markdown 表格里
   - 数字对比 → 用 chart-card（bar/line）
   - 占比分布 → 用 chart-card（pie/doughnut）或 kpi-grid
   - 关键数据 → 用 kpi-grid
   - 关键洞察 → 用 callout
   - 用户原话 → 用 quote-card 而不是 markdown `>`
   - 事件演变 → 用 timeline
4. **多源融合**：综合三个 Agent 的发现，形成统一叙事
5. **引用标注**：引用某个 Agent 的发现时用 *(来源: InsightAgent)* 这种斜体标注

**禁止事项**：
- ❌ 不要写"本章将分析..."这种废话开头
- ❌ 不要在章节末尾写"综上所述..."这种总结
- ❌ 不要重复其他章节的内容
- ❌ 不要输出 JSON，直接输出 Markdown 正文（JSON 只能在自定义标签内部）
- ❌ 自定义标签内的 JSON 不能有多余换行或注释，必须是合法 JSON
- ❌ 自定义标签的内容不能嵌套其他自定义标签

直接输出本章 Markdown 正文（从 ## 章节标题 开始），目标 {target_words} 字，**必须包含至少 2-3 个可视化组件**。"""


CROSS_VALIDATION_PROMPT = """你是舆情数据交叉验证专家。基于以下三个 Agent 的分析结果，进行跨源对比验证。

**主题**：{query}

**三 Agent 报告摘要**：
{agent_summaries}

## 📊 必须使用的可视化组件

### 1. 信息源覆盖矩阵（必须）
用 `<info-matrix>` 组件替代普通 markdown 表格：
```
<info-matrix title="三 Agent 数据覆盖矩阵">
{{
  "headers": ["维度", "InsightAgent", "MediaAgent", "QueryAgent"],
  "rows": [
    {{"dimension": "社交媒体热度", "insightagent": "primary", "mediaagent": "secondary", "queryagent": "none"}},
    {{"dimension": "主流媒体报道", "insightagent": "none", "mediaagent": "primary", "queryagent": "primary"}},
    {{"dimension": "图片视觉数据", "insightagent": "weak", "mediaagent": "primary", "queryagent": "none"}},
    {{"dimension": "事实核查", "insightagent": "none", "mediaagent": "secondary", "queryagent": "primary"}},
    {{"dimension": "海外视角", "insightagent": "secondary", "mediaagent": "secondary", "queryagent": "primary"}}
  ]
}}
</info-matrix>
```
cell 值：primary（★★★主力）/ secondary（★★部分）/ weak（★弱）/ none（—无）。

### 2. 可信度评级 KPI（必须）
```
<kpi-grid>
[
  {{"label": "数据覆盖度", "value": "A", "delta": "完整", "tone": "up"}},
  {{"label": "时效性", "value": "B", "delta": "近期", "tone": "neutral"}},
  {{"label": "偏差风险", "value": "B", "delta": "可控", "tone": "neutral"}},
  {{"label": "整体评级", "value": "A-", "delta": "可信", "tone": "up"}}
]
</kpi-grid>
```

---

## 输出结构

请输出一份**跨源验证分析**章节（约 1500-2000 字）：

## 跨源对比与可信度评估

### 信息源覆盖矩阵

[必须使用 info-matrix 组件，包含 5-7 行维度]

### 三方共识

提炼三个 Agent 都达成一致的核心结论（3-5 条），每条说明：
- 共识内容
- 三方各自的支撑证据
- 可信度评分（高/中/低）

### 三方分歧

识别三个 Agent 之间存在明显差异的判断（2-4 处），每处说明：
- 分歧的具体内容
- 各方观点
- 可能的原因（数据源差异？时间窗口？立场差异？）
- 哪一方更可信，理由是什么

**对于关键分歧**，用 callout 高亮：
```
<callout type="warning" title="关键分歧">
...
</callout>
```

### 信息可信度评估

[必须使用上面的 kpi-grid 组件]

随后用文字说明为什么是这个评级。

直接输出 Markdown（可嵌入自定义标签），不要解释。"""


EXECUTIVE_SUMMARY_PROMPT = """你是高管简报撰写专家。基于以下完整报告内容，撰写一份给高管/决策者的执行摘要。

**报告主题**：{query}
**报告标题**：{report_title}
**章节内容（节选）**：

{chapters_preview}

**跨源验证结论**：
{cross_validation_summary}

## 📊 必须使用的可视化组件

执行摘要必须大量使用可视化组件，让高管一眼看到关键信息：

### 1. KPI 数据卡片（必须，4-6 个核心指标）
```
<kpi-grid>
[
  {{"label": "指标名", "value": "数值", "unit": "单位", "delta": "变化", "tone": "up/down/neutral"}}
]
</kpi-grid>
```

### 2. 整体情感分布饼图（必须）
```
<chart-card title="舆情情感总览">
{{
  "type": "doughnut",
  "data": {{
    "labels": ["正面", "负面", "中性"],
    "datasets": [{{"data": [X, Y, Z]}}]
  }}
}}
</chart-card>
```

### 3. 关键洞察 Callout（必须，用于一句话结论）
```
<callout type="insight" title="核心结论">
一句话概括整个分析的核心结论
</callout>
```

### 4. 风险预警 Callout（必须）
```
<callout type="warning" title="风险预警">
需要警惕的风险点
</callout>
```

---

## 输出结构

请严格按以下结构输出：

## 执行摘要

[使用 callout type="insight" 组件写一句话结论]

### 关键数据快览

[使用 kpi-grid 组件，包含 4-6 个最重要的数据指标]

### 情感全景

[使用 chart-card doughnut 图表展示整体情感分布]

### 五大关键发现

1. **[发现标题]**：具体内容（50-80 字）
2. **[发现标题]**：具体内容
3. ...

### 核心建议

1. [具体行动建议]
2. ...
3. ...

### 风险预警

[使用 callout type="warning" 组件列出 2-3 个主要风险]

---

**数据来源**：数字和比例**必须来自章节内容里提到的真实数据**。如果没有精确数字，可以基于定性描述估算，但要保持内部一致性。

直接输出 Markdown（可嵌入自定义标签），不要其他解释。"""


# ===== Helper functions =====

def _summarize_for_outline(agent_results: Dict[str, Any], host_speeches: List[str], max_chars: int = 3000) -> str:
    """为大纲规划阶段生成精简的输入预览"""
    parts = []
    for agent_type, result in agent_results.items():
        if not result:
            continue
        agent_name = result.get("agent_name", agent_type.title())
        paragraphs = result.get("paragraphs", [])
        parts.append(f"### {agent_name}")
        if paragraphs:
            parts.append("段落标题：")
            for p in paragraphs:
                parts.append(f"- {p.get('title', '')}")
        # 取最终报告前 600 字作为预览
        final = result.get("final_report", "")
        if final:
            parts.append(f"报告开头：{final[:600]}...")
        parts.append("")

    if host_speeches:
        parts.append("### 论坛主持人引导（关键观点）")
        for i, s in enumerate(host_speeches[:3], 1):
            parts.append(f"{i}. {s[:300]}...")

    text = "\n".join(parts)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...(内容已截断)"
    return text


def _build_source_materials(
    agent_results: Dict[str, Any],
    source_agents: List[str],
    chapter_focus: str,
    max_per_agent: int = 4000,
) -> str:
    """为某一章节抽取相关 agent 的素材"""
    parts = []
    name_map = {"insight": "InsightAgent (社交媒体舆情)", "media": "MediaAgent (多模态网页)", "query": "QueryAgent (新闻调查)"}

    for at in source_agents:
        result = agent_results.get(at)
        if not result:
            continue
        parts.append(f"### {name_map.get(at, at)}")
        # 优先用 paragraphs（结构化），否则用 final_report
        paragraphs = result.get("paragraphs", [])
        if paragraphs:
            for p in paragraphs:
                title = p.get("title", "")
                state = p.get("paragraph_latest_state", "")
                parts.append(f"\n**{title}**\n{state[:max_per_agent // max(len(paragraphs), 1)]}")
        else:
            parts.append(result.get("final_report", "")[:max_per_agent])
        parts.append("")
    return "\n".join(parts)


def _filter_relevant_host_speeches(host_speeches: List[str], chapter_focus: str) -> str:
    """从所有 host 发言里找跟本章 focus 相关的（简单实现：返回最近 2 条）"""
    if not host_speeches:
        return "（本章无相关主持人引导）"
    return "\n\n".join(f"- {s[:500]}..." if len(s) > 500 else f"- {s}" for s in host_speeches[-2:])


# ===== ReportAgent core =====

class ReportAgent:
    """综合报告生成器（支持异步章节并行）"""

    def __init__(self, config=None):
        if config is None:
            from config import settings
            config = settings
        self.config = config

        # 必须三个字段一组回退：避免 DeepSeek 的 key 配 aihubmix 的 base_url
        if config.REPORT_ENGINE_API_KEY:
            api_key = config.REPORT_ENGINE_API_KEY
            base_url = config.REPORT_ENGINE_BASE_URL
            model_name = config.REPORT_ENGINE_MODEL_NAME
        elif config.FORUM_HOST_API_KEY:
            print("⚠️  REPORT_ENGINE_API_KEY 未配置，回退到 FORUM_HOST_*（qwen）")
            api_key = config.FORUM_HOST_API_KEY
            base_url = config.FORUM_HOST_BASE_URL
            model_name = config.FORUM_HOST_MODEL_NAME
        elif config.QUERY_ENGINE_API_KEY:
            print("⚠️  REPORT_ENGINE_API_KEY 未配置，回退到 QUERY_ENGINE_*")
            api_key = config.QUERY_ENGINE_API_KEY
            base_url = config.QUERY_ENGINE_BASE_URL
            model_name = config.QUERY_ENGINE_MODEL_NAME
        else:
            raise ValueError("ReportAgent 需要 REPORT_ENGINE_API_KEY / FORUM_HOST_API_KEY / QUERY_ENGINE_API_KEY 至少一个")

        self.model_name = model_name
        print(f"[ReportAgent] 使用模型: {model_name}（agno 模式）")

        # 创建一个共享的 OpenAIChat model（每个 agent 用独立实例避免状态污染）
        def _make_model():
            return OpenAIChat(
                id=model_name,
                api_key=api_key,
                base_url=base_url,
                role_map=_ROLE_MAP,
            )

        # ===== 4 个专用 agno Agent =====

        # Stage 1: 大纲规划（输出 JSON）
        self.outline_agent = Agent(
            name="OutlineDesigner",
            model=_make_model(),
            instructions="你是一位资深的舆情分析报告主编，必须输出严格的 JSON 格式（不要任何 markdown 代码块包裹）。",
            system_message_role="system",
            markdown=False,
        )

        # Stage 2: 章节写作（输出 Markdown + 自定义可视化标签）
        self.chapter_agent = Agent(
            name="ChapterWriter",
            model=_make_model(),
            instructions="你是一位资深的舆情分析报告主笔，擅长将多源数据融合为深度洞察，能够使用 chart-card / kpi-grid / callout 等专业可视化组件。",
            system_message_role="system",
            markdown=True,
        )

        # Stage 3: 跨源验证
        self.cross_validator_agent = Agent(
            name="CrossValidator",
            model=_make_model(),
            instructions="你是舆情数据交叉验证专家，擅长识别多源数据的共识与分歧。",
            system_message_role="system",
            markdown=True,
        )

        # Stage 4: 执行摘要
        self.exec_summary_agent = Agent(
            name="ExecutiveSummaryWriter",
            model=_make_model(),
            instructions="你是高管简报撰写专家，能用最简洁的语言传达最核心的洞察。",
            system_message_role="system",
            markdown=True,
        )

    async def _agent_run(self, agent: Agent, user_prompt: str) -> str:
        """统一的 agno agent 异步调用入口，自动剥取 content"""
        try:
            response = await agent.arun(user_prompt)
            return response.content if response else ""
        except Exception as e:
            print(f"⚠️  agno agent {agent.name} 调用失败: {e}")
            return ""

    @staticmethod
    def _parse_json(text: str) -> Optional[Dict]:
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return None

    # ===== 阶段一：大纲规划 =====
    async def generate_outline(
        self,
        query: str,
        agent_results: Dict[str, Any],
        host_speeches: List[str],
    ) -> Dict[str, Any]:
        print("📋 [Stage 1/5] 规划报告大纲（agno OutlineDesigner）...")
        input_preview = _summarize_for_outline(agent_results, host_speeches)
        prompt = OUTLINE_PROMPT.replace("{input_preview}", input_preview)

        raw = await self._agent_run(self.outline_agent, prompt)

        outline = self._parse_json(raw)
        if not outline or "chapters" not in outline:
            # 兜底：生成默认 5 章结构
            outline = {
                "report_title": f"关于「{query}」的综合舆情分析报告",
                "report_subtitle": "基于多源数据的深度洞察",
                "chapters": [
                    {"id": "ch1", "title": "事件背景与核心脉络", "focus": "梳理事件起因、时间线、关键节点", "source_agents": ["query", "insight"], "target_words": 2000},
                    {"id": "ch2", "title": "舆情热度与传播分析", "focus": "数据统计、平台分布、传播路径", "source_agents": ["insight", "media"], "target_words": 2000},
                    {"id": "ch3", "title": "公众情感与观点图谱", "focus": "情感倾向、观点分布、争议焦点", "source_agents": ["insight"], "target_words": 2200},
                    {"id": "ch4", "title": "媒体报道与权威信息", "focus": "主流媒体报道、官方信息、事实核查", "source_agents": ["query", "media"], "target_words": 2000},
                    {"id": "ch5", "title": "深层影响与趋势研判", "focus": "社会影响、未来趋势、风险预警", "source_agents": ["insight", "media", "query"], "target_words": 2200},
                ],
            }
        chapter_count = len(outline.get("chapters", []))
        print(f"   ✅ 规划了 {chapter_count} 章: {outline.get('report_title', '')}")
        return outline

    # ===== 阶段二：章节并行写作 =====
    async def write_chapter(
        self,
        query: str,
        chapter: Dict[str, Any],
        agent_results: Dict[str, Any],
        host_speeches: List[str],
    ) -> Dict[str, Any]:
        title = chapter.get("title", "")
        focus = chapter.get("focus", "")
        source_agents = chapter.get("source_agents", ["insight", "media", "query"])
        target_words = chapter.get("target_words", 2000)

        source_materials = _build_source_materials(agent_results, source_agents, focus)
        host_hints = _filter_relevant_host_speeches(host_speeches, focus)

        prompt = CHAPTER_PROMPT.format(
            query=query,
            chapter_title=title,
            chapter_focus=focus,
            target_words=target_words,
            source_materials=source_materials,
            host_hints=host_hints,
        )

        content = await self._agent_run(self.chapter_agent, prompt)
        print(f"   ✅ 章节「{title}」完成（{len(content)} 字）")

        return {**chapter, "content": content}

    async def write_all_chapters(
        self,
        query: str,
        outline: Dict[str, Any],
        agent_results: Dict[str, Any],
        host_speeches: List[str],
    ) -> List[Dict[str, Any]]:
        print(f"\n📝 [Stage 2/5] 并行写作 {len(outline.get('chapters', []))} 个章节（agno ChapterWriter）...")
        tasks = [
            self.write_chapter(query, ch, agent_results, host_speeches)
            for ch in outline.get("chapters", [])
        ]
        return await asyncio.gather(*tasks)

    # ===== 阶段三：跨源验证 =====
    async def cross_validate(
        self,
        query: str,
        agent_results: Dict[str, Any],
    ) -> str:
        print("\n🔍 [Stage 3/5] 跨源对比验证（agno CrossValidator）...")
        summaries = []
        for at, result in agent_results.items():
            if not result:
                continue
            name_map = {"insight": "InsightAgent", "media": "MediaAgent", "query": "QueryAgent"}
            summary = result.get("final_report", "")[:2500]
            summaries.append(f"### {name_map.get(at, at)}\n{summary}")

        agent_summaries_text = "\n\n".join(summaries)
        prompt = CROSS_VALIDATION_PROMPT.format(
            query=query,
            agent_summaries=agent_summaries_text,
        )
        result = await self._agent_run(self.cross_validator_agent, prompt)
        print(f"   ✅ 跨源验证完成（{len(result)} 字）")
        return result

    # ===== 阶段四：执行摘要 =====
    async def generate_executive_summary(
        self,
        query: str,
        outline: Dict[str, Any],
        chapters: List[Dict[str, Any]],
        cross_validation: str,
    ) -> str:
        print("\n📊 [Stage 4/5] 撰写执行摘要（agno ExecutiveSummaryWriter）...")
        chapters_preview = "\n\n".join(
            f"### {ch['title']}\n{ch.get('content', '')[:1000]}..." for ch in chapters
        )

        prompt = EXECUTIVE_SUMMARY_PROMPT.format(
            query=query,
            report_title=outline.get("report_title", ""),
            chapters_preview=chapters_preview[:6000],
            cross_validation_summary=cross_validation[:2000],
        )
        result = await self._agent_run(self.exec_summary_agent, prompt)
        print(f"   ✅ 执行摘要完成（{len(result)} 字）")
        return result

    # ===== 阶段五：组装 Markdown =====
    def assemble_markdown(
        self,
        query: str,
        outline: Dict[str, Any],
        executive_summary: str,
        chapters: List[Dict[str, Any]],
        cross_validation: str,
        forum_log: str,
        host_speeches: List[str],
    ) -> str:
        report_title = outline.get("report_title", f"关于「{query}」的综合舆情分析报告")
        report_subtitle = outline.get("report_subtitle", "")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        parts = []

        # 封面信息（用 metadata 块标记）
        parts.append(f"<!-- COVER\ntitle: {report_title}\nsubtitle: {report_subtitle}\nquery: {query}\ndate: {timestamp}\n-->")
        parts.append("")

        # 执行摘要
        parts.append(executive_summary)
        parts.append("")

        # 目录占位（HTML 渲染时会基于 H1/H2 自动生成）
        parts.append("<!-- TOC -->")
        parts.append("")

        # 章节正文：统一前置一个 # 标题，便于 HTML 渲染时自动编号"第X章"
        for ch in chapters:
            content = ch.get("content", "").strip()
            chapter_title = ch.get("title", "").strip()

            # 策略：无论 LLM 是否在内部用了 #/##/### 标题，
            # 都强制在最前面加一个 # 章节标题，作为 H1。
            # 同时把 LLM 内部所有的标题级别下推一级（# → ##, ## → ###, ...）
            # 这样章节标题永远是 H1，内部分节是 H2/H3/H4。
            if content:
                # 下推所有 markdown 标题级别一级（最多到 H6）
                def _shift_heading(m):
                    hashes = m.group(1)
                    text = m.group(2)
                    new_level = min(len(hashes) + 1, 6)
                    return "#" * new_level + " " + text

                content = re.sub(r"^(#{1,5})\s+(.+)$", _shift_heading, content, flags=re.MULTILINE)

            parts.append(f"# {chapter_title}")
            parts.append("")
            parts.append(content)
            parts.append("")

        # 跨源验证
        parts.append("# 跨源数据对比与可信度评估")
        parts.append("")
        # 去掉跨源验证里可能的重复标题
        cv = re.sub(r"^##?\s*跨源.*?\n", "", cross_validation, count=1)
        parts.append(cv)
        parts.append("")

        # 附录：论坛日志
        parts.append("# 附录：分析过程论坛日志")
        parts.append("")
        parts.append(f"以下是 InsightAgent / MediaAgent / QueryAgent 在分析过程中的发言记录，以及 ForumHost 主持人的 {len(host_speeches)} 次引导发言。\n")
        parts.append("```")
        parts.append(forum_log[:8000] + ("\n...(已截断)" if len(forum_log) > 8000 else ""))
        parts.append("```")

        return "\n".join(parts)

    # ===== 阶段六：渲染 HTML =====
    def render_html(self, markdown_text: str, query: str) -> str:
        print("\n🎨 [Stage 5/5] 渲染 HTML（含可视化组件）...")

        try:
            import markdown as md_lib
        except ImportError:
            return self._render_html_fallback(markdown_text)

        # 提取封面信息
        cover_match = re.search(r"<!--\s*COVER\s*\n([\s\S]*?)\n-->", markdown_text)
        cover_info = {}
        if cover_match:
            for line in cover_match.group(1).split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    cover_info[k.strip()] = v.strip()
            markdown_text = markdown_text.replace(cover_match.group(0), "")

        # ⭐ 步骤 1：预处理自定义可视化块（转换为占位符，HTML 先被收集）
        markdown_text, block_collector = preprocess_custom_blocks(markdown_text)
        print(f"   🧩 检测到 {len(block_collector.blocks)} 个可视化组件")

        # 步骤 2：markdown → html
        body_html = md_lib.markdown(
            markdown_text,
            extensions=["tables", "fenced_code", "toc", "nl2br", "sane_lists"],
        )

        # ⭐ 步骤 3：恢复占位符为真实的可视化 HTML
        body_html = block_collector.restore(body_html)

        # 构建完整 HTML
        title = cover_info.get("title", "舆情分析报告")
        subtitle = cover_info.get("subtitle", "")
        date = cover_info.get("date", datetime.now().strftime("%Y-%m-%d"))
        query_safe = html_lib.escape(cover_info.get("query", query))

        full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html_lib.escape(title)}</title>
    {CHART_JS_LIBS}
    {REPORT_CSS}
</head>
<body>
    <div class="cover">
        <div class="badge">舆情洞察报告</div>
        <h1>{html_lib.escape(title)}</h1>
        <div class="subtitle">{html_lib.escape(subtitle)}</div>
        <div class="meta">
            <div><strong>分析主题：</strong>{query_safe}</div>
            <div><strong>生成时间：</strong>{date}</div>
            <div><strong>数据来源：</strong>InsightAgent · MediaAgent · QueryAgent</div>
            <div><strong>主持人引导：</strong>ForumHost</div>
        </div>
    </div>

    {body_html}

    <div class="footer">
        © {datetime.now().year} agno-mirofish · 由 ReportAgent 自动生成 · 基于 agno 框架
    </div>
</body>
</html>"""
        return full_html

    def _render_html_fallback(self, markdown_text: str) -> str:
        """没有 markdown 库时的纯文本回退"""
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
{REPORT_CSS}
</head><body><pre>{html_lib.escape(markdown_text)}</pre></body></html>"""

    # ===== 主入口 =====
    async def generate_report(
        self,
        query: str,
        agent_results: Dict[str, Any],
        forum_log: str = "",
        host_speeches: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """
        生成完整的综合报告。

        Returns:
            dict: {
                "title": 报告标题,
                "markdown": 完整的 Markdown 报告,
                "html": 完整的 HTML 报告,
                "outline": 大纲（dict）,
                "stats": {章节数、字数等}
            }
        """
        if host_speeches is None:
            host_speeches = []

        print(f"\n{'=' * 60}")
        print(f"  ReportAgent 启动")
        print(f"  主题: {query}")
        print(f"  Agent 报告数: {len(agent_results)}")
        print(f"  Host 引导次数: {len(host_speeches)}")
        print(f"{'=' * 60}")

        # 阶段一：大纲
        outline = await self.generate_outline(query, agent_results, host_speeches)

        # 阶段二：章节并行写作
        chapters = await self.write_all_chapters(query, outline, agent_results, host_speeches)

        # 阶段三：跨源验证（可与章节并行，但放在后面好理解）
        cross_validation = await self.cross_validate(query, agent_results)

        # 阶段四：执行摘要
        executive_summary = await self.generate_executive_summary(
            query, outline, chapters, cross_validation
        )

        # 阶段五：组装 Markdown
        print("\n📦 组装 Markdown...")
        markdown_text = self.assemble_markdown(
            query=query,
            outline=outline,
            executive_summary=executive_summary,
            chapters=chapters,
            cross_validation=cross_validation,
            forum_log=forum_log,
            host_speeches=host_speeches,
        )

        # 阶段六：HTML 渲染
        html_text = self.render_html(markdown_text, query)

        total_chars = len(markdown_text)
        print(f"\n{'=' * 60}")
        print(f"  ✅ 报告生成完成")
        print(f"  Markdown 长度: {total_chars} 字符")
        print(f"  章节数: {len(chapters)}")
        print(f"{'=' * 60}\n")

        return {
            "title": outline.get("report_title", ""),
            "markdown": markdown_text,
            "html": html_text,
            "outline": outline,
            "stats": {
                "chapter_count": len(chapters),
                "markdown_chars": total_chars,
                "html_chars": len(html_text),
            },
        }


# ===== 命令行风格入口 =====

def create_report_agent(config=None) -> ReportAgent:
    return ReportAgent(config=config)


async def run_report_generation_async(
    query: str,
    agent_results: Dict[str, Any],
    forum_log: str = "",
    host_speeches: Optional[List[str]] = None,
    config=None,
) -> Dict[str, str]:
    agent = create_report_agent(config)
    return await agent.generate_report(query, agent_results, forum_log, host_speeches)


def run_report_generation(
    query: str,
    agent_results: Dict[str, Any],
    forum_log: str = "",
    host_speeches: Optional[List[str]] = None,
    config=None,
) -> Dict[str, str]:
    """同步入口"""
    return asyncio.run(
        run_report_generation_async(query, agent_results, forum_log, host_speeches, config)
    )
