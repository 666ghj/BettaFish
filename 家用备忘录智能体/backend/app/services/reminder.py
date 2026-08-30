# -*- coding: utf-8 -*-
"""
提醒调度服务。

基于 Redis 的延迟队列实现，后台 worker 轮询到期任务并推送通知。
"""
import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from loguru import logger
import redis.asyncio as aioredis

from app.config import settings


class ReminderService:
    """
    提醒调度服务。

    使用 Redis zset 管理定时任务：
    - key: reminder:{family_id}
    - score: 下次提醒时间戳（秒）
    - value: JSON 格式的任务信息
    """

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

    async def get_redis(self) -> aioredis.Redis:
        """获取 Redis 客户端（懒加载）"""
        if self._redis is None:
            self._redis = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
            )
        return self._redis

    async def schedule(self, memo_id: str, family_id: str, due_time: datetime,
                       repeat_rule: Optional[dict] = None) -> bool:
        """
        安排一个提醒任务。

        Args:
            memo_id: 备忘条目 ID
            family_id: 家庭空间 ID
            due_time: 到期时间
            repeat_rule: 重复规则，如 {"type": "monthly", "day": 15}

        Returns:
            是否成功
        """
        try:
            redis = await self.get_redis()
            key = f"reminder:{family_id}"

            task = {
                "memo_id": memo_id,
                "family_id": family_id,
                "due_time": due_time.isoformat(),
                "repeat_rule": repeat_rule,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "overdue_count": 0,
            }

            score = due_time.timestamp()
            await redis.zadd(key, {json.dumps(task, ensure_ascii=False): score})
            logger.info(f"提醒已安排: {memo_id} -> {due_time.isoformat()}")
            return True
        except Exception as e:
            logger.error(f"安排提醒失败: {e}")
            return False

    async def cancel(self, memo_id: str, family_id: str) -> bool:
        """取消提醒"""
        try:
            redis = await self.get_redis()
            key = f"reminder:{family_id}"

            # 查找并删除匹配的任务
            tasks = await redis.zrange(key, 0, -1)
            for task_json in tasks:
                task = json.loads(task_json)
                if task.get("memo_id") == memo_id:
                    await redis.zrem(key, task_json)
                    logger.info(f"提醒已取消: {memo_id}")
                    return True
            return False
        except Exception as e:
            logger.error(f"取消提醒失败: {e}")
            return False

    async def mark_overdue(self, memo_id: str, family_id: str) -> Optional[int]:
        """标记逾期，返回逾期次数"""
        try:
            redis = await self.get_redis()
            key = f"reminder:{family_id}"

            tasks = await redis.zrange(key, 0, -1)
            for task_json in tasks:
                task = json.loads(task_json)
                if task.get("memo_id") == memo_id:
                    task["overdue_count"] = task.get("overdue_count", 0) + 1
                    # 重新入队，下次提醒时间 = 当前时间 + 24小时
                    new_due = datetime.now(timezone.utc) + timedelta(hours=24)
                    task["due_time"] = new_due.isoformat()
                    await redis.zrem(key, task_json)
                    await redis.zadd(key, {json.dumps(task, ensure_ascii=False): new_due.timestamp()})
                    return task["overdue_count"]
            return None
        except Exception as e:
            logger.error(f"标记逾期失败: {e}")
            return None

    async def get_due_tasks(self, family_id: str, batch_size: int = 50) -> list[dict]:
        """获取到期的任务"""
        try:
            redis = await self.get_redis()
            key = f"reminder:{family_id}"
            now = datetime.now(timezone.utc).timestamp()

            tasks = await redis.zrangebyscore(key, 0, now, start=0, num=batch_size)
            result = []
            for task_json in tasks:
                try:
                    task = json.loads(task_json)
                    result.append(task)
                except json.JSONDecodeError:
                    continue

            # 移除已到期的任务
            if result:
                await redis.zremrangebyscore(key, 0, now)

            return result
        except Exception as e:
            logger.error(f"获取到期任务失败: {e}")
            return []

    async def get_upcoming(self, family_id: str, limit: int = 20) -> list[dict]:
        """获取即将到来的提醒"""
        try:
            redis = await self.get_redis()
            key = f"reminder:{family_id}"
            now = datetime.now(timezone.utc).timestamp()

            tasks = await redis.zrangebyscore(key, now, "+inf", start=0, num=limit)
            result = []
            for task_json in tasks:
                try:
                    task = json.loads(task_json)
                    due = datetime.fromisoformat(task["due_time"])
                    task["due_time_display"] = due.strftime("%m月%d日 %H:%M")
                    task["remaining_seconds"] = int(due.timestamp() - now)
                    result.append(task)
                except (json.JSONDecodeError, ValueError):
                    continue
            return result
        except Exception as e:
            logger.error(f"获取即将到来的提醒失败: {e}")
            return []

    async def start_worker(self):
        """启动后台 worker，持续轮询到期任务"""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("提醒调度 worker 已启动")

    async def stop_worker(self):
        """停止后台 worker"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("提醒调度 worker 已停止")

    async def _worker_loop(self):
        """Worker 主循环"""
        while self._running:
            try:
                # 轮询所有家庭空间的到期任务
                # TODO: 优化为按家庭空间遍历
                redis = await self.get_redis()

                # 获取所有 reminder key
                cursor = 0
                while True:
                    cursor, keys = await redis.scan(cursor, match="reminder:*", count=100)
                    for key in keys:
                        tasks = await self._process_family_tasks(key)
                        for task in tasks:
                            await self._push_notification(task)

                    if cursor == 0:
                        break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker 轮询异常: {e}")

            # 轮询间隔
            await asyncio.sleep(settings.REMINDER_POLL_INTERVAL)

    async def _process_family_tasks(self, key: str) -> list[dict]:
        """处理单个家庭空间的到期任务"""
        try:
            redis = await self.get_redis()
            now = datetime.now(timezone.utc).timestamp()

            tasks = await redis.zrangebyscore(key, 0, now)
            if not tasks:
                return []

            # 移除到期任务
            await redis.zremrangebyscore(key, 0, now)

            result = []
            for task_json in tasks:
                try:
                    task = json.loads(task_json)
                    # 如果有重复规则，重新安排
                    if task.get("repeat_rule"):
                        new_due = self._calc_next_repeat(task)
                        if new_due:
                            task["due_time"] = new_due.isoformat()
                            task["overdue_count"] = 0
                            await redis.zadd(key, {json.dumps(task, ensure_ascii=False): new_due.timestamp()})
                    result.append(task)
                except json.JSONDecodeError:
                    continue

            return result
        except Exception as e:
            logger.error(f"处理家庭任务失败 {key}: {e}")
            return []

    def _calc_next_repeat(self, task: dict) -> Optional[datetime]:
        """计算下次重复时间"""
        from dateutil.relativedelta import relativedelta

        rule = task.get("repeat_rule")
        if not rule:
            return None

        due = datetime.fromisoformat(task["due_time"])
        now = datetime.now(timezone.utc)

        repeat_type = rule.get("type")
        if repeat_type == "daily":
            next_due = due + timedelta(days=1)
            while next_due <= now:
                next_due += timedelta(days=1)
            return next_due

        elif repeat_type == "weekly":
            next_due = due + timedelta(weeks=1)
            while next_due <= now:
                next_due += timedelta(weeks=1)
            return next_due

        elif repeat_type == "monthly":
            day = rule.get("day", due.day)
            next_due = due + relativedelta(months=1)
            try:
                next_due = next_due.replace(day=min(day, 28))
            except ValueError:
                next_due = next_due.replace(day=28)
            while next_due <= now:
                next_due += relativedelta(months=1)
                try:
                    next_due = next_due.replace(day=min(day, 28))
                except ValueError:
                    next_due = next_due.replace(day=28)
            return next_due

        return None

    async def _push_notification(self, task: dict):
        """推送通知（调用 push 服务）"""
        try:
            from app.services.push import push_service
            await push_service.send_reminder(task)
        except Exception as e:
            logger.error(f"推送通知失败: {e}")


# 单例
reminder_service = ReminderService()