# -*- coding: utf-8 -*-
"""
时间解析服务。

规则引擎 + LLM 兜底，将中文时间表达式解析为具体时间。
"""
import re
import json
from datetime import datetime, timedelta, date, timezone
from typing import Optional, Tuple
from loguru import logger
from dateutil.relativedelta import relativedelta

from app.config import settings

# 时区
CST = timezone(timedelta(hours=8))


class TimeParser:
    """
    时间解析器。
    先用规则引擎匹配常见表达，匹配不到时调用 LLM 兜底。
    """

    def __init__(self):
        self._today = date.today()
        self._now = datetime.now(CST)

    def resolve(self, expr: str, context: Optional[dict] = None) -> Tuple[Optional[str], float]:
        """
        解析时间表达式。

        Args:
            expr: 时间表达式，如 "明天下午三点"、"下周三"、"月底"
            context: 上下文信息（如家庭习惯）

        Returns:
            (resolved_iso_time, confidence)
            - 无法解析时返回 (None, 0.0)
        """
        if not expr or not expr.strip():
            return None, 0.0

        expr = expr.strip()

        # 1. 规则引擎匹配
        result = self._rule_match(expr)
        if result[0]:
            return result

        # 2. LLM 兜底
        if settings.LLM_API_KEY:
            result = self._llm_fallback(expr, context)
            if result[0]:
                return result

        # 3. 无法解析
        return None, 0.0

    def _rule_match(self, expr: str) -> Tuple[Optional[str], float]:
        """规则引擎匹配常见时间表达"""
        expr = expr.strip().lower()

        # ===== 绝对时间 =====
        # 匹配 "2026年9月2日 10:00" 或 "2026-09-02 10:00"
        m = re.search(r'(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})[日]?\s*(\d{1,2})[:：](\d{2})', expr)
        if m:
            try:
                dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                             int(m.group(4)), int(m.group(5)), tzinfo=CST)
                return (dt.isoformat(), 1.0)
            except ValueError:
                pass

        # 匹配 "9月2日 10:00"
        m = re.search(r'(\d{1,2})[月](\d{1,2})[日]?\s*(\d{1,2})[:：](\d{2})', expr)
        if m:
            try:
                dt = datetime(self._today.year, int(m.group(1)), int(m.group(2)),
                             int(m.group(3)), int(m.group(4)), tzinfo=CST)
                if dt.date() < self._today:
                    dt = dt.replace(year=dt.year + 1)
                return (dt.isoformat(), 1.0)
            except ValueError:
                pass

        # 匹配 "9月2日" 无时间
        m = re.search(r'(\d{1,2})[月](\d{1,2})[日]号?', expr)
        if m:
            try:
                d = date(self._today.year, int(m.group(1)), int(m.group(2)))
                if d < self._today:
                    d = d.replace(year=d.year + 1)
                dt = datetime.combine(d, datetime.min.time(), tzinfo=CST)
                return (dt.isoformat(), 0.9)
            except ValueError:
                pass

        # ===== 相对时间 =====

        # 今天/明天/后天/大后天
        day_map = {
            "大后天": 3, "后天": 2, "明天": 1, "今天": 0, "今日": 0,
            "明日": 1, "昨日": -1, "昨天": -1, "前天": -2,
        }
        for kw, offset in day_map.items():
            if kw in expr:
                target = self._today + timedelta(days=offset)
                time_str = self._extract_time(expr)
                dt = self._combine(target, time_str)
                return (dt.isoformat(), 0.95)

        # 下周几
        weekday_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
        m = re.search(r'下[周]([一二三四五六日天])', expr)
        if m:
            target_weekday = weekday_map.get(m.group(1), 0)
            # 计算下周的星期几
            days_ahead = target_weekday - self._today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            days_ahead += 7  # 下周
            target = self._today + timedelta(days=days_ahead)
            time_str = self._extract_time(expr)
            dt = self._combine(target, time_str)
            return (dt.isoformat(), 0.9)

        # 这周几
        m = re.search(r'这[周]([一二三四五六日天])', expr)
        if m:
            target_weekday = weekday_map.get(m.group(1), 0)
            days_ahead = target_weekday - self._today.weekday()
            if days_ahead < 0:
                days_ahead += 7
            target = self._today + timedelta(days=days_ahead)
            time_str = self._extract_time(expr)
            dt = self._combine(target, time_str)
            return (dt.isoformat(), 0.9)

        # 下个月
        if "下个月" in expr:
            next_month = self._today + relativedelta(months=1)
            day = self._extract_day(expr) or self._today.day
            try:
                target = next_month.replace(day=min(day, 28))  # 避免超出月份天数
                time_str = self._extract_time(expr)
                dt = self._combine(target, time_str)
                return (dt.isoformat(), 0.85)
            except ValueError:
                pass

        # 月底
        if "月底" in expr:
            import calendar
            last_day = calendar.monthrange(self._today.year, self._today.month)[1]
            target = self._today.replace(day=last_day)
            time_str = self._extract_time(expr)
            dt = self._combine(target, time_str)
            return (dt.isoformat(), 0.85)

        # 月初
        if "月初" in expr:
            target = self._today.replace(day=1)
            time_str = self._extract_time(expr)
            dt = self._combine(target, time_str)
            return (dt.isoformat(), 0.85)

        # 周末
        if "周末" in expr:
            days_to_saturday = (5 - self._today.weekday()) % 7
            if days_to_saturday == 0:
                days_to_saturday = 7  # 这周六已经过了，到下周六
            target = self._today + timedelta(days=days_to_saturday)
            time_str = self._extract_time(expr) or "10:00"
            dt = self._combine(target, time_str)
            return (dt.isoformat(), 0.8)

        # 晚上/下午/早上/上午/中午
        time_map = {
            "早上": "08:00", "早晨": "07:00", "上午": "09:00",
            "中午": "12:00", "下午": "14:00", "晚上": "19:00",
            "今晚": "20:00", "明早": "08:00", "明晚": "20:00",
        }
        for kw, default_time in time_map.items():
            if expr.startswith(kw) or expr == kw:
                target = self._today
                if kw in ("明早", "明晚"):
                    target = self._today + timedelta(days=1)
                # 如果已经过了这个时间，推到明天
                time_str = self._extract_time(expr) or default_time
                dt = self._combine(target, time_str)
                # 如果已经过了，推到明天
                if dt <= self._now:
                    dt = dt + timedelta(days=1)
                return (dt.isoformat(), 0.9)

        return None, 0.0

    def _extract_time(self, expr: str, is_evening: bool = False) -> Optional[str]:
        """从表达式中提取时间部分，如 '下午三点' -> '15:00'"""
        # 中文数字映射
        cn_digits = {
            "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
            "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
            "两": 2,
        }

        def _is_evening(expr: str) -> bool:
            return any(kw in expr for kw in ["下午", "晚上", "今晚", "明晚", "半夜"])

        # 优先处理 "X点半"（含中文数字）
        if "半" in expr:
            m = re.search(r'([零一二三四五六七八九两\d]{1,2})点半', expr)
            if m:
                hour_str = m.group(1)
                hour = cn_digits.get(hour_str, int(hour_str) if hour_str.isdigit() else 0)
                if _is_evening(expr) and hour < 12:
                    hour += 12
                return f"{hour:02d}:30"

        # 尝试匹配 "X点" 或 "X点Y分"（支持中文数字）
        m = re.search(r'([零一二三四五六七八九两\d]{1,2})[：:点](\d{0,2})', expr)
        if m:
            hour_str = m.group(1)
            # 中文数字转阿拉伯数字
            hour = cn_digits.get(hour_str, int(hour_str) if hour_str.isdigit() else 0)
            minute = int(m.group(2)) if m.group(2) else 0
            # 处理下午/晚上/今晚
            if _is_evening(expr) and hour < 12:
                hour += 12
            elif "凌晨" in expr or "半夜" in expr:
                if hour < 6:
                    pass  # 凌晨时间
            elif "中午" in expr:
                if hour < 12:
                    hour = 12  # 中午12点
            else:
                # 默认上午
                if hour > 12 and "下午" not in expr and "晚上" not in expr:
                    pass  # 已经是24小时制
            return f"{hour:02d}:{minute:02d}"

        # 半/半点
        if "半" in expr:
            m = re.search(r'([零一二三四五六七八九两\d]{1,2})点半', expr)
            if m:
                hour_str = m.group(1)
                hour = cn_digits.get(hour_str, int(hour_str) if hour_str.isdigit() else 0)
                minute = 30
                if any(kw in expr for kw in ["下午", "晚上", "今晚", "明晚", "半夜"]):
                    if hour < 12:
                        hour += 12
                return f"{hour:02d}:{minute:02d}"
                if "下午" in expr or "晚上" in expr:
                    if hour < 12:
                        hour += 12
                return f"{hour:02d}:30"

        return None

    def _extract_day(self, expr: str) -> Optional[int]:
        """提取日期数字"""
        cn_digits = {
            "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
            "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
            "两": 2,
        }
        m = re.search(r'(\d{1,2})[日号]', expr)
        if m:
            return int(m.group(1))
        # 中文数字日期
        m = re.search(r'([一二三四五六七八九两十]{1,3})[日号]', expr)
        if m:
            day_str = m.group(1)
            if "十" in day_str:
                parts = day_str.split("十")
                if parts[0] and parts[1]:
                    return cn_digits.get(parts[0], 0) * 10 + cn_digits.get(parts[1], 0)
                elif parts[0]:
                    return cn_digits.get(parts[0], 0) * 10
                else:
                    return cn_digits.get(parts[1], 0) + 10
            return cn_digits.get(day_str, 0)
        return None

    def _combine(self, target_date: date, time_str: Optional[str]) -> datetime:
        """将日期和时间组合为 datetime"""
        if time_str:
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            return datetime(target_date.year, target_date.month, target_date.day,
                          hour, minute, tzinfo=CST)
        return datetime(target_date.year, target_date.month, target_date.day,
                      10, 0, tzinfo=CST)  # 默认上午10点

    def _llm_fallback(self, expr: str, context: Optional[dict] = None) -> Tuple[Optional[str], float]:
        """LLM 兜底解析复杂时间表达"""
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
            )

            today = self._today.isoformat()
            now = self._now.strftime("%Y-%m-%d %H:%M")

            prompt = f"""你是一个时间解析专家。请将中文时间表达式解析为 ISO 格式时间。

今天日期: {today}
当前时间: {now}

时间表达式: "{expr}"

请输出 JSON:
{{
    "resolved_time": "ISO格式时间(如2026-09-02T10:00:00+08:00)",
    "confidence": 0.0-1.0,
    "reason": "解析理由"
}}

如果无法确定，confidence 设为 0.0。"""

            response = client.chat.completions.create(
                model=settings.LLM_MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)
            if result.get("confidence", 0) > 0.5:
                return (result["resolved_time"], result["confidence"])
        except Exception as e:
            logger.error(f"LLM 时间解析失败: {e}")

        return None, 0.0


# 单例
time_parser = TimeParser()


async def resolve_time(expr: str, context: Optional[dict] = None) -> Tuple[Optional[str], float]:
    """便捷函数：解析时间表达式"""
    return time_parser.resolve(expr, context)