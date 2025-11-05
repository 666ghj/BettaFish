"""
舆情大数据聚合主表ORM模型（自动由原tables.sql结构同步生成，对应大表批量搜索与内容入库）

数据模型定义位置：
- MindSpider/DeepSentimentCrawling/MediaCrawler/schema/tables.sql  # 主表结构来源文件
- 本模块（自动映射SQL表，适配MySQL/PostgreSQL，推荐手动完善注释、唯一/索引补充）
- MindSpider/schema/models_sa.py  # Base 定义来源

本模块以MindSpider\DeepSentimentCrawling\MediaCrawler\database\models.py为准
"""

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, BigInteger, Text, ForeignKey

# 使用 models_sa 中的 Base，确保所有表在同一个 metadata 中，外键引用可以正常工作
from models_sa import Base

class BilibiliVideo(Base):
    __tablename__ = "bilibili_video"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, unique=True)
    video_url: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    liked_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    video_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    create_time: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    disliked_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_play_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_favorite_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_share_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_coin_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_danmaku: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_keyword: Mapped[str | None] = mapped_column(Text, default='', nullable=True)
    topic_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("daily_topics.topic_id", ondelete="SET NULL"), nullable=True)
    crawling_task_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("crawling_tasks.task_id", ondelete="SET NULL"), nullable=True)

class BilibiliVideoComment(Base):
    __tablename__ = "bilibili_video_comment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    sex: Mapped[str | None] = mapped_column(Text, nullable=True)
    sign: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    comment_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    video_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    create_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sub_comment_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_comment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    like_count: Mapped[str | None] = mapped_column(Text, default='0', nullable=True)


class BilibiliUpInfo(Base):
    __tablename__ = "bilibili_up_info"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    sex: Mapped[str | None] = mapped_column(Text, nullable=True)
    sign: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_fans: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_liked: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_official: Mapped[int | None] = mapped_column(Integer, nullable=True)


class BilibiliContactInfo(Base):
    __tablename__ = "bilibili_contact_info"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    up_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    fan_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    up_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    fan_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    up_sign: Mapped[str | None] = mapped_column(Text, nullable=True)
    fan_sign: Mapped[str | None] = mapped_column(Text, nullable=True)
    up_avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    fan_avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class BilibiliUpDynamic(Base):
    __tablename__ = "bilibili_up_dynamic"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dynamic_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str | None] = mapped_column(Text, nullable=True)
    pub_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_forwards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_liked: Mapped[int | None] = mapped_column(Integer, nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class DouyinAweme(Base):
    __tablename__ = "douyin_aweme"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sec_uid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    short_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_unique_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    aweme_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    aweme_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    create_time: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    liked_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    share_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    collected_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    aweme_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_download_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    music_download_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_download_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_keyword: Mapped[str | None] = mapped_column(Text, default='', nullable=True)
    topic_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("daily_topics.topic_id", ondelete="SET NULL"), nullable=True)
    crawling_task_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("crawling_tasks.task_id", ondelete="SET NULL"), nullable=True)

class DouyinAwemeComment(Base):
    __tablename__ = "douyin_aweme_comment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sec_uid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    short_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_unique_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    comment_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    aweme_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    create_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sub_comment_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_comment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    like_count: Mapped[str | None] = mapped_column(Text, default='0', nullable=True)
    pictures: Mapped[str | None] = mapped_column(Text, default='', nullable=True)


class DyCreator(Base):
    __tablename__ = "dy_creator"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    gender: Mapped[str | None] = mapped_column(Text, nullable=True)
    follows: Mapped[str | None] = mapped_column(Text, nullable=True)
    fans: Mapped[str | None] = mapped_column(Text, nullable=True)
    interaction: Mapped[str | None] = mapped_column(Text, nullable=True)
    videos_count: Mapped[str | None] = mapped_column(String(255), nullable=True)


class KuaishouVideo(Base):
    __tablename__ = "kuaishou_video"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    video_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    video_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    create_time: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    liked_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    viewd_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_cover_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_play_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_keyword: Mapped[str | None] = mapped_column(Text, default='', nullable=True)
    topic_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("daily_topics.topic_id", ondelete="SET NULL"), nullable=True)
    crawling_task_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("crawling_tasks.task_id", ondelete="SET NULL"), nullable=True)

class KuaishouVideoComment(Base):
    __tablename__ = "kuaishou_video_comment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    comment_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    video_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    create_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sub_comment_count: Mapped[str | None] = mapped_column(Text, nullable=True)

class WeiboNote(Base):
    __tablename__ = "weibo_note"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    gender: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_location: Mapped[str | None] = mapped_column(Text, default='', nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    note_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    create_time: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    create_date_time: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    liked_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    comments_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    shared_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_keyword: Mapped[str | None] = mapped_column(Text, default='', nullable=True)
    topic_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("daily_topics.topic_id", ondelete="SET NULL"), nullable=True)
    crawling_task_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("crawling_tasks.task_id", ondelete="SET NULL"), nullable=True)

class WeiboNoteComment(Base):
    __tablename__ = "weibo_note_comment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    gender: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_location: Mapped[str | None] = mapped_column(Text, default='', nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    comment_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    note_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    create_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    create_date_time: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    comment_like_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    sub_comment_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_comment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)


class WeiboCreator(Base):
    __tablename__ = "weibo_creator"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    gender: Mapped[str | None] = mapped_column(Text, nullable=True)
    follows: Mapped[str | None] = mapped_column(Text, nullable=True)
    fans: Mapped[str | None] = mapped_column(Text, nullable=True)
    tag_list: Mapped[str | None] = mapped_column(Text, nullable=True)


class XhsCreator(Base):
    __tablename__ = "xhs_creator"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    gender: Mapped[str | None] = mapped_column(Text, nullable=True)
    follows: Mapped[str | None] = mapped_column(Text, nullable=True)
    fans: Mapped[str | None] = mapped_column(Text, nullable=True)
    interaction: Mapped[str | None] = mapped_column(Text, nullable=True)
    tag_list: Mapped[str | None] = mapped_column(Text, nullable=True)


class XhsNote(Base):
    __tablename__ = "xhs_note"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    note_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    type: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    time: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    last_update_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    liked_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    collected_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    share_count: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_list: Mapped[str | None] = mapped_column(Text, nullable=True)
    tag_list: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_keyword: Mapped[str | None] = mapped_column(Text, default='', nullable=True)
    xsec_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("daily_topics.topic_id", ondelete="SET NULL"), nullable=True)
    crawling_task_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("crawling_tasks.task_id", ondelete="SET NULL"), nullable=True)


class XhsNoteComment(Base):
    __tablename__ = "xhs_note_comment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    comment_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    create_time: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    note_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    sub_comment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pictures: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_comment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    like_count: Mapped[str | None] = mapped_column(Text, nullable=True)

class TiebaNote(Base):
    __tablename__ = "tieba_note"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    note_id: Mapped[str | None] = mapped_column(String(644), index=True, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_time: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    user_link: Mapped[str | None] = mapped_column(Text, default='', nullable=True)
    user_nickname: Mapped[str | None] = mapped_column(Text, default='', nullable=True)
    user_avatar: Mapped[str | None] = mapped_column(Text, default='', nullable=True)
    tieba_id: Mapped[str | None] = mapped_column(String(255), default='', nullable=True)
    tieba_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    tieba_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_replay_num: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    total_replay_page: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    ip_location: Mapped[str | None] = mapped_column(Text, default='', nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_keyword: Mapped[str | None] = mapped_column(Text, default='', nullable=True)
    topic_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("daily_topics.topic_id", ondelete="SET NULL"), nullable=True)
    crawling_task_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("crawling_tasks.task_id", ondelete="SET NULL"), nullable=True)

class TiebaComment(Base):
    __tablename__ = "tieba_comment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comment_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    parent_comment_id: Mapped[str | None] = mapped_column(String(255), default='', nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_link: Mapped[str | None] = mapped_column(Text, default='', nullable=True)
    user_nickname: Mapped[str | None] = mapped_column(Text, default='', nullable=True)
    user_avatar: Mapped[str | None] = mapped_column(Text, default='', nullable=True)
    tieba_id: Mapped[str | None] = mapped_column(String(255), default='', nullable=True)
    tieba_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    tieba_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_time: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    ip_location: Mapped[str | None] = mapped_column(Text, default='', nullable=True)
    sub_comment_count: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    note_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    note_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class TiebaCreator(Base):
    __tablename__ = "tieba_creator"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    gender: Mapped[str | None] = mapped_column(Text, nullable=True)
    follows: Mapped[str | None] = mapped_column(Text, nullable=True)
    fans: Mapped[str | None] = mapped_column(Text, nullable=True)
    registration_duration: Mapped[str | None] = mapped_column(Text, nullable=True)


class ZhihuContent(Base):
    __tablename__ = "zhihu_content"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    content_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_time: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    updated_time: Mapped[str | None] = mapped_column(Text, nullable=True)
    voteup_count: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    comment_count: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    source_keyword: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_url_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    topic_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("daily_topics.topic_id", ondelete="SET NULL"), nullable=True)
    crawling_task_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("crawling_tasks.task_id", ondelete="SET NULL"), nullable=True)

class ZhihuComment(Base):
    __tablename__ = "zhihu_comment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comment_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    parent_comment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_time: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    ip_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    sub_comment_count: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    like_count: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    dislike_count: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    content_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    content_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class ZhihuCreator(Base):
    __tablename__ = "zhihu_creator"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    user_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_nickname: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    url_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    gender: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    follows: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    fans: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    anwser_count: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    video_count: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    question_count: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    article_count: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    column_count: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    get_voteup_count: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    add_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_modify_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
