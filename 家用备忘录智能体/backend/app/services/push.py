# -*- coding: utf-8 -*-
"""
微信推送服务。

使用微信小程序订阅消息进行推送。
"""
from typing import Optional
from loguru import logger
import httpx
import json

from app.config import settings


class PushService:
    """
    推送服务。

    目前支持微信订阅消息，后续可扩展 App Push、短信等通道。
    """

    def __init__(self):
        self._access_token: Optional[str] = None
        self._token_expire: float = 0

    async def _get_access_token(self) -> Optional[str]:
        """获取微信 access_token"""
        now = __import__("time").time()
        if self._access_token and now < self._token_expire:
            return self._access_token

        if not settings.WECHAT_APPID or not settings.WECHAT_SECRET:
            logger.warning("微信小程序未配置，无法推送")
            return None

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.weixin.qq.com/cgi-bin/token",
                    params={
                        "grant_type": "client_credential",
                        "appid": settings.WECHAT_APPID,
                        "secret": settings.WECHAT_SECRET,
                    },
                )
                data = resp.json()
                if "access_token" in data:
                    self._access_token = data["access_token"]
                    self._token_expire = now + data.get("expires_in", 7200) - 300
                    return self._access_token
                else:
                    logger.error(f"获取 access_token 失败: {data}")
                    return None
        except Exception as e:
            logger.error(f"获取 access_token 异常: {e}")
            return None

    async def send_reminder(self, task: dict) -> bool:
        """
        发送提醒推送。

        使用微信小程序订阅消息。
        """
        # TODO: 接入微信订阅消息 API
        # 需要用户先订阅，获取 template_id 和用户 openid

        memo_id = task.get("memo_id", "")
        family_id = task.get("family_id", "")
        due_time = task.get("due_time", "")
        overdue_count = task.get("overdue_count", 0)

        logger.info(f"推送提醒: memo_id={memo_id}, due_time={due_time}, overdue_count={overdue_count}")

        # 逾期升级策略
        if overdue_count >= 7:
            # 逾期7天，通知配偶
            logger.info(f"逾期7天，需通知配偶: {memo_id}")
        elif overdue_count >= 3:
            # 逾期3天，升级推送频次
            logger.info(f"逾期3天，升级推送: {memo_id}")

        # TODO: 实际调用微信订阅消息接口
        # template_msg = {
        #     "touser": "openid",
        #     "template_id": "template_id",
        #     "page": "pages/index/index",
        #     "data": {
        #         "thing1": {"value": "缴费提醒"},
        #         "time2": {"value": due_time},
        #         "thing3": {"value": "请及时处理"},
        #     },
        # }

        return True

    async def send_subscribe_guide(self, openid: str) -> bool:
        """
        引导用户订阅提醒消息。
        在创建提醒时调用。
        """
        # TODO: 调用微信订阅消息引导
        return True


# 单例
push_service = PushService()