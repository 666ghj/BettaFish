# test_integration.py
# 集成测试 - 由总负责人维护
# 验证三条开发线合并后的整体功能

import pytest


class TestToolLayer:
    """A组交付验收：工具层测试"""

    def test_tools_importable(self):
        """所有 tool 函数可以正常 import"""
        from agno_tools import (
            search_weibo, search_forum, search_news,
            analyze_sentiment, optimize_keywords,
        )
        assert all([search_weibo, search_forum, search_news, analyze_sentiment, optimize_keywords])

    def test_sentiment_tool_basic(self):
        """情感分析工具基础功能"""
        from agno_tools import analyze_sentiment
        results = analyze_sentiment(["今天天气真好", "这件事太糟糕了"])
        assert len(results) == 2
        assert results[0]["sentiment"] in ["positive", "negative", "neutral"]
        assert 0 <= results[0]["confidence"] <= 1

    def test_keyword_tool_basic(self):
        """关键词优化工具基础功能"""
        from agno_tools import optimize_keywords
        keywords = optimize_keywords("特斯拉召回事件", num_keywords=3)
        assert isinstance(keywords, list)
        assert len(keywords) >= 1

    def test_db_query_tool_basic(self):
        """数据库查询工具基础功能（需要真实数据库连接）"""
        pytest.skip("需要数据库连接，在集成环境中运行")


class TestAgentLayer:
    """B组交付验收：Agent层测试"""

    def test_agents_instantiable(self):
        """三个核心 Agent 可以无报错实例化"""
        from agno_agents import create_insight_agent, create_media_agent, create_query_agent
        insight = create_insight_agent()
        media = create_media_agent()
        query = create_query_agent()
        assert insight.name == "InsightAgent"
        assert media.name == "MediaAgent"
        assert query.name == "QueryAgent"

    def test_insight_agent_run(self):
        """InsightAgent 完整运行测试（需要真实 API Key）"""
        pytest.skip("需要 API Key，在集成环境中运行")

    def test_agent_stream_support(self):
        """Agent 支持流式输出"""
        from agno_agents import create_insight_agent
        agent = create_insight_agent()
        assert agent.stream is True


class TestTeamLayer:
    """C组交付验收：编排层测试"""

    def test_team_instantiable(self):
        """Opinion Team 可以无报错实例化"""
        from agno_team.opinion_team import create_opinion_team
        team = create_opinion_team()
        assert team.name == "微舆舆情分析团队"

    def test_full_pipeline(self):
        """完整流水线运行测试（需要所有 API Key）"""
        pytest.skip("需要完整环境，在集成环境中运行")


class TestAppLayer:
    """应用入口测试"""

    def test_app_starts(self):
        """Flask app 可以正常创建"""
        from main import app
        assert app is not None

    def test_health_endpoint(self):
        """健康检查接口正常"""
        from main import app
        client = app.test_client()
        response = client.get('/health')
        assert response.status_code == 200
        assert response.get_json()["status"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
