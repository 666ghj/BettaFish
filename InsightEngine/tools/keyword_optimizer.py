"""
关键词优化中间件
使用LLM将Agent生成的搜索词优化为更适合舆情数据库查询的关键词。
支持 OpenAI / Anthropic（含 Claude Code OAuth）双后端。
"""

import json
import sys
import os
from typing import List, Dict, Any
from dataclasses import dataclass

# 添加项目根目录到Python路径以导入config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from config import settings
from loguru import logger

# 添加utils目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
utils_dir = os.path.join(root_dir, 'utils')
if utils_dir not in sys.path:
    sys.path.append(utils_dir)

from retry_helper import with_graceful_retry, SEARCH_API_RETRY_CONFIG
from utils.llm_provider import LLMClient

@dataclass
class KeywordOptimizationResponse:
    """关键词优化响应"""
    original_query: str
    optimized_keywords: List[str]
    reasoning: str
    success: bool
    error_message: str = ""

class KeywordOptimizer:
    """
    关键词优化器
    使用硅基流动的Qwen3模型将Agent生成的搜索词优化为更贴近真实舆情的关键词
    """
    
    def __init__(self, api_key: str = None, base_url: str = None, model_name: str = None):
        """
        初始化关键词优化器
        
        Args:
            api_key: API密钥或OAuth token，如果不提供则从配置文件读取
            base_url: 接口基础地址，默认使用配置文件中的地址
            model_name: 模型名称，如果不提供则从配置文件读取
        """
        self.api_key = api_key or settings.KEYWORD_OPTIMIZER_API_KEY

        if not self.api_key:
            raise ValueError("未找到API密钥，请在配置文件中设置KEYWORD_OPTIMIZER_API_KEY")

        self.base_url = base_url or settings.KEYWORD_OPTIMIZER_BASE_URL
        self.model = model_name or settings.KEYWORD_OPTIMIZER_MODEL_NAME

        # 使用统一 LLM 客户端（自动支持 OpenAI / Anthropic OAuth）
        self.llm_client = LLMClient(
            api_key=self.api_key,
            model_name=self.model,
            base_url=self.base_url,
            engine_name="Keyword Optimizer",
            prepend_time=False,
        )
    
    def optimize_keywords(self, original_query: str, context: str = "") -> KeywordOptimizationResponse:
        """
        优化搜索关键词
        
        Args:
            original_query: Agent生成的原始搜索查询
            context: 额外的上下文信息（如段落标题、内容描述等）
            
        Returns:
            KeywordOptimizationResponse: 优化后的关键词列表
        """
        logger.info(f"🔍 关键词优化中间件: 处理查询 '{original_query}'")
        
        try:
            # 构建优化prompt
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(original_query, context)
            
            # 调用Qwen API
            response = self._call_qwen_api(system_prompt, user_prompt)
            
            if response["success"]:
                # 解析响应
                content = response["content"]
                try:
                    # 尝试解析JSON格式的响应
                    if content.strip().startswith('{'):
                        parsed = json.loads(content)
                        keywords = parsed.get("keywords", [])
                        reasoning = parsed.get("reasoning", "")
                    else:
                        # 如果不是JSON格式，尝试从文本中提取关键词
                        keywords = self._extract_keywords_from_text(content)
                        reasoning = content
                    
                    # 验证关键词质量
                    validated_keywords = self._validate_keywords(keywords)
                    
                    logger.info(
                        f"✅ 优化成功: {len(validated_keywords)}个关键词" +
                        ("" if not validated_keywords else "\n" +
                         "\n".join([f"   {i}. '{k}'" for i, k in enumerate(validated_keywords, 1)]))
                    )
                        
                    
                    
                    return KeywordOptimizationResponse(
                        original_query=original_query,
                        optimized_keywords=validated_keywords,
                        reasoning=reasoning,
                        success=True
                    )
                
                except Exception as e:
                    logger.exception(f"⚠️ 解析响应失败，使用备用方案: {str(e)}")
                    # 备用方案：从原始查询中提取关键词
                    fallback_keywords = self._fallback_keyword_extraction(original_query)
                    return KeywordOptimizationResponse(
                        original_query=original_query,
                        optimized_keywords=fallback_keywords,
                        reasoning="API响应解析失败，使用备用关键词提取",
                        success=True
                    )
            else:
                logger.error(f"❌ API调用失败: {response['error']}")
                # 使用备用方案
                fallback_keywords = self._fallback_keyword_extraction(original_query)
                return KeywordOptimizationResponse(
                    original_query=original_query,
                    optimized_keywords=fallback_keywords,
                    reasoning="API调用失败，使用备用关键词提取",
                    success=True,
                    error_message=response['error']
                )
                
        except Exception as e:
            logger.error(f"❌ 关键词优化失败: {str(e)}")
            # 最终备用方案
            fallback_keywords = self._fallback_keyword_extraction(original_query)
            return KeywordOptimizationResponse(
                original_query=original_query,
                optimized_keywords=fallback_keywords,
                reasoning="系统错误，使用备用关键词提取",
                success=False,
                error_message=str(e)
            )
    
    def _build_system_prompt(self) -> str:
        """构建系统prompt"""
        return """你是一位专业的舆情数据挖掘专家。你的任务是将用户提供的搜索查询优化为更适合在社交媒体舆情数据库中查找的关键词。

**核心原则**：
1. **贴近网民语言**：使用普通网友在社交媒体上会使用的词汇
2. **避免专业术语**：不使用"舆情"、"传播"、"倾向"、"展望"等官方词汇
3. **简洁具体**：每个关键词要非常简洁明了，便于数据库匹配
4. **情感丰富**：包含网民常用的情感表达词汇
5. **数量控制**：最少提供10个关键词，最多提供20个关键词
6. **避免重复**：不要脱离初始查询的主题

**重要提醒**：每个关键词都必须是一个不可分割的独立词条，严禁在词条内部包含空格。例如，应使用 "雷军班争议" 而不是错误的 "雷军班 争议"。


**输出格式**：
请以JSON格式返回结果：
{
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "reasoning": "选择这些关键词的理由"
}

**示例**：
输入："武汉大学舆情管理 未来展望 发展趋势"
输出：
{
    "keywords": ["武大", "武汉大学", "学校管理", "武大教育"],
    "reasoning": "选择'武大'和'武汉大学'作为核心词汇，这是网民最常使用的称呼；'学校管理'比'舆情管理'更贴近日常表达；避免使用'未来展望'、'发展趋势'等网民很少使用的专业术语"
}"""

    def _build_user_prompt(self, original_query: str, context: str) -> str:
        """构建用户prompt"""
        prompt = f"请将以下搜索查询优化为适合舆情数据库查询的关键词：\n\n原始查询：{original_query}"
        
        if context:
            prompt += f"\n\n上下文信息：{context}"
        
        prompt += "\n\n请记住：要使用网民在社交媒体上真实使用的词汇，避免官方术语和专业词汇。"
        
        return prompt
    
    @with_graceful_retry(SEARCH_API_RETRY_CONFIG, default_return={"success": False, "error": "关键词优化服务暂时不可用"})
    def _call_qwen_api(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """调用 LLM API（通过统一客户端，自动支持 OpenAI / Anthropic）"""
        try:
            content = self.llm_client.invoke(
                system_prompt,
                user_prompt,
                temperature=0.7,
            )

            if content:
                return {"success": True, "content": content}
            else:
                return {"success": False, "error": "API返回格式异常"}
        except Exception as e:
            return {"success": False, "error": f"API调用异常: {str(e)}"}
    
    def _extract_keywords_from_text(self, text: str) -> List[str]:
        """从文本中提取关键词（当JSON解析失败时使用）"""
        # 简单的关键词提取逻辑
        lines = text.split('\n')
        keywords = []
        
        for line in lines:
            line = line.strip()
            # 查找可能的关键词
            if '：' in line or ':' in line:
                parts = line.split('：') if '：' in line else line.split(':')
                if len(parts) > 1:
                    potential_keywords = parts[1].strip()
                    # 尝试分割关键词
                    if '、' in potential_keywords:
                        keywords.extend([k.strip() for k in potential_keywords.split('、')])
                    elif ',' in potential_keywords:
                        keywords.extend([k.strip() for k in potential_keywords.split(',')])
                    else:
                        keywords.append(potential_keywords)
        
        # 如果没有找到，尝试其他方法
        if not keywords:
            # 查找引号中的内容
            import re
            quoted_content = re.findall(r'["""\'](.*?)["""\']', text)
            keywords.extend(quoted_content)
        
        # 清理和验证关键词
        cleaned_keywords = []
        for keyword in keywords[:20]:  # 最多20个
            keyword = keyword.strip().strip('"\'""''')
            if keyword and len(keyword) <= 20:  # 合理长度
                cleaned_keywords.append(keyword)
        
        return cleaned_keywords[:20]
    
    def _validate_keywords(self, keywords: List[str]) -> List[str]:
        """验证和清理关键词"""
        validated = []
        
        # 不良关键词（过于专业或官方）
        bad_keywords = {
            '态度分析', '公众反应', '情绪倾向',
            '未来展望', '发展趋势', '战略规划', '政策导向', '管理机制'
        }
        
        for keyword in keywords:
            if isinstance(keyword, str):
                keyword = keyword.strip().strip('"\'""''')
                
                # 基本验证
                if (keyword and 
                    len(keyword) <= 20 and 
                    len(keyword) >= 1 and
                    not any(bad_word in keyword for bad_word in bad_keywords)):
                    validated.append(keyword)
        
        return validated[:20]  # 最多返回20个关键词
    
    def _fallback_keyword_extraction(self, original_query: str) -> List[str]:
        """备用关键词提取方案"""
        # 简单的关键词提取逻辑
        # 移除常见的无用词汇
        stop_words = {'、'}
        
        # 分割查询
        import re
        # 按空格、标点分割
        tokens = re.split(r'[\s，。！？；：、]+', original_query)
        
        keywords = []
        for token in tokens:
            token = token.strip()
            if token and token not in stop_words and len(token) >= 2:
                keywords.append(token)
        
        # 如果没有有效关键词，使用原始查询的第一个词
        if not keywords:
            first_word = original_query.split()[0] if original_query.split() else original_query
            keywords = [first_word] if first_word else ["热门"]
        
        return keywords[:20]

# 全局实例
keyword_optimizer = KeywordOptimizer()
