"""
Streamlit Web界面
为Query Agent提供友好的Web界面
"""

import os
import sys
import streamlit as st
from datetime import datetime
import json
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

from QueryEngine import DeepSearchAgent, Config
from config import QUERY_ENGINE_API_KEY, QUERY_ENGINE_BASE_URL, QUERY_ENGINE_MODEL_NAME, TAVILY_API_KEY


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
    try:
        # 尝试使用新版本的query_params
        query_params = st.query_params
        auto_query = query_params.get('query', '')
        auto_search = query_params.get('auto_search', 'false').lower() == 'true'
    except AttributeError:
        # 兼容旧版本
        query_params = st.experimental_get_query_params()
        auto_query = query_params.get('query', [''])[0]
        auto_search = query_params.get('auto_search', ['false'])[0].lower() == 'true'

    # ----- 配置被硬编码 -----
    # 强制使用 DeepSeek
    model_name = QUERY_ENGINE_MODEL_NAME or "deepseek-chat"
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
    start_research = False
    query = auto_query
    
    if auto_search and auto_query and 'auto_search_executed' not in st.session_state:
        st.session_state.auto_search_executed = True
        start_research = True
    elif auto_query and not auto_search:
        st.warning("等待搜索启动信号...")

    # 验证配置
    if start_research:
        if not query.strip():
            st.error("请输入研究查询")
            return

        # 由于强制使用DeepSeek，检查相关的API密钥
        if not QUERY_ENGINE_API_KEY:
            st.error("请在您的配置文件(config.py)中设置QUERY_ENGINE_API_KEY")
            return
        # 本地搜索不需要API Key，但仍支持Tavily API作为可选
        engine_key = QUERY_ENGINE_API_KEY
        tavily_key = TAVILY_API_KEY if TAVILY_API_KEY else None
        if not tavily_key:
            st.info("ℹ️ 未配置Tavily API Key，将使用本地搜索服务")

        # 创建配置
        config = Config(
            llm_api_key=engine_key,
            llm_base_url=QUERY_ENGINE_BASE_URL,
            llm_model_name=model_name,
            tavily_api_key=tavily_key,
            max_reflections=max_reflections,
            max_content_length=max_content_length,
            output_dir="query_engine_streamlit_reports"
        )

        # 执行研究
        execute_research(query, config)


def execute_research(query: str, config: Config):
    """执行研究"""
    try:
        # 创建进度条
        progress_bar = st.progress(0)
        status_text = st.empty()

        # 初始化Agent
        status_text.text("正在初始化Agent...")
        agent = DeepSearchAgent(config)
        st.session_state.agent = agent

        progress_bar.progress(10)

        # 生成报告结构
        status_text.text("正在生成报告结构...")
        agent._generate_report_structure(query)
        progress_bar.progress(20)

        # 处理段落
        total_paragraphs = len(agent.state.paragraphs)
        for i in range(total_paragraphs):
            status_text.text(f"正在处理段落 {i + 1}/{total_paragraphs}: {agent.state.paragraphs[i].title}")

            # 初始搜索和总结
            agent._initial_search_and_summary(i)
            progress_value = 20 + (i + 0.5) / total_paragraphs * 60
            progress_bar.progress(int(progress_value))

            # 反思循环
            agent._reflection_loop(i)
            agent.state.paragraphs[i].research.mark_completed()

            progress_value = 20 + (i + 1) / total_paragraphs * 60
            progress_bar.progress(int(progress_value))

        # 生成最终报告
        status_text.text("正在生成最终报告...")
        final_report = agent._generate_final_report()
        progress_bar.progress(90)

        # 保存报告
        status_text.text("正在保存报告...")
        agent._save_report(final_report)
        progress_bar.progress(100)

        status_text.text("研究完成！")

        # 显示结果
        display_results(agent, final_report)

    except Exception as e:
        st.error(f"研究过程中发生错误: {str(e)}")


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
