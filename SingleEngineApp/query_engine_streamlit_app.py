"""
Streamlit Web界面
为Query Agent提供友好的Web界面
"""

import os
import sys
import streamlit as st
import locale

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

from QueryEngine import DeepSearchAgent, Settings
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
        page_title="Query Agent",
        page_icon="",
        layout="wide"
    )

    st.title("Query Agent")
    st.markdown("具备强大网页搜索能力的AI代理")
    st.markdown("广度爬取官方报道与新闻，注重国内外资源相结合理解舆情")

    # 检查URL参数
    query_params, auto_query, auto_search, run_id = read_launch_params(st)

    # ----- 配置被硬编码 -----
    # 强制使用 DeepSeek
    model_name = settings.QUERY_ENGINE_MODEL_NAME or "deepseek-chat"
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
                st, run_id=run_id, engine="query", query=query, message="请输入研究查询"
            )
            return

        # 由于强制使用DeepSeek，检查相关的API密钥
        if not settings.QUERY_ENGINE_API_KEY:
            report_launch_failure(
                st,
                run_id=run_id,
                engine="query",
                query=query,
                message="请在您的环境变量中设置QUERY_ENGINE_API_KEY",
            )
            return
        if not settings.TAVILY_API_KEY:
            report_launch_failure(
                st,
                run_id=run_id,
                engine="query",
                query=query,
                message="请在您的环境变量中设置TAVILY_API_KEY",
            )
            return

        # 自动使用配置文件中的API密钥
        engine_key = settings.QUERY_ENGINE_API_KEY
        tavily_key = settings.TAVILY_API_KEY

        # 创建配置
        config = Settings(
            QUERY_ENGINE_API_KEY=engine_key,
            QUERY_ENGINE_BASE_URL=settings.QUERY_ENGINE_BASE_URL,
            QUERY_ENGINE_MODEL_NAME=model_name,
            TAVILY_API_KEY=tavily_key,
            MAX_REFLECTIONS=max_reflections,
            SEARCH_CONTENT_MAX_LENGTH=max_content_length,
            OUTPUT_DIR="query_engine_streamlit_reports"
        )

        # 执行研究
        execute_research(query, config, run_id)


def execute_research(query: str, config: Settings, run_id: str = ''):
    """执行研究"""
    return run_streamlit_research(
        st_module=st,
        query=query,
        config=config,
        run_id=run_id,
        engine="query",
        agent_factory=DeepSearchAgent,
        display_results=display_results,
        app_name="Query Engine Streamlit App",
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
                with st.expander(f"搜索 {i + 1}: {search.query}"):
                    st.write("**URL:**", search.url)
                    st.write("**标题:**", search.title)
                    st.write("**内容预览:**",
                             search.content[:200] + "..." if len(search.content) > 200 else search.content)
                    if search.score:
                        st.write("**相关度评分:**", search.score)


if __name__ == "__main__":
    main()
