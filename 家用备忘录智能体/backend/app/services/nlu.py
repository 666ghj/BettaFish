# -*- coding: utf-8 -*-
"""
NLU 自然语言理解服务。

使用 LLM 进行意图识别和槽位抽取，输出结构化 JSON。
"""
import json
from typing import Optional
from openai import AsyncOpenAI
from loguru import logger

from app.config import settings

# LLM 客户端
_client: Optional[AsyncOpenAI] = None


def get_llm_client() -> AsyncOpenAI:
    """获取 LLM 客户端（懒加载）"""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
        )
    return _client


# 系统提示词：定义意图和槽位
SYSTEM_PROMPT = """你是一个家庭备忘录智能体的自然语言理解引擎。你的任务是将用户的自然语言输入解析为结构化的意图和槽位。

## 支持的意图 (intent)

| 意图 | 说明 | 示例 |
|------|------|------|
| create_memo | 创建备忘/提醒 | "下周三交电费"、"明天下午三点接孩子" |
| query_memo | 查询待办 | "我这个月有哪些待办"、"周末有什么安排" |
| update_memo | 修改备忘 | "把那条改到晚上八点" |
| delete_memo | 删除备忘 | "删掉刚才那条" |
| mark_done | 标记完成 | "电费已经交了" |
| create_shopping | 添加购物清单 | "买一箱牛奶"、"加个拖把到购物清单" |
| agree_shopping | 同意/不同意购买 | "牛奶可以买"、"那个太贵了先不买" |
| query_finance | 查收支 | "这月花了多少钱"、"上个月买菜花了多少" |
| add_vehicle_expense | 记录用车支出 | "今天加油花了300" |
| query_vehicle | 查车辆信息 | "车险什么时候到期" |
| add_anniversary | 添加纪念日 | "记一下结婚纪念日是9月15号" |
| query_anniversary | 查纪念日 | "我生日是什么时候" |
| chat | 闲聊/问候 | "谢谢"、"早上好" |

## 输出 JSON 格式

```json
{
    "intent": "意图名称",
    "slots": {
        "content": "备忘内容（不含时间信息）",
        "raw_time": "用户原文中的时间表达",
        "resolved_time": "解析后的ISO时间(如无法确定则填空字符串)",
        "time_confidence": 0.0-1.0,
        "assignee": "负责人: self/partner/空",
        "repeat": "重复规则: 如 {\"type\":\"monthly\",\"day\":15} 或 null",
        "category": "分类: financial/shopping/vehicle/health/anniversary/other"
    },
    "need_confirm": false,
    "reply": "给用户的自然语言回复（中文，简短友好）"
}
```

## 规则
1. 如果时间表达不明确（如"改天"、"有空的时候"），设置 need_confirm=true
2. 如果用户没有指定负责人，默认 assignee="self"
3. 仅当用户明确提到"提醒老公/老婆"时，才设置 assignee 为 partner
4. 回复要简短（不超过50字），口语化，像家人之间的对话
5. 对于闲聊（打招呼、感谢等），intent 设为 chat，不需要解析槽位"""


async def parse_message(message: str, context: Optional[dict] = None) -> dict:
    """
    解析用户消息，返回结构化意图。

    Args:
        message: 用户输入的自然语言消息
        context: 对话上下文（可选），包含最近操作等信息

    Returns:
        结构化意图结果字典
    """
    # 如果 LLM 未配置，使用关键词 fallback
    if not settings.LLM_API_KEY:
        logger.warning("LLM 未配置，使用关键词 fallback")
        return _keyword_fallback(message)

    try:
        client = get_llm_client()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

        # 如果有上下文，加入
        if context:
            context_str = json.dumps(context, ensure_ascii=False)
            messages.append({
                "role": "system",
                "content": f"对话上下文（最近一条操作）：{context_str}"
            })

        messages.append({"role": "user", "content": message})

        response = await client.chat.completions.create(
            model=settings.LLM_MODEL_NAME,
            messages=messages,
            temperature=0.1,
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        result_text = response.choices[0].message.content
        result = json.loads(result_text)

        # 验证必要字段
        if "intent" not in result:
            result["intent"] = "chat"
        if "slots" not in result:
            result["slots"] = {}
        if "reply" not in result:
            result["reply"] = "好的，已收到。"
        if "need_confirm" not in result:
            result["need_confirm"] = False

        logger.info(f"NLU 解析结果: {result.get('intent')} | 置信度: {result.get('slots', {}).get('time_confidence', 'N/A')}")
        return result

    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        return _keyword_fallback(message)


def _keyword_fallback(message: str) -> dict:
    """
    关键词匹配 fallback。
    当 LLM 不可用时使用，仅覆盖基础场景。
    """
    msg = message.lower()

    # 创建备忘
    if any(kw in msg for kw in ["提醒", "记得", "交"]):
        return {
            "intent": "create_memo",
            "slots": {
                "content": message,
                "raw_time": "",
                "resolved_time": "",
                "time_confidence": 0.0,
                "assignee": "self",
                "repeat": None,
                "category": "other",
            },
            "need_confirm": True,
            "reply": "好的，已记下了。请确认具体时间和内容。",
        }

    # 购物
    if any(kw in msg for kw in ["买", "购物"]):
        return {
            "intent": "create_shopping",
            "slots": {"content": message, "category": "shopping"},
            "need_confirm": True,
            "reply": "好的，已添加到购物清单。",
        }

    # 查询
    if any(kw in msg for kw in ["查", "看", "有哪", "什么"]):
        return {
            "intent": "query_memo",
            "slots": {},
            "need_confirm": False,
            "reply": "好的，帮你查一下。",
        }

    # 修改
    if any(kw in msg for kw in ["改到", "改成", "修改", "换个"]):
        return {
            "intent": "update_memo",
            "slots": {"content": message},
            "need_confirm": True,
            "reply": "好的，已帮你修改。",
        }

    # 删除
    if any(kw in msg for kw in ["删", "取消", "不要"]):
        return {
            "intent": "delete_memo",
            "slots": {},
            "need_confirm": True,
            "reply": "好的，已删除。",
        }

    # 完成
    if any(kw in msg for kw in ["交了", "做了", "完了", "好了"]):
        return {
            "intent": "mark_done",
            "slots": {},
            "need_confirm": True,
            "reply": "好的，已标记完成。",
        }

    # 车辆
    if any(kw in msg for kw in ["加油", "充电", "车险", "违章"]):
        return {
            "intent": "add_vehicle_expense",
            "slots": {"content": message, "category": "vehicle"},
            "need_confirm": True,
            "reply": "好的，已记录用车支出。",
        }

    # 纪念日
    if any(kw in msg for kw in ["纪念日", "生日"]):
        return {
            "intent": "add_anniversary",
            "slots": {"content": message, "category": "anniversary"},
            "need_confirm": True,
            "reply": "好的，已记录纪念日。",
        }

    # 默认：闲聊
    return {
        "intent": "chat",
        "slots": {},
        "need_confirm": False,
        "reply": "收到！有什么需要帮忙的吗？",
    }