# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：  
# 1. 不得用于任何商业用途。  
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。  
# 3. 不得进行大规模爬取或对平台造成运营干扰。  
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。   
# 5. 不得用于任何非法或不当的用途。
#   
# 详细许可条款请参阅项目根目录下的LICENSE文件。  
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。  


# -*- coding: utf-8 -*-
from typing import Dict, List

import config
from base.base_crawler import AbstractStore
from model.m_zhihu import ZhihuComment, ZhihuContent, ZhihuCreator
from ._store_impl import (ZhihuCsvStoreImplement,
                                          ZhihuDbStoreImplement,
                                          ZhihuJsonStoreImplement,
                                          ZhihuSqliteStoreImplement)
from tools import utils
from var import source_keyword_var


class ZhihuStoreFactory:
    STORES = {
        "csv": ZhihuCsvStoreImplement,
        "db": ZhihuDbStoreImplement,
        "json": ZhihuJsonStoreImplement,
        "sqlite": ZhihuSqliteStoreImplement,
        "postgresql": ZhihuDbStoreImplement,
    }

    @staticmethod
    def create_store() -> AbstractStore:
        store_class = ZhihuStoreFactory.STORES.get(config.SAVE_DATA_OPTION)
        if not store_class:
            raise ValueError("[ZhihuStoreFactory.create_store] Invalid save option only supported csv or db or json or sqlite or postgresql ...")
        return store_class()

STRING_FIELDS_CONTENT = [
    "content_id",
    "content_type",
    "content_text",
    "content_url",
    "question_id",
    "title",
    "desc",
    "created_time",
    "updated_time",
    "source_keyword",
    "user_id",
    "user_link",
    "user_nickname",
    "user_avatar",
    "user_url_token",
]

STRING_FIELDS_COMMENT = [
    "comment_id",
    "parent_comment_id",
    "content",
    "publish_time",
    "content_id",
    "content_type",
    "user_id",
    "user_link",
    "user_nickname",
    "user_avatar",
]

STRING_FIELDS_CREATOR = [
    "user_id",
    "user_link",
    "user_nickname",
    "user_avatar",
    "url_token",
    "gender",
    "ip_location",
]


def _normalize_strings(payload: Dict, string_fields: List[str], context: str) -> Dict:
    """
    将原始字典中需要是字符串的字段强制转为字符串，并打印类型快照，便于排查 asyncpg DataError。
    """
    type_snapshot = {}
    for key in string_fields:
        if key not in payload:
            continue
        value = payload[key]
        type_snapshot[key] = type(value).__name__
        if value is None:
            payload[key] = ""
        elif not isinstance(value, str):
            utils.logger.warning(
                f"[store.zhihu.{context}] 字段 {key} 期望 str，实际 {type(value).__name__}，值={value}，已强制转为字符串"
            )
            payload[key] = str(value)
    utils.logger.debug(f"[store.zhihu.{context}] 字段类型快照: {type_snapshot}")
    return payload


async def batch_update_zhihu_contents(contents: List[ZhihuContent]):
    """
    批量更新知乎内容
    Args:
        contents:

    Returns:

    """
    if not contents:
        return

    for content_item in contents:
        await update_zhihu_content(content_item)

async def update_zhihu_content(content_item: ZhihuContent):
    """
    更新知乎内容
    Args:
        content_item:

    Returns:

    """
    content_item.source_keyword = source_keyword_var.get()
    local_db_item = content_item.model_dump()
    local_db_item.update({"last_modify_ts": utils.get_current_timestamp()})
    local_db_item = _normalize_strings(local_db_item, STRING_FIELDS_CONTENT, "update_zhihu_content")
    utils.logger.info(f"[store.zhihu.update_zhihu_content] zhihu content: {local_db_item}")
    await ZhihuStoreFactory.create_store().store_content(local_db_item)



async def batch_update_zhihu_note_comments(comments: List[ZhihuComment]):
    """
    批量更新知乎内容评论
    Args:
        comments:

    Returns:

    """
    if not comments:
        return
    
    for comment_item in comments:
        await update_zhihu_content_comment(comment_item)


async def update_zhihu_content_comment(comment_item: ZhihuComment):
    """
    更新知乎内容评论
    Args:
        comment_item:

    Returns:

    """
    local_db_item = comment_item.model_dump()
    local_db_item.update({"last_modify_ts": utils.get_current_timestamp()})
    local_db_item = _normalize_strings(local_db_item, STRING_FIELDS_COMMENT, "update_zhihu_content_comment")
    utils.logger.info(f"[store.zhihu.update_zhihu_note_comment] zhihu content comment:{local_db_item}")
    await ZhihuStoreFactory.create_store().store_comment(local_db_item)


async def save_creator(creator: ZhihuCreator):
    """
    保存知乎创作者信息
    Args:
        creator:

    Returns:

    """
    if not creator:
        return
    local_db_item = creator.model_dump()
    local_db_item.update({"last_modify_ts": utils.get_current_timestamp()})
    local_db_item = _normalize_strings(local_db_item, STRING_FIELDS_CREATOR, "save_creator")
    await ZhihuStoreFactory.create_store().store_creator(local_db_item)
