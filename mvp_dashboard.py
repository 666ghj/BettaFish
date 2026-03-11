from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pymysql
from flask import Blueprint, jsonify, render_template, request
from loguru import logger

from config import settings


mvp_bp = Blueprint("mvp_dashboard", __name__, url_prefix="/mvp")


def _db_conn():
    return pymysql.connect(
        host=settings.DB_HOST,
        port=int(settings.DB_PORT),
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        charset=settings.DB_CHARSET or "utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def _parse_int(value: Any) -> int:
    if value is None:
        return 0
    text = str(value).strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else 0


def _default_date_range(days: int = 30) -> tuple[str, str]:
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days - 1)
    return str(start_date), str(end_date)


def _safe_pagination(page: str | None, page_size: str | None) -> tuple[int, int]:
    p = max(int(page or 1), 1)
    s = min(max(int(page_size or 10), 1), 50)
    return p, s


@mvp_bp.route("/")
def hot_page():
    return render_template("mvp/hot_ranking.html", page_key="hot")


@mvp_bp.route("/trend")
def trend_page():
    return render_template("mvp/trend.html", page_key="trend")


@mvp_bp.route("/heatmap")
def heatmap_page():
    return render_template("mvp/heatmap.html", page_key="heatmap")


@mvp_bp.route("/api/hot-events")
def hot_events():
    platform = (request.args.get("platform") or "weibo").strip().lower()
    topic = (request.args.get("topic") or "").strip()
    start_date = (request.args.get("start_date") or "").strip()
    end_date = (request.args.get("end_date") or "").strip()
    page, page_size = _safe_pagination(request.args.get("page"), request.args.get("page_size"))
    offset = (page - 1) * page_size

    if not start_date or not end_date:
        start_date, end_date = _default_date_range(30)

    if platform != "weibo":
        return jsonify({"success": False, "message": "当前MVP仅支持 weibo 平台"}), 400

    where = [
        "wn.create_date_time >= %s",
        "wn.create_date_time <= %s",
    ]
    params: list[Any] = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
    if topic:
        where.append("(dt.topic_name LIKE %s OR wn.source_keyword LIKE %s)")
        params.extend([f"%{topic}%", f"%{topic}%"])

    where_sql = " AND ".join(where)
    try:
        with _db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        COUNT(*) AS total
                    FROM weibo_note wn
                    LEFT JOIN daily_topics dt ON dt.topic_id = wn.topic_id
                    WHERE {where_sql}
                    """,
                    params,
                )
                total = int(cur.fetchone()["total"])

                cur.execute(
                    f"""
                    SELECT
                        wn.note_id,
                        wn.nickname,
                        wn.content,
                        wn.create_date_time,
                        wn.source_keyword,
                        wn.liked_count,
                        wn.comments_count,
                        wn.shared_count,
                        wn.note_url,
                        COALESCE(dt.topic_name, '') AS topic_name
                    FROM weibo_note wn
                    LEFT JOIN daily_topics dt ON dt.topic_id = wn.topic_id
                    WHERE {where_sql}
                    ORDER BY wn.create_date_time DESC
                    LIMIT %s OFFSET %s
                    """,
                    params + [page_size, offset],
                )
                rows = cur.fetchall()
    except Exception as exc:
        logger.exception(f"hot-events 查询失败: {exc}")
        return jsonify({"success": False, "message": f"数据库查询失败: {exc}"}), 500

    items = []
    for row in rows:
        likes = _parse_int(row.get("liked_count"))
        comments = _parse_int(row.get("comments_count"))
        shares = _parse_int(row.get("shared_count"))
        risk_index = min(100, int(likes * 0.08 + comments * 0.25 + shares * 0.3))
        items.append(
            {
                "note_id": row.get("note_id"),
                "nickname": row.get("nickname") or "匿名用户",
                "content": row.get("content") or "",
                "create_time": row.get("create_date_time") or "",
                "topic_name": row.get("topic_name") or row.get("source_keyword") or "未分类",
                "liked_count": likes,
                "comments_count": comments,
                "shared_count": shares,
                "risk_index": risk_index,
                "note_url": row.get("note_url") or "",
                "platform": "weibo",
            }
        )

    return jsonify(
        {
            "success": True,
            "data": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size if total else 0,
            },
            "filters": {
                "platform": platform,
                "topic": topic,
                "start_date": start_date,
                "end_date": end_date,
            },
        }
    )


@mvp_bp.route("/api/ranking")
def ranking():
    topic = (request.args.get("topic") or "").strip()
    start_date = (request.args.get("start_date") or "").strip()
    end_date = (request.args.get("end_date") or "").strip()
    top_n = min(max(int(request.args.get("top_n", "10")), 1), 20)
    if not start_date or not end_date:
        start_date, end_date = _default_date_range(30)

    where = ["wn.create_date_time >= %s", "wn.create_date_time <= %s"]
    params: list[Any] = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
    if topic:
        where.append("(dt.topic_name LIKE %s OR wn.source_keyword LIKE %s)")
        params.extend([f"%{topic}%", f"%{topic}%"])
    where_sql = " AND ".join(where)

    try:
        with _db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        wn.note_id,
                        wn.nickname,
                        wn.content,
                        wn.create_date_time,
                        wn.liked_count,
                        wn.comments_count,
                        wn.shared_count,
                        COALESCE(dt.topic_name, '') AS topic_name
                    FROM weibo_note wn
                    LEFT JOIN daily_topics dt ON dt.topic_id = wn.topic_id
                    WHERE {where_sql}
                    ORDER BY wn.create_date_time DESC
                    LIMIT 300
                    """,
                    params,
                )
                rows = cur.fetchall()
    except Exception as exc:
        logger.exception(f"ranking 查询失败: {exc}")
        return jsonify({"success": False, "message": f"数据库查询失败: {exc}"}), 500

    scored = []
    for row in rows:
        likes = _parse_int(row.get("liked_count"))
        comments = _parse_int(row.get("comments_count"))
        shares = _parse_int(row.get("shared_count"))
        score = likes + comments * 2 + shares * 2
        scored.append(
            {
                "note_id": row.get("note_id"),
                "nickname": row.get("nickname") or "匿名用户",
                "content": row.get("content") or "",
                "topic_name": row.get("topic_name") or "未分类",
                "create_time": row.get("create_date_time") or "",
                "heat_score": score,
                "liked_count": likes,
                "comments_count": comments,
                "shared_count": shares,
            }
        )

    scored.sort(key=lambda x: x["heat_score"], reverse=True)
    return jsonify(
        {
            "success": True,
            "data": scored[:top_n],
            "filters": {"topic": topic, "start_date": start_date, "end_date": end_date, "top_n": top_n},
        }
    )


@mvp_bp.route("/api/trend-30d")
def trend_30d():
    topic = (request.args.get("topic") or "").strip()
    start_date = (request.args.get("start_date") or "").strip()
    end_date = (request.args.get("end_date") or "").strip()
    if not start_date or not end_date:
        start_date, end_date = _default_date_range(30)

    where = ["dt.extract_date >= %s", "dt.extract_date <= %s"]
    params: list[Any] = [start_date, end_date]
    if topic:
        where.append("dt.topic_name LIKE %s")
        params.append(f"%{topic}%")
    where_sql = " AND ".join(where)

    try:
        with _db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        dt.extract_date AS report_date,
                        COUNT(*) AS topic_count,
                        AVG(COALESCE(dt.relevance_score, 0)) AS avg_relevance
                    FROM daily_topics dt
                    WHERE {where_sql}
                    GROUP BY dt.extract_date
                    ORDER BY dt.extract_date ASC
                    """,
                    params,
                )
                rows = cur.fetchall()
    except Exception as exc:
        logger.exception(f"trend 查询失败: {exc}")
        return jsonify({"success": False, "message": f"数据库查询失败: {exc}"}), 500

    dates = []
    topic_counts = []
    risk_index = []
    for row in rows:
        d = str(row["report_date"])
        cnt = int(row.get("topic_count") or 0)
        rel = float(row.get("avg_relevance") or 0.0)
        # 将 relevance 平滑映射到 0-100 风险指数
        risk = max(0, min(100, int(rel * 20 + cnt * 1.5)))
        dates.append(d)
        topic_counts.append(cnt)
        risk_index.append(risk)

    return jsonify(
        {
            "success": True,
            "data": {"dates": dates, "topic_counts": topic_counts, "risk_index": risk_index},
            "filters": {"topic": topic, "start_date": start_date, "end_date": end_date},
        }
    )


@mvp_bp.route("/api/heatmap-china")
def heatmap_china():
    start_date = (request.args.get("start_date") or "").strip()
    end_date = (request.args.get("end_date") or "").strip()
    if not start_date or not end_date:
        start_date, end_date = _default_date_range(30)

    # 固定映射为中国省级名称，便于前端直接喂给ECharts地图
    province_alias = {
        "北京": "北京市",
        "上海": "上海市",
        "天津": "天津市",
        "重庆": "重庆市",
        "内蒙古": "内蒙古自治区",
        "广西": "广西壮族自治区",
        "西藏": "西藏自治区",
        "宁夏": "宁夏回族自治区",
        "新疆": "新疆维吾尔自治区",
        "香港": "香港特别行政区",
        "澳门": "澳门特别行政区",
    }

    try:
        with _db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        IFNULL(ip_location, '') AS ip_location,
                        liked_count,
                        comments_count,
                        shared_count
                    FROM weibo_note
                    WHERE create_date_time >= %s AND create_date_time <= %s
                    LIMIT 3000
                    """,
                    [f"{start_date} 00:00:00", f"{end_date} 23:59:59"],
                )
                rows = cur.fetchall()
    except Exception as exc:
        logger.exception(f"heatmap 查询失败: {exc}")
        return jsonify({"success": False, "message": f"数据库查询失败: {exc}"}), 500

    region_scores: dict[str, int] = {}
    region_events: dict[str, int] = {}
    for row in rows:
        location = (row.get("ip_location") or "").replace("IP属地：", "").strip()
        if not location:
            continue
        region = location[:2]
        if location.startswith(("内蒙古", "黑龙江")):
            region = location[:3]
        if location.startswith(("新疆", "广西", "宁夏", "西藏")):
            region = location[:2]

        region_name = province_alias.get(region, f"{region}省" if len(region) == 2 else region)
        likes = _parse_int(row.get("liked_count"))
        comments = _parse_int(row.get("comments_count"))
        shares = _parse_int(row.get("shared_count"))
        score = likes + comments * 2 + shares * 2

        region_scores[region_name] = region_scores.get(region_name, 0) + score
        region_events[region_name] = region_events.get(region_name, 0) + 1

    max_score = max(region_scores.values()) if region_scores else 1
    heat_data = []
    for region_name, score in region_scores.items():
        normalized = int((score / max_score) * 100)
        heat_data.append({"name": region_name, "value": normalized, "event_count": region_events[region_name]})

    return jsonify(
        {
            "success": True,
            "data": heat_data,
            "filters": {"start_date": start_date, "end_date": end_date},
        }
    )
