# agno_agents/insight_agent.py
# 迁移自 InsightEngine/agent.py (DeepSearchAgent)
# 定位：本地社交媒体数据库舆情分析（微博/B站/知乎/贴吧等）

import json
import httpx
from openai import OpenAI as _OpenAI
from agno.agent import Agent
from agno.models.openai import OpenAIChat

from .models import (
    SearchDecision,
    ReportStructure,
    ParagraphResult,
    AnalysisResult,
    parse_analysis_result,
)

from agno_tools import (
    # 中文社交媒体（本地数据库）
    search_hot_content, search_topic_globally, search_topic_by_date,
    get_comments_for_topic, search_topic_on_platform, analyze_sentiment,
    # 海外数据源（实时 API）
    search_hackernews, search_hackernews_recent, search_hackernews_comments,
    search_github_repos, search_github_issues, search_github_code,
    search_youtube_videos, get_youtube_comments, search_youtube_with_comments,
    search_reddit, get_subreddit_hot, get_reddit_post_comments,
)

# ===== JSON Schema 定义（保留原始 Schema，供 prompt 引用）=====

output_schema_report_structure = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "content": {"type": "string"}
        }
    }
}

input_schema_first_search = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "content": {"type": "string"}
    }
}

output_schema_first_search = {
    "type": "object",
    "properties": {
        "search_query": {"type": "string"},
        "search_tool": {"type": "string"},
        "reasoning": {"type": "string"},
        "start_date": {"type": "string", "description": "开始日期，格式YYYY-MM-DD，search_topic_by_date和search_topic_on_platform工具可能需要"},
        "end_date": {"type": "string", "description": "结束日期，格式YYYY-MM-DD，search_topic_by_date和search_topic_on_platform工具可能需要"},
        "platform": {"type": "string", "description": "平台名称，search_topic_on_platform工具必需，可选值：bilibili, weibo, douyin, kuaishou, xhs, zhihu, tieba"},
        "time_period": {"type": "string", "description": "时间周期，search_hot_content工具可选，可选值：24h, week, year"},
        "enable_sentiment": {"type": "boolean", "description": "是否启用自动情感分析，默认为true，适用于除analyze_sentiment外的所有搜索工具"},
        "texts": {"type": "array", "items": {"type": "string"}, "description": "文本列表，仅用于analyze_sentiment工具"}
    },
    "required": ["search_query", "search_tool", "reasoning"]
}

input_schema_first_summary = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "content": {"type": "string"},
        "search_query": {"type": "string"},
        "search_results": {
            "type": "array",
            "items": {"type": "string"}
        }
    }
}

output_schema_first_summary = {
    "type": "object",
    "properties": {
        "paragraph_latest_state": {"type": "string"}
    }
}

input_schema_reflection = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "content": {"type": "string"},
        "paragraph_latest_state": {"type": "string"}
    }
}

output_schema_reflection = {
    "type": "object",
    "properties": {
        "search_query": {"type": "string"},
        "search_tool": {"type": "string"},
        "reasoning": {"type": "string"},
        "start_date": {"type": "string", "description": "开始日期，格式YYYY-MM-DD，search_topic_by_date和search_topic_on_platform工具可能需要"},
        "end_date": {"type": "string", "description": "结束日期，格式YYYY-MM-DD，search_topic_by_date和search_topic_on_platform工具可能需要"},
        "platform": {"type": "string", "description": "平台名称，search_topic_on_platform工具必需，可选值：bilibili, weibo, douyin, kuaishou, xhs, zhihu, tieba"},
        "time_period": {"type": "string", "description": "时间周期，search_hot_content工具可选，可选值：24h, week, year"},
        "enable_sentiment": {"type": "boolean", "description": "是否启用自动情感分析，默认为true，适用于除analyze_sentiment外的所有搜索工具"},
        "texts": {"type": "array", "items": {"type": "string"}, "description": "文本列表，仅用于analyze_sentiment工具"}
    },
    "required": ["search_query", "search_tool", "reasoning"]
}

input_schema_reflection_summary = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "content": {"type": "string"},
        "search_query": {"type": "string"},
        "search_results": {
            "type": "array",
            "items": {"type": "string"}
        },
        "paragraph_latest_state": {"type": "string"}
    }
}

output_schema_reflection_summary = {
    "type": "object",
    "properties": {
        "updated_paragraph_latest_state": {"type": "string"}
    }
}

input_schema_report_formatting = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "paragraph_latest_state": {"type": "string"}
        }
    }
}

# ===== 系统提示词定义（完整保留原始 prompt）=====

SYSTEM_PROMPT_REPORT_STRUCTURE = f"""
你是一位专业的舆情分析师和报告架构师。给定一个查询，你需要规划一个全面、深入的舆情分析报告结构。

**报告规划要求：**
1. **段落数量**：设计5个核心段落，每个段落都要有足够的深度和广度
2. **内容丰富度**：每个段落应该包含多个子话题和分析维度，确保能挖掘出大量真实数据
3. **逻辑结构**：从宏观到微观、从现象到本质、从数据到洞察的递进式分析
4. **多维分析**：确保涵盖情感倾向、平台差异、时间演变、群体观点、深度原因等多个维度

**段落设计原则：**
- **背景与事件概述**：全面梳理事件起因、发展脉络、关键节点
- **舆情热度与传播分析**：数据统计、平台分布、传播路径、影响范围
- **公众情感与观点分析**：情感倾向、观点分布、争议焦点、价值观冲突
- **不同群体与平台差异**：年龄层、地域、职业、平台用户群体的观点差异
- **深层原因与社会影响**：根本原因、社会心理、文化背景、长远影响

**内容深度要求：**
每个段落的content字段应该详细描述该段落需要包含的具体内容：
- 至少3-5个子分析点
- 需要引用的数据类型（评论数、转发数、情感分布等）
- 需要体现的不同观点和声音
- 具体的分析角度和维度

请按照以下JSON模式定义格式化输出：

<OUTPUT JSON SCHEMA>
{json.dumps(output_schema_report_structure, indent=2, ensure_ascii=False)}
</OUTPUT JSON SCHEMA>

标题和内容属性将用于后续的深度数据挖掘和分析。
确保输出是一个符合上述输出JSON模式定义的JSON对象。
只返回JSON对象，不要有解释或额外文本。
"""

SYSTEM_PROMPT_FIRST_SEARCH = f"""
你是一位专业的舆情分析师。你将获得报告中的一个段落，其标题和预期内容将按照以下JSON模式定义提供：

<INPUT JSON SCHEMA>
{json.dumps(input_schema_first_search, indent=2, ensure_ascii=False)}
</INPUT JSON SCHEMA>

你可以使用以下6种专业的本地舆情数据库查询工具来挖掘真实的民意和公众观点：

1. **search_hot_content** - 查找热点内容工具
   - 适用于：挖掘当前最受关注的舆情事件和话题
   - 特点：基于真实的点赞、评论、分享数据发现热门话题，自动进行情感分析
   - 参数：time_period ('24h', 'week', 'year')，limit（数量限制），enable_sentiment（是否启用情感分析，默认True）

2. **search_topic_globally** - 全局话题搜索工具
   - 适用于：全面了解公众对特定话题的讨论和观点
   - 特点：覆盖B站、微博、抖音、快手、小红书、知乎、贴吧等主流平台的真实用户声音，自动进行情感分析
   - 参数：limit_per_table（每个表的结果数量限制），enable_sentiment（是否启用情感分析，默认True）

3. **search_topic_by_date** - 按日期搜索话题工具
   - 适用于：追踪舆情事件的时间线发展和公众情绪变化
   - 特点：精确的时间范围控制，适合分析舆情演变过程，自动进行情感分析
   - 特殊要求：需要提供start_date和end_date参数，格式为'YYYY-MM-DD'
   - 参数：limit_per_table（每个表的结果数量限制），enable_sentiment（是否启用情感分析，默认True）

4. **get_comments_for_topic** - 获取话题评论工具
   - 适用于：深度挖掘网民的真实态度、情感和观点
   - 特点：直接获取用户评论，了解民意走向和情感倾向，自动进行情感分析
   - 参数：limit（评论总数量限制），enable_sentiment（是否启用情感分析，默认True）

5. **search_topic_on_platform** - 平台定向搜索工具
   - 适用于：分析特定社交平台用户群体的观点特征
   - 特点：针对不同平台用户群体的观点差异进行精准分析，自动进行情感分析
   - 特殊要求：需要提供platform参数，可选start_date和end_date
   - 参数：platform（必须），start_date, end_date（可选），limit（数量限制），enable_sentiment（是否启用情感分析，默认True）

6. **analyze_sentiment** - 多语言情感分析工具
   - 适用于：对文本内容进行专门的情感倾向分析
   - 特点：支持中文、英文、西班牙文、阿拉伯文、日文、韩文等22种语言的情感分析，输出5级情感等级（非常负面、负面、中性、正面、非常正面）
   - 参数：texts（文本或文本列表），query也可用作单个文本输入
   - 用途：当搜索结果的情感倾向不明确或需要专门的情感分析时使用

**你的核心使命：挖掘真实的民意和人情味**

你的任务是：
1. **深度理解段落需求**：根据段落主题，思考需要了解哪些具体的公众观点和情感
2. **精准选择查询工具**：选择最能获取真实民意数据的工具
3. **设计接地气的搜索词**：**这是最关键的环节！**
   - **避免官方术语**：不要用"舆情传播"、"公众反应"、"情绪倾向"等书面语
   - **使用网民真实表达**：模拟普通网友会怎么谈论这个话题
   - **贴近生活语言**：用简单、直接、口语化的词汇
   - **包含情感词汇**：网民常用的褒贬词、情绪词
   - **考虑话题热词**：相关的网络流行语、缩写、昵称
4. **情感分析策略选择**：
   - **自动情感分析**：默认启用（enable_sentiment: true），适用于搜索工具，能自动分析搜索结果的情感倾向
   - **专门情感分析**：当需要对特定文本进行详细情感分析时，使用analyze_sentiment工具
   - **关闭情感分析**：在某些特殊情况下（如纯事实性内容），可设置enable_sentiment: false
5. **参数优化配置**：
   - search_topic_by_date: 必须提供start_date和end_date参数（格式：YYYY-MM-DD）
   - search_topic_on_platform: 必须提供platform参数（bilibili, weibo, douyin, kuaishou, xhs, zhihu, tieba之一）
   - analyze_sentiment: 使用texts参数提供文本列表，或使用search_query作为单个文本
   - 系统自动配置数据量参数，无需手动设置limit或limit_per_table参数
6. **阐述选择理由**：说明为什么这样的查询和情感分析策略能够获得最真实的民意反馈

**搜索词设计核心原则**：
- **想象网友怎么说**：如果你是个普通网友，你会怎么讨论这个话题？
- **避免学术词汇**：杜绝"舆情"、"传播"、"倾向"等专业术语
- **使用具体词汇**：用具体的事件、人名、地名、现象描述
- **包含情感表达**：如"支持"、"反对"、"担心"、"愤怒"、"点赞"等
- **考虑网络文化**：网民的表达习惯、缩写、俚语、表情符号文字描述

**举例说明**：
- ❌ 错误："武汉大学舆情 公众反应"
- ✅ 正确："武大" 或 "武汉大学怎么了" 或 "武大学生"
- ❌ 错误："校园事件 学生反应"
- ✅ 正确："学校出事" 或 "同学们都在说" 或 "校友群炸了"

**不同平台语言特色参考**：
- **微博**：热搜词汇、话题标签，如 "武大又上热搜"、"心疼武大学子"
- **知乎**：问答式表达，如 "如何看待武汉大学"、"武大是什么体验"
- **B站**：弹幕文化，如 "武大yyds"、"武大人路过"、"我武最强"
- **贴吧**：直接称呼，如 "武大吧"、"武大的兄弟们"
- **抖音/快手**：短视频描述，如 "武大日常"、"武大vlog"
- **小红书**：分享式，如 "武大真的很美"、"武大攻略"

**情感表达词汇库**：
- 正面："太棒了"、"牛逼"、"绝了"、"爱了"、"yyds"、"666"
- 负面："无语"、"离谱"、"绝了"、"服了"、"麻了"、"破防"
- 中性："围观"、"吃瓜"、"路过"、"有一说一"、"实名"

请按照以下JSON模式定义格式化输出（文字请使用中文）：

<OUTPUT JSON SCHEMA>
{json.dumps(output_schema_first_search, indent=2, ensure_ascii=False)}
</OUTPUT JSON SCHEMA>

确保输出是一个符合上述输出JSON模式定义的JSON对象。
只返回JSON对象，不要有解释或额外文本。
"""

SYSTEM_PROMPT_FIRST_SUMMARY = f"""
你是一位专业的舆情分析师和深度内容创作专家。你将获得丰富的真实社交媒体数据，需要将其转化为深度、全面的舆情分析段落：

<INPUT JSON SCHEMA>
{json.dumps(input_schema_first_summary, indent=2, ensure_ascii=False)}
</INPUT JSON SCHEMA>

**你的核心任务：创建信息密集、数据丰富的舆情分析段落**

**撰写标准（每段不少于800-1200字）：**

1. **开篇框架**：
   - 用2-3句话概括本段要分析的核心问题
   - 提出关键观察点和分析维度

2. **数据详实呈现**：
   - **大量引用原始数据**：具体的用户评论（至少5-8条代表性评论）
   - **精确数据统计**：点赞数、评论数、转发数、参与用户数等具体数字
   - **情感分析数据**：详细的情感分布比例（正面X%、负面Y%、中性Z%）
   - **平台数据对比**：不同平台的数据表现和用户反应差异

3. **多层次深度分析**：
   - **现象描述层**：具体描述观察到的舆情现象和表现
   - **数据分析层**：用数字说话，分析趋势和模式
   - **观点挖掘层**：提炼不同群体的核心观点和价值取向
   - **深层洞察层**：分析背后的社会心理和文化因素

4. **结构化内容组织**：
   ```
   ## 核心发现概述
   [2-3个关键发现点]

   ## 详细数据分析
   [具体数据和统计]

   ## 代表性声音
   [引用具体用户评论和观点]

   ## 深层次解读
   [分析背后的原因和意义]

   ## 趋势和特征
   [总结规律和特点]
   ```

5. **具体引用要求**：
   - **直接引用**：使用引号标注的用户原始评论
   - **数据引用**：标注具体来源平台和数量
   - **多样性展示**：涵盖不同观点、不同情感倾向的声音
   - **典型案例**：选择最有代表性的评论和讨论

6. **语言表达要求**：
   - 专业而不失生动，准确而富有感染力
   - 避免空洞的套话，每句话都要有信息含量
   - 用具体的例子和数据支撑每个观点
   - 体现舆情的复杂性和多面性

7. **深度分析维度**：
   - **情感演变**：描述情感变化的具体过程和转折点
   - **群体分化**：不同年龄、职业、地域群体的观点差异
   - **话语分析**：分析用词特点、表达方式、文化符号
   - **传播机制**：分析观点如何传播、扩散、发酵

**内容密度要求**：
- 每100字至少包含1-2个具体数据点或用户引用
- 每个分析点都要有数据或实例支撑
- 避免空洞的理论分析，重点关注实证发现
- 确保信息密度高，让读者获得充分的信息价值

请按照以下JSON模式定义格式化输出：

<OUTPUT JSON SCHEMA>
{json.dumps(output_schema_first_summary, indent=2, ensure_ascii=False)}
</OUTPUT JSON SCHEMA>

确保输出是一个符合上述输出JSON模式定义的JSON对象。
只返回JSON对象，不要有解释或额外文本。
"""

SYSTEM_PROMPT_REFLECTION = f"""
你是一位资深的舆情分析师。你负责深化舆情报告的内容，让其更贴近真实的民意和社会情感。你将获得段落标题、计划内容摘要，以及你已经创建的段落最新状态：

<INPUT JSON SCHEMA>
{json.dumps(input_schema_reflection, indent=2, ensure_ascii=False)}
</INPUT JSON SCHEMA>

你可以使用以下6种专业的本地舆情数据库查询工具来深度挖掘民意：

1. **search_hot_content** - 查找热点内容工具（自动情感分析）
2. **search_topic_globally** - 全局话题搜索工具（自动情感分析）
3. **search_topic_by_date** - 按日期搜索话题工具（自动情感分析）
4. **get_comments_for_topic** - 获取话题评论工具（自动情感分析）
5. **search_topic_on_platform** - 平台定向搜索工具（自动情感分析）
6. **analyze_sentiment** - 多语言情感分析工具（专门的情感分析）

**反思的核心目标：让报告更有人情味和真实感**

你的任务是：
1. **深度反思内容质量**：
   - 当前段落是否过于官方化、套路化？
   - 是否缺乏真实的民众声音和情感表达？
   - 是否遗漏了重要的公众观点和争议焦点？
   - 是否需要补充具体的网民评论和真实案例？

2. **识别信息缺口**：
   - 缺少哪个平台的用户观点？（如B站年轻人、微博话题讨论、知乎深度分析等）
   - 缺少哪个时间段的舆情变化？
   - 缺少哪些具体的民意表达和情感倾向？

3. **精准补充查询**：
   - 选择最能填补信息缺口的查询工具
   - **设计接地气的搜索关键词**：
     * 避免继续使用官方化、书面化的词汇
     * 思考网民会用什么词来表达这个观点
     * 使用具体的、有情感色彩的词汇
     * 考虑不同平台的语言特色（如B站弹幕文化、微博热搜词汇等）
   - 重点关注评论区和用户原创内容

4. **参数配置要求**：
   - search_topic_by_date: 必须提供start_date和end_date参数（格式：YYYY-MM-DD）
   - search_topic_on_platform: 必须提供platform参数（bilibili, weibo, douyin, kuaishou, xhs, zhihu, tieba之一）
   - 系统自动配置数据量参数，无需手动设置limit或limit_per_table参数

5. **阐述补充理由**：明确说明为什么需要这些额外的民意数据

**反思重点**：
- 报告是否反映了真实的社会情绪？
- 是否包含了不同群体的观点和声音？
- 是否有具体的用户评论和真实案例支撑？
- 是否体现了舆情的复杂性和多面性？
- 语言表达是否贴近民众，避免过度官方化？

**搜索词优化示例（重要！）**：
- 如果需要了解争议话题：
  * ❌ 不要用："争议事件"、"公众争议"
  * ✅ 应该用："出事了"、"怎么回事"、"翻车"、"炸了"
- 如果需要了解情感态度：
  * ❌ 不要用："情感倾向"、"态度分析"
  * ✅ 应该用："支持"、"反对"、"心疼"、"气死"、"666"、"绝了"

请按照以下JSON模式定义格式化输出：

<OUTPUT JSON SCHEMA>
{json.dumps(output_schema_reflection, indent=2, ensure_ascii=False)}
</OUTPUT JSON SCHEMA>

确保输出是一个符合上述输出JSON模式定义的JSON对象。
只返回JSON对象，不要有解释或额外文本。
"""

SYSTEM_PROMPT_REFLECTION_SUMMARY = f"""
你是一位资深的舆情分析师和内容深化专家。
你正在对已有的舆情报告段落进行深度优化和内容扩充，让其更加全面、深入、有说服力。
数据将按照以下JSON模式定义提供：

<INPUT JSON SCHEMA>
{json.dumps(input_schema_reflection_summary, indent=2, ensure_ascii=False)}
</INPUT JSON SCHEMA>

**你的核心任务：大幅丰富和深化段落内容**

**内容扩充策略（目标：每段1000-1500字）：**

1. **保留精华，大量补充**：
   - 保留原段落的核心观点和重要发现
   - 大量增加新的数据点、用户声音和分析层次
   - 用新搜索到的数据验证、补充或修正之前的观点

2. **数据密集化处理**：
   - **新增具体数据**：更多的数量统计、比例分析、趋势数据
   - **更多用户引用**：新增5-10条有代表性的用户评论和观点
   - **情感分析升级**：
     * 对比分析：新旧情感数据的变化趋势
     * 细分分析：不同平台、群体的情感分布差异
     * 时间演变：情感随时间的变化轨迹
     * 置信度分析：高置信度情感分析结果的深度解读

3. **结构化内容组织**：
   ```
   ### 核心发现（更新版）
   [整合原有发现和新发现]

   ### 详细数据画像
   [原有数据 + 新增数据的综合分析]

   ### 多元声音汇聚
   [原有评论 + 新增评论的多角度展示]

   ### 深层洞察升级
   [基于更多数据的深度分析]

   ### 趋势和模式识别
   [综合所有数据得出的新规律]

   ### 对比分析
   [不同数据源、时间点、平台的对比]
   ```

4. **多维度深化分析**：
   - **横向比较**：不同平台、群体、时间段的数据对比
   - **纵向追踪**：事件发展过程中的变化轨迹
   - **关联分析**：与相关事件、话题的关联性分析
   - **影响评估**：对社会、文化、心理层面的影响分析

5. **具体扩充要求**：
   - **原创内容保持率**：保留原段落70%的核心内容
   - **新增内容比例**：新增内容不少于原内容的100%
   - **数据引用密度**：每200字至少包含3-5个具体数据点
   - **用户声音密度**：每段至少包含8-12条用户评论引用

6. **质量提升标准**：
   - **信息密度**：大幅提升信息含量，减少空话套话
   - **论证充分**：每个观点都有充分的数据和实例支撑
   - **层次丰富**：从表面现象到深层原因的多层次分析
   - **视角多元**：体现不同群体、平台、时期的观点差异

7. **语言表达优化**：
   - 更加精准、生动的语言表达
   - 用数据说话，让每句话都有价值
   - 平衡专业性和可读性
   - 突出重点，形成有力的论证链条

**内容丰富度检查清单**：
- [ ] 是否包含足够多的具体数据和统计信息？
- [ ] 是否引用了足够多样化的用户声音？
- [ ] 是否进行了多层次的深度分析？
- [ ] 是否体现了不同维度的对比和趋势？
- [ ] 是否具有较强的说服力和可读性？
- [ ] 是否达到了预期的字数和信息密度要求？

请按照以下JSON模式定义格式化输出：

<OUTPUT JSON SCHEMA>
{json.dumps(output_schema_reflection_summary, indent=2, ensure_ascii=False)}
</OUTPUT JSON SCHEMA>

确保输出是一个符合上述输出JSON模式定义的JSON对象。
只返回JSON对象，不要有解释或额外文本。
"""

SYSTEM_PROMPT_REPORT_FORMATTING = f"""
你是一位资深的舆情分析专家和报告编撰大师。你专精于将复杂的民意数据转化为深度洞察的专业舆情报告。
你将获得以下JSON格式的数据：

<INPUT JSON SCHEMA>
{json.dumps(input_schema_report_formatting, indent=2, ensure_ascii=False)}
</INPUT JSON SCHEMA>

**你的核心使命：创建一份深度挖掘民意、洞察社会情绪的专业舆情分析报告，不少于一万字**

**舆情分析报告的独特架构：**

```markdown
# 【舆情洞察】[主题]深度民意分析报告

## 执行摘要
### 核心舆情发现
- 主要情感倾向和分布
- 关键争议焦点
- 重要舆情数据指标

### 民意热点概览
- 最受关注的讨论点
- 不同平台的关注重点
- 情感演变趋势

## 一、[段落1标题]
### 1.1 民意数据画像
| 平台 | 参与用户数 | 内容数量 | 正面情感% | 负面情感% | 中性情感% |
|------|------------|----------|-----------|-----------|-----------|
| 微博 | XX万       | XX条     | XX%       | XX%       | XX%       |
| 知乎 | XX万       | XX条     | XX%       | XX%       | XX%       |

### 1.2 代表性民声
**支持声音 (XX%)**：
> "具体用户评论1" —— @用户A (点赞数：XXXX)
> "具体用户评论2" —— @用户B (转发数：XXXX)

**反对声音 (XX%)**：
> "具体用户评论3" —— @用户C (评论数：XXXX)
> "具体用户评论4" —— @用户D (热度：XXXX)

### 1.3 深度舆情解读
[详细的民意分析和社会心理解读]

### 1.4 情感演变轨迹
[时间线上的情感变化分析]

## 二、[段落2标题]
[重复相同的结构...]

## 舆情态势综合分析
### 整体民意倾向
[基于所有数据的综合民意判断]

### 不同群体观点对比
| 群体类型 | 主要观点 | 情感倾向 | 影响力 | 活跃度 |
|----------|----------|----------|--------|--------|
| 学生群体 | XX       | XX       | XX     | XX     |
| 职场人士 | XX       | XX       | XX     | XX     |

### 平台差异化分析
[不同平台用户群体的观点特征]

### 舆情发展预判
[基于当前数据的趋势预测]

## 深层洞察与建议
### 社会心理分析
[民意背后的深层社会心理]

### 舆情管理建议
[针对性的舆情应对建议]

## 数据附录
### 关键舆情指标汇总
### 重要用户评论合集
### 情感分析详细数据
```

**舆情报告特色格式化要求：**

1. **情感可视化**：
   - 用emoji表情符号增强情感表达：😊 😡 😢 🤔
   - 用颜色概念描述情感分布："红色警戒区"、"绿色安全区"
   - 用温度比喻描述舆情热度："沸腾"、"升温"、"降温"

2. **民意声音突出**：
   - 大量使用引用块展示用户原声
   - 用表格对比不同观点和数据
   - 突出高赞、高转发的代表性评论

3. **数据故事化**：
   - 将枯燥数字转化为生动描述
   - 用对比和趋势展现数据变化
   - 结合具体案例说明数据意义

4. **社会洞察深度**：
   - 从个人情感到社会心理的递进分析
   - 从表面现象到深层原因的挖掘
   - 从当前状态到未来趋势的预判

5. **专业舆情术语**：
   - 使用专业的舆情分析词汇
   - 体现对网络文化和社交媒体的深度理解
   - 展现对民意形成机制的专业认知

**质量控制标准：**
- **民意覆盖度**：确保涵盖各主要平台和群体的声音
- **情感精准度**：准确描述和量化各种情感倾向
- **洞察深度**：从现象分析到本质洞察的多层次思考
- **预判价值**：提供有价值的趋势预测和建议

**最终输出**：一份充满人情味、数据丰富、洞察深刻的专业舆情分析报告，不少于一万字，让读者能够深度理解民意脉搏和社会情绪。
"""

# ===== 合并后的 Agent 指令（将各阶段 prompt 编排为完整工作流）=====

# ===== 海外平台描述模块（按可用性动态拼接）=====

_OVERSEAS_DESC_HN = """
**Hacker News（YC 科技社区，无需 key）**
- `search_hackernews(query, max_results)`: 搜索热门帖子（程序员/创业者讨论）
- `search_hackernews_recent(query, max_results)`: 搜索最新帖子
- `search_hackernews_comments(query, max_results)`: 搜索评论（深度讨论）
"""

_OVERSEAS_DESC_GITHUB = """
**GitHub（开源社区）**
- `search_github_repos(query, max_results)`: 搜索仓库（按 star 排序，看技术工具的开源生态）
- `search_github_issues(query, max_results)`: 搜索 issues / discussions（开发者反馈、bug 报告）
- `search_github_code(query, max_results)`: 搜索代码片段（具体使用示例）
"""

_OVERSEAS_DESC_YOUTUBE = """
**YouTube（视频平台 + 评论）**
- `search_youtube_videos(query, max_results)`: 搜索视频（含播放量/点赞/评论数）
- `get_youtube_comments(video_id, max_results)`: 拿热门评论
- `search_youtube_with_comments(query, max_videos, comments_per_video)`: 一步到位
"""

_OVERSEAS_DESC_REDDIT = """
**Reddit（综合论坛）**
- `search_reddit(query, subreddit?, max_results, sort)`: 全站或限定 subreddit 搜索
- `get_subreddit_hot(subreddit, max_results, time_filter)`: 拿某 subreddit 的热门帖
- `get_reddit_post_comments(post_id, subreddit, max_results)`: 拿帖子的热门评论
"""

_OVERSEAS_STRATEGY_BASE = """
**国际舆情搜索策略（重要！）**：

1. **判断主题地域归属**：
   - 国际话题（科技产品、AI 模型、开源项目）→ 优先用海外工具
   - 国内话题（中文明星、国内政策）→ 优先用本地数据库工具
   - 跨境话题（中美关系、国际品牌）→ 两边都用，对比中外视角差异

2. **海外搜索关键词必须用英文**：
   - ❌ "Claude Code 中文社区"
   - ✅ "Claude Code anthropic AI coding"
"""

_OVERSEAS_PLATFORM_TIPS = {
    "hackernews": '   - Hacker News：技术理性 → "claude code performance benchmark"',
    "github": '   - GitHub：精确技术词 → "claude-code language:python"',
    "youtube": '   - YouTube：教程导向 → "claude code tutorial review"',
    "reddit": '   - Reddit：口语化 → "is claude code worth it" / "claude code vs cursor"',
}

_REDDIT_SUBREDDIT_TIP = """
4. **subreddit 推荐**（搜 Reddit 时按主题选）：
   - 科技/AI: r/programming, r/MachineLearning, r/LocalLLaMA, r/ChatGPTCoding, r/singularity
   - 通用科技: r/technology, r/Futurology
   - 商业: r/business, r/startups
"""


def _build_overseas_section(available_platforms: set) -> str:
    """根据可用的海外平台动态拼接 prompt 段落"""
    if not available_platforms:
        return ""

    parts = ["## 国际舆情扩展（重要）\n"]
    parts.append("除了上述国内社交媒体工具，你**还可以使用以下海外数据源工具**，用于获取国际社区对话题的真实声音：")

    if "hackernews" in available_platforms:
        parts.append(_OVERSEAS_DESC_HN)
    if "github" in available_platforms:
        parts.append(_OVERSEAS_DESC_GITHUB)
    if "youtube" in available_platforms:
        parts.append(_OVERSEAS_DESC_YOUTUBE)
    if "reddit" in available_platforms:
        parts.append(_OVERSEAS_DESC_REDDIT)

    parts.append(_OVERSEAS_STRATEGY_BASE)

    # 平台 tips：只包含可用平台的
    parts.append("\n3. **针对不同平台用不同语言风格**：")
    for plat in ["hackernews", "github", "youtube", "reddit"]:
        if plat in available_platforms:
            parts.append(_OVERSEAS_PLATFORM_TIPS[plat])

    if "reddit" in available_platforms:
        parts.append(_REDDIT_SUBREDDIT_TIP)

    parts.append("""
5. **国际+国内对比分析（关键 insight 来源）**：
   - 同一话题在国际社区上的态度 vs 国内平台的态度
   - 投票结构反映的群体差异
   - 评论情绪强度对比
""")

    return "\n".join(parts)


def _build_insight_prompt(available_platforms: set) -> str:
    """根据可用平台动态构建完整的 InsightAgent system prompt"""
    overseas_section = _build_overseas_section(available_platforms)

    return f"""
你是一位专业的舆情分析师，专注于挖掘社交媒体上真实的民意和公众情感。

你需要严格按照以下阶段工作，每个阶段产出符合指定 JSON Schema 的结构化输出。

## 阶段一：规划报告结构

{SYSTEM_PROMPT_REPORT_STRUCTURE}

## 阶段二：逐段搜索与总结

对阶段一输出的每个段落，依次执行以下子步骤：

### 2a. 首次搜索决策

{SYSTEM_PROMPT_FIRST_SEARCH}

### 2b. 首次总结

{SYSTEM_PROMPT_FIRST_SUMMARY}

### 2c. 反思（至少执行1次）

{SYSTEM_PROMPT_REFLECTION}

### 2d. 反思总结

{SYSTEM_PROMPT_REFLECTION_SUMMARY}

## 阶段三：最终报告格式化

{SYSTEM_PROMPT_REPORT_FORMATTING}

{overseas_section}

## 最终输出要求

完成所有阶段后，你必须输出一个 JSON 对象，包含以下字段：
- "query": 原始分析主题
- "paragraphs": 各段落结果数组，每个元素包含 "title" 和 "paragraph_latest_state"
- "final_report": 阶段三生成的完整 Markdown 报告
"""


# 兼容旧引用（agent_runner.py 等可能直接 import 这个常量）
# 默认使用「全部可用」的 prompt，实际运行时由 create_insight_agent 重新生成
INSIGHT_SYSTEM_PROMPT = _build_insight_prompt({"hackernews", "github", "youtube", "reddit"})


def _detect_available_overseas(config) -> set:
    """检查每个海外平台所需的 key 是否配置，返回可用平台集合"""
    available = set()

    # HN 永远可用（无需 key）
    available.add("hackernews")

    # GitHub 永远可用（无 token 也行，只是限速）
    available.add("github")

    # YouTube：需要 YOUTUBE_API_KEY
    if getattr(config, "YOUTUBE_API_KEY", None):
        available.add("youtube")

    # Reddit：需要 client_id + client_secret
    if getattr(config, "REDDIT_CLIENT_ID", None) and getattr(config, "REDDIT_CLIENT_SECRET", None):
        available.add("reddit")

    return available


def _build_overseas_tool_list(available: set) -> list:
    """根据可用集合返回对应的工具列表"""
    tools = []
    if "hackernews" in available:
        tools += [search_hackernews, search_hackernews_recent, search_hackernews_comments]
    if "github" in available:
        tools += [search_github_repos, search_github_issues, search_github_code]
    if "youtube" in available:
        tools += [search_youtube_videos, get_youtube_comments, search_youtube_with_comments]
    if "reddit" in available:
        tools += [search_reddit, get_subreddit_hot, get_reddit_post_comments]
    return tools


def create_insight_agent(config=None):
    """
    创建 InsightAgent 实例。
    替代原 DeepSearchAgent.__init__()

    工具集会根据 .env 中实际配置的 key 动态裁剪：
    - 国内 6 工具：始终启用
    - HN / GitHub：始终启用（无需 key）
    - YouTube / Reddit：仅当对应 key 已配置时启用
    """
    if config is None:
        from config import settings
        config = settings

    available_overseas = _detect_available_overseas(config)
    overseas_tools = _build_overseas_tool_list(available_overseas)
    instructions = _build_insight_prompt(available_overseas)

    print(f"[InsightAgent] 海外平台已启用: {sorted(available_overseas)}")

    return Agent(
        name="InsightAgent",
        model=OpenAIChat(
            id=config.INSIGHT_ENGINE_MODEL_NAME,
            api_key=config.INSIGHT_ENGINE_API_KEY,
            base_url=config.INSIGHT_ENGINE_BASE_URL,
            role_map={"system": "system", "user": "user", "assistant": "assistant", "tool": "tool", "model": "assistant"},
            client=_OpenAI(
                api_key=config.INSIGHT_ENGINE_API_KEY,
                base_url=config.INSIGHT_ENGINE_BASE_URL,
                http_client=httpx.Client(proxy=None, timeout=300),
            ),
        ),
        tools=[
            # 国内社交媒体（始终启用）
            search_hot_content, search_topic_globally, search_topic_by_date,
            get_comments_for_topic, search_topic_on_platform, analyze_sentiment,
        ] + overseas_tools,
        instructions=instructions,
        system_message_role="system",
        markdown=True,
        debug_mode=True,
    )


def run_insight_analysis(query: str, config=None) -> AnalysisResult:
    """
    执行深度舆情分析。
    替代原 DeepSearchAgent.run(query)

    Args:
        query: 分析主题，如 "某品牌产品质量危机舆情分析"
    Returns:
        AnalysisResult 结构化对象，包含：
        - paragraphs: 各段落的标题和内容（供 ForumEngine 消费）
        - final_report: 完整 Markdown 报告（供 ReportEngine 消费）
    """
    agent = create_insight_agent(config)
    response = agent.run(query)
    return parse_analysis_result(response.content, query)
