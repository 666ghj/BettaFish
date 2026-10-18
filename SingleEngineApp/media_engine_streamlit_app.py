"""
Streamlit Web界面
为Media Agent提供友好的Web界面
"""

import os
import sys
import streamlit as st
import locale
from loguru import logger

# 设置UTF-8编码环境
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

# 设置系统编码
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'C.UTF-8')
    except locale.Error:
        pass

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from MediaEngine import DeepSearchAgent, AnspireSearchAgent, Settings
from config import settings
from SingleEngineApp.research_runner import (
    read_launch_params,
    report_launch_failure,
    run_streamlit_research,
    should_start_research,
)


def main():
    """主函数"""
    st.set_page_config(
        page_title="Media Agent",
        page_icon="",
        layout="wide"
    )

    st.title("Media Agent")
    st.markdown("具备强大多模态能力的AI代理")
    st.markdown("突破传统文本交流限制，广泛的浏览抖音、快手、小红书的视频、图文、直播")
    st.markdown("使用现代化搜索引擎提供的诸如日历卡、天气卡、股票卡等多模态结构化信息进一步增强能力")

    # 检查URL参数
    query_params, auto_query, auto_search, run_id = read_launch_params(st)

    # ----- 配置被硬编码 -----
    # 强制使用 Gemini
    model_name = settings.MEDIA_ENGINE_MODEL_NAME or "gemini-2.5-pro"
    # 默认高级配置
    max_reflections = 2
    max_content_length = 20000

    # 简化的研究查询展示区域

    # 如果有自动查询，使用它作为默认值，否则显示占位符
    display_query = auto_query if auto_query else "等待从主页面接收分析内容..."

    # 只读的查询展示区域
    st.text_area(
        "当前查询",
        value=display_query,
        height=100,
        disabled=True,
        help="查询内容由主页面的搜索框控制",
        label_visibility="hidden"
    )

    # 自动搜索逻辑
    query = auto_query
    start_research = should_start_research(st, query, auto_search, run_id)

    # 验证配置
    if start_research:
        if not query.strip():
            report_launch_failure(
                st, run_id=run_id, engine="media", query=query, message="请输入研究查询"
            )
            return

        # 由于强制使用Gemini，检查相关的API密钥
        if not settings.MEDIA_ENGINE_API_KEY:
            report_launch_failure(
                st,
                run_id=run_id,
                engine="media",
                query=query,
                message="请在您的环境变量中设置MEDIA_ENGINE_API_KEY",
            )
            return

        # 自动使用配置文件中的API密钥
        engine_key = settings.MEDIA_ENGINE_API_KEY
        bocha_key = settings.BOCHA_WEB_SEARCH_API_KEY
        ansire_key = settings.ANSPIRE_API_KEY

        # 构建 Settings（pydantic_settings风格，优先大写环境变量）
        if settings.SEARCH_TOOL_TYPE == "BochaAPI":
            if not bocha_key:
                report_launch_failure(
                    st,
                    run_id=run_id,
                    engine="media",
                    query=query,
                    message="请在您的环境变量中设置BOCHA_WEB_SEARCH_API_KEY",
                )
                return
            logger.info("使用Bocha搜索API密钥")
            config = Settings(
                MEDIA_ENGINE_API_KEY=engine_key,
                MEDIA_ENGINE_BASE_URL=settings.MEDIA_ENGINE_BASE_URL,
                MEDIA_ENGINE_MODEL_NAME=model_name,
                SEARCH_TOOL_TYPE="BochaAPI",
                BOCHA_WEB_SEARCH_API_KEY=bocha_key,
                MAX_REFLECTIONS=max_reflections,
                SEARCH_CONTENT_MAX_LENGTH=max_content_length,
                OUTPUT_DIR="media_engine_streamlit_reports",
            )
        elif settings.SEARCH_TOOL_TYPE == "AnspireAPI":
            if not ansire_key:
                report_launch_failure(
                    st,
                    run_id=run_id,
                    engine="media",
                    query=query,
                    message="请在您的环境变量中设置ANSPIRE_API_KEY",
                )
                return
            logger.info("使用Anspire搜索API密钥")
            config = Settings(
                MEDIA_ENGINE_API_KEY=engine_key,
                MEDIA_ENGINE_BASE_URL=settings.MEDIA_ENGINE_BASE_URL,
                MEDIA_ENGINE_MODEL_NAME=model_name,
                SEARCH_TOOL_TYPE="AnspireAPI",
                ANSPIRE_API_KEY=ansire_key,
                MAX_REFLECTIONS=max_reflections,
                SEARCH_CONTENT_MAX_LENGTH=max_content_length,
                OUTPUT_DIR="media_engine_streamlit_reports",
            )
        else:
            report_launch_failure(
                st,
                run_id=run_id,
                engine="media",
                query=query,
                message=f"未知的搜索工具类型: {settings.SEARCH_TOOL_TYPE}",
            )
            return

        # 执行研究
        execute_research(query, config, run_id)


def execute_research(query: str, config: Settings, run_id: str = ''):
    """执行研究"""
    def build_agent(media_config):
        if media_config.SEARCH_TOOL_TYPE == "BochaAPI":
            return DeepSearchAgent(media_config)
        if media_config.SEARCH_TOOL_TYPE == "AnspireAPI":
            return AnspireSearchAgent(media_config)
        raise ValueError(f"未知的搜索工具类型: {media_config.SEARCH_TOOL_TYPE}")

    return run_streamlit_research(
        st_module=st,
        query=query,
        config=config,
        run_id=run_id,
        engine="media",
        agent_factory=build_agent,
        display_results=display_results,
        app_name="Media Engine Streamlit App",
    )


def display_results(agent: DeepSearchAgent, final_report: str):
    """显示研究结果"""
    st.header("研究结果")

    # 结果标签页（已移除下载选项）
    tab1, tab2 = st.tabs(["研究小结", "引用信息"])

    with tab1:
        st.markdown(final_report)

    with tab2:
        # 段落详情
        st.subheader("段落详情")
        for i, paragraph in enumerate(agent.state.paragraphs):
            with st.expander(f"段落 {i + 1}: {paragraph.title}"):
                st.write("**预期内容:**", paragraph.content)
                st.write("**最终内容:**", paragraph.research.latest_summary[:300] + "..."
                if len(paragraph.research.latest_summary) > 300
                else paragraph.research.latest_summary)
                st.write("**搜索次数:**", paragraph.research.get_search_count())
                st.write("**反思次数:**", paragraph.research.reflection_iteration)

        # 搜索历史
        st.subheader("搜索历史")
        all_searches = []
        for paragraph in agent.state.paragraphs:
            all_searches.extend(paragraph.research.search_history)

        if all_searches:
            for i, search in enumerate(all_searches):
                query_label = search.query if search.query else "未记录查询"
                with st.expander(f"搜索 {i + 1}: {query_label}"):
                    paragraph_title = getattr(search, "paragraph_title", "") or "未标注段落"
                    search_tool = getattr(search, "search_tool", "") or "未标注工具"
                    has_result = getattr(search, "has_result", True)
                    st.write("**段落:**", paragraph_title)
                    st.write("**使用的工具:**", search_tool)
                    preview = search.content or ""
                    if not isinstance(preview, str):
                        preview = str(preview)
                    if len(preview) > 200:
                        preview = preview[:200] + "..."
                    st.write("**URL:**", search.url or "无")
                    st.write("**标题:**", search.title or "无")
                    st.write("**内容预览:**", preview if preview else "无可用内容")
                    if not has_result:
                        st.info("本次搜索未返回结果")
                    if search.score:
                        st.write("**相关度评分:**", search.score)


if __name__ == "__main__":
    main()
