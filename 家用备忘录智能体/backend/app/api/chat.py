# -*- coding: utf-8 -*-
"""
自然语言对话入口（核心接口）。

接收用户自然语言输入，经 LLM 意图识别后分发到对应服务执行。
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.family import FamilyMember
from app.models.memo import MemoItem
from app.core.deps import get_current_member
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.nlu import parse_message
from app.services.time_parser import resolve_time

router = APIRouter()

# 对话上下文缓存（简单内存实现，生产环境用 Redis）
_chat_context: dict[str, dict] = {}


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """
    核心对话接口。
    接收用户自然语言输入，解析意图并执行。
    """
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="消息不能为空")

    # 获取对话上下文
    context = _chat_context.get(member.id, {})
    context["member_id"] = member.id
    context["family_id"] = member.family_id
    context["role"] = member.role

    # 1. NLU 意图识别
    nlu_result = await parse_message(message, context)
    intent = nlu_result.get("intent", "chat")
    slots = nlu_result.get("slots", {})
    reply = nlu_result.get("reply", "收到")
    need_confirm = nlu_result.get("need_confirm", False)

    # 2. 时间解析（如果有时间表达式）
    raw_time = slots.get("raw_time", "")
    resolved_time = slots.get("resolved_time", "")
    if raw_time and not resolved_time:
        resolved, confidence = await resolve_time(raw_time, context)
        if resolved and confidence > 0.5:
            slots["resolved_time"] = resolved
            slots["time_confidence"] = confidence
        elif raw_time:
            need_confirm = True

    # 3. 执行意图
    data = None
    try:
        if intent == "create_memo" and member.family_id:
            data = await _execute_create_memo(db, member, slots)
            if data:
                reply = f"已为你创建提醒：{data.get('due_time', '')} {slots.get('content', '')}"
                # 更新上下文
                context["last_memo_id"] = data.get("id")
                context["last_intent"] = "create_memo"

        elif intent == "query_memo" and member.family_id:
            memos = await _execute_query_memo(db, member, slots)
            if memos:
                count = len(memos)
                reply = f"你有 {count} 条待办事项"
                data = memos
            else:
                reply = "当前没有待办事项"

        elif intent == "mark_done" and member.family_id:
            memo_id = context.get("last_memo_id")
            if memo_id:
                await _execute_mark_done(db, member, memo_id)
                reply = "已标记完成！"
            else:
                reply = "请告诉我哪一条已完成"

        elif intent == "update_memo" and member.family_id:
            memo_id = context.get("last_memo_id")
            if memo_id:
                data = await _execute_update_memo(db, member, memo_id, slots)
                if data:
                    reply = f"已更新：{data.get('content', '')} {data.get('due_time', '')}"
                else:
                    reply = "没有找到要修改的备忘"
            else:
                reply = "请告诉我修改哪一条"

        elif intent == "delete_memo" and member.family_id:
            memo_id = context.get("last_memo_id")
            if memo_id:
                await _execute_delete_memo(db, member, memo_id)
                reply = "已删除！"
            else:
                reply = "请告诉我删除哪一条"

        elif intent == "create_shopping" and member.family_id:
            data = {"content": slots.get("content", message), "category": "shopping"}
            reply = "好的，已添加到购物清单。"

        elif intent == "add_vehicle_expense" and member.family_id:
            reply = "好的，已记录用车支出。"

        elif intent == "add_anniversary" and member.family_id:
            reply = "好的，已记录纪念日提醒。"

        elif intent in ("chat",):
            # 闲聊，不需要操作
            pass

        else:
            if not member.family_id:
                reply = "请先创建或加入家庭空间后再使用。"

    except Exception as e:
        from loguru import logger
        logger.error(f"执行意图失败: {e}")
        reply = "处理时出了点问题，请稍后重试。"
        need_confirm = True

    # 保存上下文
    _chat_context[member.id] = context

    return ChatResponse(
        intent=intent,
        reply=reply,
        data=data,
        need_confirm=need_confirm,
    )


async def _execute_create_memo(db: AsyncSession, member: FamilyMember, slots: dict) -> dict:
    """创建备忘条目"""
    import json
    from app.models.memo import MemoItem

    content = slots.get("content", "")
    resolved_time_str = slots.get("resolved_time", "")
    due_time = None
    if resolved_time_str:
        try:
            due_time = datetime.fromisoformat(resolved_time_str)
        except ValueError:
            pass

    repeat_rule = slots.get("repeat")
    if repeat_rule and isinstance(repeat_rule, str):
        try:
            repeat_rule = json.loads(repeat_rule)
        except json.JSONDecodeError:
            repeat_rule = None

    assignee_id = member.id
    if slots.get("assignee") == "partner":
        # 查找配偶
        from sqlalchemy import select
        from app.models.family import FamilyMember
        result = await db.execute(
            select(FamilyMember).where(
                FamilyMember.family_id == member.family_id,
                FamilyMember.id != member.id,
            )
        )
        partner = result.scalar_one_or_none()
        if partner:
            assignee_id = partner.id

    memo = MemoItem(
        family_id=member.family_id,
        content=content,
        category=slots.get("category", "other"),
        due_time=due_time,
        repeat_rule=repeat_rule,
        assignee_id=assignee_id,
        creator_id=member.id,
        source_type="chat",
    )
    db.add(memo)
    await db.flush()

    return {
        "id": memo.id,
        "content": memo.content,
        "due_time": due_time.strftime("%m月%d日 %H:%M") if due_time else "待确认",
        "category": memo.category,
    }


async def _execute_query_memo(db: AsyncSession, member: FamilyMember, slots: dict) -> list:
    """查询待办"""
    from app.models.memo import MemoItem

    query = select(MemoItem).where(
        MemoItem.family_id == member.family_id,
        MemoItem.status == "pending",
    )
    result = await db.execute(query.order_by(MemoItem.due_time.asc()))
    memos = result.scalars().all()

    return [
        {
            "id": m.id,
            "content": m.content,
            "due_time": m.due_time.strftime("%m月%d日 %H:%M") if m.due_time else "待确认",
            "category": m.category,
        }
        for m in memos
    ]


async def _execute_mark_done(db: AsyncSession, member: FamilyMember, memo_id: str):
    """标记完成"""
    from app.models.memo import MemoItem

    result = await db.execute(
        select(MemoItem).where(
            MemoItem.id == memo_id,
            MemoItem.family_id == member.family_id,
        )
    )
    memo = result.scalar_one_or_none()
    if memo:
        memo.status = "done"


async def _execute_update_memo(db: AsyncSession, member: FamilyMember, memo_id: str, slots: dict) -> dict | None:
    """修改备忘（多轮对话场景四）"""
    from app.models.memo import MemoItem

    result = await db.execute(
        select(MemoItem).where(
            MemoItem.id == memo_id,
            MemoItem.family_id == member.family_id,
        )
    )
    memo = result.scalar_one_or_none()
    if not memo:
        return None

    # 更新内容
    new_content = slots.get("content", "")
    if new_content:
        memo.content = new_content

    # 更新时间
    resolved_time_str = slots.get("resolved_time", "")
    if resolved_time_str:
        try:
            memo.due_time = datetime.fromisoformat(resolved_time_str)
        except ValueError:
            pass

    return {
        "id": memo.id,
        "content": memo.content,
        "due_time": memo.due_time.strftime("%m月%d日 %H:%M") if memo.due_time else "待确认",
    }


async def _execute_delete_memo(db: AsyncSession, member: FamilyMember, memo_id: str):
    """删除备忘"""
    from app.models.memo import MemoItem

    result = await db.execute(
        select(MemoItem).where(
            MemoItem.id == memo_id,
            MemoItem.family_id == member.family_id,
        )
    )
    memo = result.scalar_one_or_none()
    if memo:
        memo.status = "cancelled"


@router.get("/history")
async def get_chat_history(
    member: FamilyMember = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
):
    """获取对话历史（最近50条）"""
    # TODO: 从对话历史表查询
    return {"history": []}