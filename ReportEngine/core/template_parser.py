"""
Markdown模板切片工具。

LLM需要“按章调用”，因此必须把Markdown模板解析为结构化章节队列。
这里通过轻量正则和缩进启发式，兼容“# 标题”与
“- **1.0 标题** /   - 1.1 子标题”等多种写法。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional

SECTION_ORDER_STEP = 10


@dataclass
class TemplateSection:
    """
    模板章节实体。

    记录标题、slug、序号、层级、原始标题、章节编号与提纲，
    方便后续节点在提示词中引用并保持锚点一致。
    """

    title: str
    slug: str
    order: int
    depth: int
    raw_title: str
    number: str = ""
    chapter_id: str = ""
    outline: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """
        将章节实体序列化为字典。

        该结构广泛用于提示词上下文以及 layout/word budget 节点的输入。
        """
        return {
            "title": self.title,
            "slug": self.slug,
            "order": self.order,
            "depth": self.depth,
            "number": self.number,
            "chapterId": self.chapter_id,
            "outline": self.outline,
        }


# The parsing expressions intentionally avoid `.*` to keep matching deterministic and
# eliminate easy Regular-Expression-DoS gadgets on untrusted template text.
heading_pattern = re.compile(
    r"""
    (?P<marker>\#{1,6})       # Markdown heading markers
    [ \t]+                    # required whitespace
    (?P<title>[^\r\n]+)       # heading text without newline characters
    """,
    re.VERBOSE,
)
bullet_pattern = re.compile(
    r"""
    (?P<marker>[-*+])         # list bullet symbol
    [ \t]+
    (?P<title>[^\r\n]+)
    """,
    re.VERBOSE,
)
number_pattern = re.compile(
    r"""
    (?P<num>
        (?:0|[1-9]\d*)
        (?:\.(?:0|[1-9]\d*))*
    )
    (?:
        (?:[ \t\u00A0\u3000、:：-]+|\.(?!\d))+
        (?P<label>[^\r\n]*)
    )?
    """,
    re.VERBOSE,
)


def parse_template_sections(template_md: str) -> List[TemplateSection]:
    """
    将Markdown模板切分成章节列表（按大标题）。

    返回的每个TemplateSection都携带slug/order/章节号，
    方便后续分章调用与锚点生成。解析时会同时兼容
    “# 标题”“无符号编号”“列表提纲”等不同写法。

    参数:
        template_md: 模板Markdown全文。

    返回:
        list[TemplateSection]: 结构化的章节序列。
    """

    sections: List[TemplateSection] = []
    current: Optional[TemplateSection] = None
    order = SECTION_ORDER_STEP
    used_slugs = set()

    for raw_line in template_md.splitlines():
        if not raw_line.strip():
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()

        meta = _classify_line(stripped, indent)
        if not meta:
            continue

        if meta["is_section"]:
            slug = _ensure_unique_slug(meta["slug"], used_slugs)
            section = TemplateSection(
                title=meta["title"],
                slug=slug,
                order=order,
                depth=meta["depth"],
                raw_title=meta["raw"],
                number=meta["number"],
            )
            sections.append(section)
            current = section
            order += SECTION_ORDER_STEP
            continue

        # outline
        if current:
            current.outline.append(meta["title"])

    for idx, section in enumerate(sections, start=1):
        # 为每个章节生成稳定的chapter_id，便于后续引用
        section.chapter_id = f"S{idx}"

    return sections


def _classify_line(stripped: str, indent: int) -> Optional[dict]:
    """
    根据缩进与符号分类行。

    借助正则判断当前行是章节标题、提纲还是普通列表项，
    并衍生 depth/slug/number 等派生信息。

    参数:
        stripped: 去除前后空格后的原始行。
        indent: 行首空格数量，用于区分层级。

    返回:
        dict | None: 识别后的元数据；无法识别时返回None。
    """

    heading_match = heading_pattern.fullmatch(stripped)
    if heading_match:
        level = len(heading_match.group("marker"))
        payload = _strip_markup(heading_match.group("title").strip())
        title_info = _split_number(payload)
        slug = _build_slug(title_info["number"], title_info["title"])
        return {
            "is_section": level <= 2,
            "depth": level,
            "title": title_info["display"],
            "raw": payload,
            "number": title_info["number"],
            "slug": slug,
        }

    bullet_match = bullet_pattern.fullmatch(stripped)
    if bullet_match:
        payload = _strip_markup(bullet_match.group("title").strip())
        title_info = _split_number(payload)
        slug = _build_slug(title_info["number"], title_info["title"])
        is_section = indent <= 1
        depth = 1 if indent <= 1 else 2
        return {
            "is_section": is_section,
            "depth": depth,
            "title": title_info["display"],
            "raw": payload,
            "number": title_info["number"],
            "slug": slug,
        }

    # 兼容“1.1 ...”没有前缀符号的行
    number_match = number_pattern.fullmatch(stripped)
    if number_match and number_match.group("label"):
        payload = stripped
        title = number_match.group("label").strip()
        number = number_match.group("num")
        slug = _build_slug(number, title)
        is_section = indent == 0 and number.count(".") <= 1
        depth = 1 if is_section else 2
        display = f"{number} {title}" if title else number
        return {
            "is_section": is_section,
            "depth": depth,
            "title": display,
            "raw": payload,
            "number": number,
            "slug": slug,
        }

    return None


def _strip_markup(text: str) -> str:
    """去除包裹的**、__等强调标记，避免干扰标题匹配。"""
    if text.startswith(("**", "__")) and text.endswith(("**", "__")) and len(text) > 4:
        return text[2:-2].strip()
    return text


def _split_number(payload: str) -> dict:
    """
    拆分编号与标题。

    例如 `1.2 市场趋势` 会被拆成 number=1.2、label=市场趋势，
    并提供 display 用于回填标题。

    参数:
        payload: 原始标题字符串。

    返回:
        dict: 包含 number/title/display。
    """
    match = number_pattern.fullmatch(payload)
    number = match.group("num") if match else ""
    label = match.group("label") if match else payload
    label = (label or "").strip()
    display = f"{number} {label}".strip() if number else label or payload
    title_core = label or payload
    return {
        "number": number,
        "title": title_core,
        "display": display,
    }


def _build_slug(number: str, title: str) -> str:
    """
    根据编号/标题生成锚点，优先复用编号，缺失时对标题slug化。

    参数:
        number: 章节编号。
        title: 标题文本。

    返回:
        str: 形如 `section-1-0` 的slug。
    """
    if number:
        token = number.replace(".", "-")
    else:
        token = _slugify_text(title)
    token = token or "section"
    return f"section-{token}"


def _slugify_text(text: str) -> str:
    """
    对任意文本做降噪与转写，得到URL友好的slug片段。

    会规整大小写、移除特殊符号并保留汉字，确保锚点可读。
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.replace("·", "-").replace(" ", "-")
    text = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-").lower()


def _ensure_unique_slug(slug: str, used: set) -> str:
    """
    若slug重复则自动追加序号，直到在used集合中唯一。

    通过 `-2/-3...` 的方式保证相同标题不会产生重复锚点。

    参数:
        slug: 初始slug。
        used: 已使用集合。

    返回:
        str: 去重后的slug。
    """
    if slug not in used:
        used.add(slug)
        return slug
    base = slug
    idx = 2
    while slug in used:
        slug = f"{base}-{idx}"
        idx += 1
    used.add(slug)
    return slug


__all__ = ["TemplateSection", "parse_template_sections"]
