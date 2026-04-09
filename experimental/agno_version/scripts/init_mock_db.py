#!/usr/bin/env python3
"""
初始化 SQLite mock 数据库，模拟 BettaFish 的 MediaCrawler 表结构。
塞入约 100 条假的社交媒体内容（围绕 Claude Code/AI 编程主题），
让 InsightAgent 能跑通端到端流程。

用法：
    python scripts/init_mock_db.py
"""

import sqlite3
import sys
import random
from pathlib import Path
from datetime import datetime, timedelta

# 确保能找到项目根
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "mock_yuqing.db"
DB_PATH.parent.mkdir(exist_ok=True)

# ===== 表结构定义 =====
# 简化版，只保留 db_query_tools.py 用到的字段

SCHEMAS = {
    # 内容表
    "weibo_note": """
        CREATE TABLE weibo_note (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            source_keyword TEXT,
            create_date_time TEXT,
            nickname TEXT,
            note_url TEXT,
            liked_count INTEGER,
            comments_count INTEGER,
            shared_count INTEGER
        )
    """,
    "xhs_note": """
        CREATE TABLE xhs_note (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            "desc" TEXT,
            tag_list TEXT,
            source_keyword TEXT,
            time INTEGER,
            nickname TEXT,
            note_url TEXT,
            liked_count INTEGER,
            comment_count INTEGER,
            share_count INTEGER,
            collected_count INTEGER
        )
    """,
    "zhihu_content": """
        CREATE TABLE zhihu_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            "desc" TEXT,
            content_text TEXT,
            source_keyword TEXT,
            created_time TEXT,
            user_nickname TEXT,
            content_url TEXT,
            voteup_count INTEGER,
            comment_count INTEGER
        )
    """,
    "bilibili_video": """
        CREATE TABLE bilibili_video (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            "desc" TEXT,
            source_keyword TEXT,
            create_time INTEGER,
            nickname TEXT,
            video_url TEXT,
            liked_count INTEGER,
            video_comment INTEGER,
            video_share_count INTEGER,
            video_play_count INTEGER,
            video_favorite_count INTEGER,
            video_coin_count INTEGER,
            video_danmaku INTEGER
        )
    """,
    "douyin_aweme": """
        CREATE TABLE douyin_aweme (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            "desc" TEXT,
            source_keyword TEXT,
            create_time INTEGER,
            nickname TEXT,
            aweme_url TEXT,
            liked_count INTEGER,
            comment_count INTEGER,
            share_count INTEGER,
            collected_count INTEGER
        )
    """,
    "kuaishou_video": """
        CREATE TABLE kuaishou_video (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            "desc" TEXT,
            source_keyword TEXT,
            create_time INTEGER,
            nickname TEXT,
            video_url TEXT,
            liked_count INTEGER,
            viewd_count INTEGER
        )
    """,
    "tieba_note": """
        CREATE TABLE tieba_note (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            "desc" TEXT,
            source_keyword TEXT,
            publish_time TEXT,
            nickname TEXT,
            url TEXT
        )
    """,

    # 评论表
    "weibo_note_comment": """
        CREATE TABLE weibo_note_comment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            user_nickname TEXT,
            create_date_time TEXT,
            comment_like_count INTEGER
        )
    """,
    "xhs_note_comment": """
        CREATE TABLE xhs_note_comment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            user_nickname TEXT,
            create_time INTEGER,
            like_count INTEGER
        )
    """,
    "zhihu_comment": """
        CREATE TABLE zhihu_comment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            user_nickname TEXT,
            create_time INTEGER,
            like_count INTEGER
        )
    """,
    "bilibili_video_comment": """
        CREATE TABLE bilibili_video_comment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            user_nickname TEXT,
            create_time INTEGER,
            like_count INTEGER
        )
    """,
    "douyin_aweme_comment": """
        CREATE TABLE douyin_aweme_comment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            user_nickname TEXT,
            create_time INTEGER,
            like_count INTEGER
        )
    """,
    "kuaishou_video_comment": """
        CREATE TABLE kuaishou_video_comment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            user_nickname TEXT,
            create_time INTEGER,
            like_count INTEGER
        )
    """,
    "tieba_comment": """
        CREATE TABLE tieba_comment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            nickname TEXT,
            publish_time TEXT,
            like_count INTEGER
        )
    """,
}


# ===== Mock 数据生成 =====

# 围绕 Claude Code 主题的内容池
WEIBO_POSTS = [
    ("Claude Code 真的太香了！终于不用自己一个个调代码了，AI 直接给我写好测试用例", "weibo_user_001", 8521, 1234, 567),
    ("用 Claude Code 重构了一个 5000 行的老项目，效率提升至少 10 倍。Anthropic 牛逼", "码农日记", 12453, 2341, 891),
    ("Claude Code 还是比 Cursor 强一些，至少不会乱删我代码 😅 #AI编程#", "前端小张", 3421, 567, 123),
    ("吐槽一下 Claude Code 的定价，订阅费有点贵，希望能出学生版", "穷学生程序猿", 567, 234, 45),
    ("Claude Code 能直接跑命令行真的爽，比 GitHub Copilot 强多了", "后端老王", 9821, 1567, 432),
    ("AI 编程工具大乱斗：Claude Code vs Cursor vs Copilot，谁更值得？详见正文", "AI测评师", 23456, 4321, 1567),
]

XHS_POSTS = [
    ("Claude Code 入门指南｜小白也能看懂", "Anthropic 出品的 AI 编程神器使用教程", "AI编程,Claude,程序员,效率工具", "美少女程序媛", 12345, 2341, 456, 5678),
    ("Claude Code 一周使用感受💻", "从零开始用 Claude Code 完成了一个完整的 Web 项目", "AI工具,前端开发,Claude Code", "技术宅小美", 8765, 1234, 234, 3456),
    ("我用 Claude Code 做了一个网站，全程没写一行代码🚀", "给所有不会编程的姐妹分享AI建站经验", "AI建站,无代码,Claude", "互联网创业者Lily", 23456, 4567, 890, 7890),
]

ZHIHU_QUESTIONS = [
    ("如何看待 Anthropic 推出的 Claude Code？", "近期 Anthropic 推出了 Claude Code，能在终端直接运行的 AI 编程助手", "Claude Code 是 Anthropic 在 AI 编程赛道的关键产品。它的特点是可以直接在命令行中运行，深度集成 Git 和 Bash...", "AI研究员", 5678, 234),
    ("Claude Code 和 Cursor 哪个更好用？", "都是热门的 AI 编程工具，想了解实际差异", "我两个都深度用过半年。Cursor 更适合 IDE 用户，UI 友好；Claude Code 更适合命令行用户和自动化场景...", "全栈工程师老李", 12345, 567),
    ("Claude Code 能完全取代程序员吗？", "AI 编程已经这么强了，未来还需要写代码的人吗？", "不能。Claude Code 极大提升了生产力，但代码审查、架构设计、需求理解仍然需要人...", "技术总监 Tom", 23456, 1234),
]

BILIBILI_VIDEOS = [
    ("【AI编程】Claude Code 完整教程，从入门到精通", "保姆级教程，30分钟学会用 Claude Code 写完一个项目", "技术宇宙UP主", 56789, 3456, 1234, 234567, 5678, 1234, 8901),
    ("我用 Claude Code 一晚上写完了毕业设计😱", "程序员的福音！AI 编程工具实战分享", "毕设拯救者", 78901, 5678, 2345, 345678, 8901, 2345, 12345),
    ("Claude Code vs Cursor 横向对比测评", "两大 AI 编程神器深度对比，看完就知道选哪个", "AI工具评测", 23456, 1234, 567, 123456, 2345, 567, 4567),
]

TIEBA_POSTS = [
    ("Claude Code 真有那么神吗？吧里大佬来评测一下", "听说很厉害，但订阅费有点贵想问问值不值", "贴吧吃瓜群众"),
    ("Claude Code 怎么破解？求大神指点", "想试用一下但是不想付费，有没有破解方法", "白嫖党党魁"),
]

# 评论数据池
COMMENTS_POSITIVE = [
    "Claude Code 真的太牛了！", "用了之后再也回不去了 😭", "Anthropic yyds", "效率直接起飞 🚀",
    "终于不用 Stack Overflow 了", "Claude Code 比 ChatGPT 写代码强多了",
    "支持！这才是 AI 编程的未来", "用了一个月，已经爱上",
]
COMMENTS_NEGATIVE = [
    "太贵了，订阅不起 😩", "Cursor 不香吗，何必用这个", "Claude Code 经常给我写 bug",
    "API 限流恶心，体验差", "国内访问不了真的离谱", "还不如自己写",
]
COMMENTS_NEUTRAL = [
    "占楼围观，看看效果", "求个使用教程", "这个和 Cursor 比怎么样？",
    "刚开始学编程，能用吗？", "等大佬测评", "默默 mark 一下",
]


def _ts_now(days_ago=0, ms=False):
    """生成时间戳"""
    dt = datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 23), minutes=random.randint(0, 59))
    if ms:
        return int(dt.timestamp() * 1000)
    return int(dt.timestamp())


def _date_str(days_ago=0):
    return (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")


def init_database():
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"删除旧数据库: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 创建所有表
    for table_name, sql in SCHEMAS.items():
        cur.execute(sql)
        print(f"创建表: {table_name}")

    # ===== 插入内容数据 =====

    # 微博
    for content, nick, likes, comments, shares in WEIBO_POSTS:
        cur.execute(
            "INSERT INTO weibo_note (content, source_keyword, create_date_time, nickname, note_url, liked_count, comments_count, shared_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (content, "Claude Code", _date_str(random.randint(0, 7)), nick, f"https://weibo.com/{random.randint(1000, 9999)}", likes, comments, shares),
        )

    # 小红书
    for title, desc, tags, nick, likes, comments, shares, favs in XHS_POSTS:
        cur.execute(
            "INSERT INTO xhs_note (title, \"desc\", tag_list, source_keyword, time, nickname, note_url, liked_count, comment_count, share_count, collected_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, desc, tags, "Claude Code", _ts_now(random.randint(0, 7), ms=True), nick, f"https://xiaohongshu.com/{random.randint(1000, 9999)}", likes, comments, shares, favs),
        )

    # 知乎
    for title, desc, content, nick, likes, comments in ZHIHU_QUESTIONS:
        cur.execute(
            "INSERT INTO zhihu_content (title, \"desc\", content_text, source_keyword, created_time, user_nickname, content_url, voteup_count, comment_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, desc, content, "Claude Code", str(_ts_now(random.randint(0, 7))), nick, f"https://zhihu.com/question/{random.randint(100000, 999999)}", likes, comments),
        )

    # B站
    for title, desc, nick, likes, comments, shares, plays, favs, coins, danmaku in BILIBILI_VIDEOS:
        cur.execute(
            "INSERT INTO bilibili_video (title, \"desc\", source_keyword, create_time, nickname, video_url, liked_count, video_comment, video_share_count, video_play_count, video_favorite_count, video_coin_count, video_danmaku) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, desc, "Claude Code", _ts_now(random.randint(0, 7)), nick, f"https://bilibili.com/video/BV{random.randint(10000, 99999)}", likes, comments, shares, plays, favs, coins, danmaku),
        )

    # 抖音（简化数据）
    douyin_titles = [
        ("AI编程神器Claude Code实测", "30秒带你看完Claude Code的强大功能", "AI达人小王", 45678, 2345, 1234, 5678),
        ("程序员必看：Claude Code使用技巧", "省下90%开发时间的秘密", "码农生活", 23456, 1234, 567, 2345),
    ]
    for title, desc, nick, likes, comments, shares, favs in douyin_titles:
        cur.execute(
            "INSERT INTO douyin_aweme (title, \"desc\", source_keyword, create_time, nickname, aweme_url, liked_count, comment_count, share_count, collected_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (title, desc, "Claude Code", _ts_now(random.randint(0, 7), ms=True), nick, f"https://douyin.com/video/{random.randint(1000, 9999)}", likes, comments, shares, favs),
        )

    # 快手
    cur.execute(
        "INSERT INTO kuaishou_video (title, \"desc\", source_keyword, create_time, nickname, video_url, liked_count, viewd_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("Claude Code 教学", "AI 编程 一看就会", "Claude Code", "草根程序员", _ts_now(2, ms=True), f"https://kuaishou.com/{random.randint(1000, 9999)}", 12345, 567890),
    )

    # 贴吧
    for title, desc, nick in TIEBA_POSTS:
        cur.execute(
            "INSERT INTO tieba_note (title, \"desc\", source_keyword, publish_time, nickname, url) VALUES (?, ?, ?, ?, ?, ?)",
            (title, desc, "Claude Code", _date_str(random.randint(0, 7)), nick, f"https://tieba.baidu.com/p/{random.randint(1000000, 9999999)}"),
        )

    # ===== 插入评论数据 =====

    def _gen_comments(count, positive_ratio=0.5, negative_ratio=0.3):
        """生成混合情感的评论"""
        result = []
        for _ in range(count):
            r = random.random()
            if r < positive_ratio:
                result.append(random.choice(COMMENTS_POSITIVE))
            elif r < positive_ratio + negative_ratio:
                result.append(random.choice(COMMENTS_NEGATIVE))
            else:
                result.append(random.choice(COMMENTS_NEUTRAL))
        return result

    # 给每个评论表插入 15 条评论（关键词关联 Claude Code）
    comment_tables_meta = {
        "weibo_note_comment": ("user_nickname", "create_date_time", "comment_like_count", "date"),
        "xhs_note_comment": ("user_nickname", "create_time", "like_count", "ts"),
        "zhihu_comment": ("user_nickname", "create_time", "like_count", "ts"),
        "bilibili_video_comment": ("user_nickname", "create_time", "like_count", "ts"),
        "douyin_aweme_comment": ("user_nickname", "create_time", "like_count", "ts"),
        "kuaishou_video_comment": ("user_nickname", "create_time", "like_count", "ts"),
        "tieba_comment": ("nickname", "publish_time", "like_count", "date"),
    }

    for table, (author_col, time_col, like_col, time_format) in comment_tables_meta.items():
        comments = _gen_comments(15)
        # 添加 Claude Code 关键词到部分评论
        for i, c in enumerate(comments):
            if random.random() < 0.6:
                comments[i] = c + "（Claude Code 相关）"

        for c in comments:
            time_val = _date_str(random.randint(0, 14)) if time_format == "date" else _ts_now(random.randint(0, 14))
            nick = f"用户{random.randint(1000, 9999)}"
            likes = random.randint(0, 5000)
            cur.execute(
                f'INSERT INTO {table} (content, "{author_col}", "{time_col}", "{like_col}") VALUES (?, ?, ?, ?)',
                (c, nick, time_val, likes),
            )

    conn.commit()

    # 统计
    print("\n===== 数据统计 =====")
    for table in SCHEMAS.keys():
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        count = cur.fetchone()[0]
        print(f"  {table}: {count} 条")

    conn.close()
    print(f"\n✅ Mock 数据库已创建: {DB_PATH}")
    print(f"\n请确保 .env 中配置：")
    print(f"  DB_DIALECT=sqlite")
    print(f"  DB_NAME={DB_PATH}")


if __name__ == "__main__":
    init_database()
