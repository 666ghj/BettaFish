# Tool Integration Interfaces

## Overview

This document defines the standardized interfaces for integrating external tools and services with the modernized BettaFish system using LangChain tools within DBOS durable workflows. These interfaces ensure consistent communication, error handling, and data exchange across all tool integrations while providing enterprise-grade reliability through DBOS and flexible tool orchestration through LangChain.

## Tool Interface Architecture

### 1. LangChain Tool Interface with DBOS

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union, Type
from dataclasses import dataclass
from enum import Enum
import asyncio
from langchain_core.tools import BaseTool as LangChainBaseTool
from langchain_core.pydantic_v1 import BaseModel, Field
from dbos import DBOS

class ToolStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"

@dataclass
class ToolConfig:
    """Configuration for tool instances"""
    name: str
    version: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    rate_limit: Optional[Dict[str, Any]] = None
    custom_params: Dict[str, Any] = None

@dataclass
class ToolResult:
    """Standardized tool result format"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    execution_time: Optional[float] = None
    tokens_used: Optional[int] = None
    rate_limit_info: Optional[Dict[str, Any]] = None

class BettaFishTool(LangChainBaseTool):
    """LangChain-compatible tool with DBOS durability"""

    name: str
    description: str
    config: ToolConfig
    status: ToolStatus = ToolStatus.UNAVAILABLE

    def __init__(self, config: ToolConfig):
        super().__init__()
        self.config = config
        self.status = ToolStatus.UNAVAILABLE
        self.last_health_check = None

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the tool connection"""
        pass

    @abstractmethod
    async def health_check(self) -> ToolStatus:
        """Check tool health and availability"""
        pass

    @abstractmethod
    async def _arun(self, *args, **kwargs) -> str:
        """LangChain async run method with DBOS durability"""
        pass

    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """Execute the tool with given parameters"""
        start_time = asyncio.get_event_loop().time()

        try:
            # Validate parameters
            if not await self.validate_parameters(parameters):
                return ToolResult(
                    success=False,
                    error="Invalid parameters"
                )

            # Execute via LangChain interface
            result_str = await self._arun(**parameters)
            execution_time = asyncio.get_event_loop().time() - start_time

            # Parse result (assuming JSON structure)
            try:
                result_data = json.loads(result_str) if result_str else {}
            except json.JSONDecodeError:
                result_data = {"content": result_str}

            return ToolResult(
                success=True,
                data=result_data,
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = asyncio.get_event_loop().time() - start_time
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Return list of tool capabilities"""
        pass

    async def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Validate input parameters"""
        return True

    async def cleanup(self) -> None:
        """Cleanup resources"""
        pass

    @DBOS.step()
    async def durable_execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """DBOS-durable tool execution"""
        # DBOS ensures this execution is durable and recoverable
        return await self.execute(parameters)
```

### 2. LangChain Tool Registry with DBOS

```python
from typing import Dict, Type, List
import importlib
from pathlib import Path
from langchain_core.tools import BaseTool as LangChainBaseTool
from dbos import DBOS

class ToolRegistry:
    """Registry for managing LangChain tool instances with DBOS"""

    def __init__(self):
        self._tools: Dict[str, BettaFishTool] = {}
        self._tool_classes: Dict[str, Type[BettaFishTool]] = {}

    def register_tool_class(self, name: str, tool_class: Type[BettaFishTool]) -> None:
        """Register a tool class"""
        self._tool_classes[name] = tool_class

    @DBOS.step()
    async def create_tool(self, name: str, config: ToolConfig) -> BettaFishTool:
        """Create and initialize a tool instance with DBOS durability"""
        if name not in self._tool_classes:
            raise ValueError(f"Tool class '{name}' not registered")

        tool_class = self._tool_classes[name]
        tool = tool_class(config)

        if await tool.initialize():
            self._tools[config.name] = tool
            # DBOS ensures tool registration is durable
            await self._persist_tool_registration(config.name, tool)
            return tool
        else:
            raise RuntimeError(f"Failed to initialize tool '{config.name}'")

    def get_tool(self, name: str) -> Optional[BettaFishTool]:
        """Get a tool instance by name"""
        return self._tools.get(name)

    def get_langchain_tools(self) -> List[LangChainBaseTool]:
        """Get all tools as LangChain tool instances"""
        return list(self._tools.values())

    def list_tools(self) -> List[str]:
        """List all registered tool names"""
        return list(self._tools.keys())

    @DBOS.step()
    async def health_check_all(self) -> Dict[str, ToolStatus]:
        """Health check all tools with DBOS durability"""
        results = {}
        for name, tool in self._tools.items():
            status = await tool.health_check()
            results[name] = status
            # DBOS ensures health check results are durable
            await self._record_health_status(name, status)
        return results

    @DBOS.step()
    async def cleanup_all(self) -> None:
        """Cleanup all tools with DBOS durability"""
        for tool in self._tools.values():
            await tool.cleanup()
        self._tools.clear()
        # DBOS ensures cleanup is recorded durably
        await self._record_cleanup_event()

    @DBOS.step()
    async def _persist_tool_registration(self, name: str, tool: BettaFishTool) -> None:
        """Persist tool registration durably"""
        registration_data = {
            'tool_name': name,
            'tool_class': tool.__class__.__name__,
            'config': tool.config.__dict__,
            'registered_at': datetime.now()
        }
        # DBOS ensures this is stored durably
        DBOS.set_event('tool_registry', f'registration_{name}', registration_data)

    @DBOS.step()
    async def _record_health_status(self, name: str, status: ToolStatus) -> None:
        """Record tool health status durably"""
        health_data = {
            'tool_name': name,
            'status': status,
            'checked_at': datetime.now()
        }
        DBOS.set_event('tool_health', f'health_{name}', health_data)

    @DBOS.step()
    async def _record_cleanup_event(self) -> None:
        """Record cleanup event durably"""
        cleanup_data = {
            'cleanup_time': datetime.now(),
            'tools_cleaned': list(self._tools.keys())
        }
        DBOS.set_event('tool_registry', 'cleanup', cleanup_data)

# Global tool registry instance
tool_registry = ToolRegistry()
```

## Search Tool Interfaces

### 1. Tavily Search LangChain Tool

```python
import aiohttp
import asyncio
from typing import Dict, List, Any, Optional, Type
from langchain_core.pydantic_v1 import BaseModel, Field
import json

class TavilySearchInput(BaseModel):
    """Input schema for Tavily search tool"""
    query: str = Field(description="Search query")
    max_results: Optional[int] = Field(default=10, description="Maximum results to return")
    search_depth: Optional[str] = Field(default="basic", description="Search depth: basic or advanced")
    include_raw_content: Optional[bool] = Field(default=False, description="Include raw content")
    include_domains: Optional[List[str]] = Field(default_factory=list, description="Domains to include")
    exclude_domains: Optional[List[str]] = Field(default_factory=list, description="Domains to exclude")
    days: Optional[int] = Field(default=7, description="Days to search back")

class TavilySearchTool(BettaFishTool):
    """Tavily search API integration as LangChain tool"""

    name: str = "tavily_search"
    description: str = "Search the web using Tavily API for comprehensive, AI-optimized results"
    args_schema: Type[BaseModel] = TavilySearchInput

    def __init__(self, config: ToolConfig):
        super().__init__(config)
        self.api_key = config.api_key
        self.base_url = config.base_url or "https://api.tavily.com"
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self) -> bool:
        """Initialize Tavily connection"""
        try:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            )
            # Test connection with a simple search
            test_result = await self._make_request({
                "api_key": self.api_key,
                "query": "test",
                "max_results": 1
            })
            self.status = ToolStatus.AVAILABLE
            return True
        except Exception as e:
            self.status = ToolStatus.ERROR
            return False

    async def health_check(self) -> ToolStatus:
        """Check Tavily API health"""
        try:
            if not self.session:
                await self.initialize()

            test_result = await self._make_request({
                "api_key": self.api_key,
                "query": "health check",
                "max_results": 1
            })
            self.status = ToolStatus.AVAILABLE
            return self.status
        except Exception:
            self.status = ToolStatus.ERROR
            return self.status

    async def _arun(self, query: str, max_results: int = 10, search_depth: str = "basic",
                   include_raw_content: bool = False, include_domains: Optional[List[str]] = None,
                   exclude_domains: Optional[List[str]] = None, days: int = 7) -> str:
        """LangChain async run method"""
        parameters = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_raw_content": include_raw_content,
            "include_domains": include_domains or [],
            "exclude_domains": exclude_domains or [],
            "days": days
        }

        result = await self.execute(parameters)

        if result.success:
            return json.dumps(result.data, default=str)
        else:
            raise Exception(f"Tavily search failed: {result.error}")

    async def _make_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to Tavily API"""
        if not self.session:
            raise RuntimeError("Tool not initialized")

        async with self.session.post(
            f"{self.base_url}/search",
            json=data,
            headers={"Content-Type": "application/json"}
        ) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 429:
                self.status = ToolStatus.RATE_LIMITED
                raise Exception("Rate limit exceeded")
            else:
                raise Exception(f"API error: {response.status}")

    def get_capabilities(self) -> List[str]:
        """Return Tavily capabilities"""
        return [
            "web_search",
            "news_search",
            "real_time_search",
            "domain_filtering",
            "content_extraction"
        ]

    async def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Validate search parameters"""
        required_fields = ["query"]
        for field in required_fields:
            if field not in parameters:
                return False

        # Validate query length
        if len(parameters["query"]) > 400:
            return False

        # Validate max_results
        max_results = parameters.get("max_results", 10)
        if not isinstance(max_results, int) or max_results < 1 or max_results > 100:
            return False

        return True

    async def cleanup(self) -> None:
        """Cleanup resources"""
        if self.session:
            await self.session.close()
            self.session = None
```

### 2. Unified Search LangChain Tool

```python
from langchain_core.tools import tool
from typing import List, Optional

class UnifiedSearchTool(BettaFishTool):
    """Unified search tool that can use multiple search providers"""

    name: str = "unified_search"
    description: str = "Unified search interface supporting web, news, and real-time search with fallback providers"

    def __init__(self, config: ToolConfig):
        super().__init__(config)
        self.primary_search: Optional[TavilySearchTool] = None
        self.fallback_search: Optional[BettaFishTool] = None

    async def initialize(self) -> bool:
        """Initialize primary and fallback search tools"""
        # Initialize Tavily as primary
        tavily_config = ToolConfig(
            name="tavily_primary",
            version="1.0",
            api_key=self.config.api_key,
            base_url=self.config.base_url
        )
        self.primary_search = TavilySearchTool(tavily_config)

        if await self.primary_search.initialize():
            self.status = ToolStatus.AVAILABLE
            return True

        self.status = ToolStatus.ERROR
        return False

    @tool("search_web")
    async def search_web(self, query: str, max_results: int = 10, search_depth: str = "basic",
                        include_raw_content: bool = False) -> str:
        """Search the web using primary provider with fallback"""
        parameters = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_raw_content": include_raw_content
        }

        # Try primary search first
        if self.primary_search:
            result = await self.primary_search.execute(parameters)
            if result.success:
                return json.dumps(result.data, default=str)

        # Try fallback if available
        if self.fallback_search:
            try:
                return await self.fallback_search._arun(query=query, max_results=max_results,
                                                       search_depth=search_depth,
                                                       include_raw_content=include_raw_content)
            except Exception:
                pass

        raise Exception("All search providers failed")

    @tool("search_news")
    async def search_news(self, query: str, max_results: int = 10, days: int = 7,
                         include_raw_content: bool = False) -> str:
        """Search for news articles with fallback"""
        parameters = {
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_raw_content": include_raw_content,
            "days": days
        }

        # Try primary search first
        if self.primary_search:
            result = await self.primary_search.execute(parameters)
            if result.success:
                return json.dumps(result.data, default=str)

        # Try fallback if available
        if self.fallback_search:
            try:
                return await self.fallback_search._arun(query=query, max_results=max_results,
                                                       search_depth="advanced",
                                                       include_raw_content=include_raw_content,
                                                       days=days)
            except Exception:
                pass

        raise Exception("All news search providers failed")

    @tool("search_real_time")
    async def search_real_time(self, query: str, max_results: int = 5) -> str:
        """Search for real-time information"""
        parameters = {
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_raw_content": True,
            "days": 1  # Last 24 hours for real-time
        }

        # Try primary search first
        if self.primary_search:
            result = await self.primary_search.execute(parameters)
            if result.success:
                return json.dumps(result.data, default=str)

        # Try fallback if available
        if self.fallback_search:
            try:
                return await self.fallback_search._arun(query=query, max_results=max_results,
                                                       search_depth="advanced",
                                                       include_raw_content=True, days=1)
            except Exception:
                pass

        raise Exception("All real-time search providers failed")

    async def _arun(self, **kwargs) -> str:
        """Main LangChain interface - delegates to appropriate search method"""
        search_type = kwargs.get("search_type", "web")

        if search_type == "news":
            return await self.search_news(**kwargs)
        elif search_type == "real_time":
            return await self.search_real_time(**kwargs)
        else:
            return await self.search_web(**kwargs)

    def get_capabilities(self) -> List[str]:
        """Return unified search capabilities"""
        capabilities = ["unified_search", "fallback_support", "web_search", "news_search", "real_time_search"]
        if self.primary_search:
            capabilities.extend(self.primary_search.get_capabilities())
        return list(set(capabilities))
```

## LLM Tool Interfaces

### 1. OpenAI LLM LangChain Tool

```python
import openai
from typing import List, Dict, Any, Optional, Type
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

class OpenAILLMInput(BaseModel):
    """Input schema for OpenAI LLM tool"""
    messages: List[Dict[str, str]] = Field(description="Chat messages")
    model: Optional[str] = Field(default="gpt-4o-mini", description="Model to use")
    max_tokens: Optional[int] = Field(default=4000, description="Maximum tokens")
    temperature: Optional[float] = Field(default=0.1, description="Temperature for generation")

class OpenAILLMTool(BettaFishTool):
    """OpenAI LLM integration as LangChain tool"""

    name: str = "openai_llm"
    description: str = "OpenAI LLM for text completion and chat"
    args_schema: Type[BaseModel] = OpenAILLMInput

    def __init__(self, config: ToolConfig):
        super().__init__(config)
        self.llm = None
        self.model = config.custom_params.get("model", "gpt-4o-mini")
        self.max_tokens = config.custom_params.get("max_tokens", 4000)
        self.temperature = config.custom_params.get("temperature", 0.1)

    async def initialize(self) -> bool:
        """Initialize OpenAI LLM"""
        try:
            self.llm = ChatOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )

            # Test with a simple message
            test_response = await self.llm.ainvoke([{"role": "user", "content": "test"}])

            self.status = ToolStatus.AVAILABLE
            return True
        except Exception as e:
            self.status = ToolStatus.ERROR
            return False

    async def _arun(self, messages: List[Dict[str, str]], model: Optional[str] = None,
                   max_tokens: Optional[int] = None, temperature: Optional[float] = None) -> str:
        """LangChain async run method"""
        if not self.llm:
            raise RuntimeError("LLM not initialized")

        # Use provided parameters or defaults
        model = model or self.model
        max_tokens = max_tokens or self.max_tokens
        temperature = temperature or self.temperature

        # Create LangChain message format
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

        langchain_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            else:  # user or default
                langchain_messages.append(HumanMessage(content=content))

        # Get response
        response = await self.llm.ainvoke(langchain_messages)

        # Return JSON with content and usage
        result = {
            "content": response.content,
            "usage": getattr(response, 'usage', {}),
            "model": model
        }

        return json.dumps(result, default=str)

    async def health_check(self) -> ToolStatus:
        """Check OpenAI API health"""
        try:
            if not self.llm:
                await self.initialize()

            test_response = await self.llm.ainvoke([{"role": "user", "content": "health check"}])
            self.status = ToolStatus.AVAILABLE
            return self.status
        except Exception:
            self.status = ToolStatus.ERROR
            return self.status

    def get_capabilities(self) -> List[str]:
        """Return OpenAI capabilities"""
        return [
            "text_completion",
            "chat_completion",
            "function_calling",
            "streaming",
            "json_mode"
        ]
```

### 2. Multi-Provider LLM LangChain Tool

```python
from langchain_core.tools import tool
from typing import List, Optional, Dict, Any

class MultiProviderLLMTool(BettaFishTool):
    """LLM tool supporting multiple providers with LangChain"""

    name: str = "multi_provider_llm"
    description: str = "Multi-provider LLM interface with automatic fallback and specialized capabilities"

    def __init__(self, config: ToolConfig):
        super().__init__(config)
        self.providers: Dict[str, BettaFishTool] = {}
        self.default_provider: Optional[str] = None

    async def add_provider(self, name: str, provider: BettaFishTool) -> None:
        """Add an LLM provider"""
        if await provider.initialize():
            self.providers[name] = provider
            if not self.default_provider:
                self.default_provider = name

    @tool("complete_text")
    async def complete_text(self, prompt: str, provider: Optional[str] = None,
                           max_tokens: int = 1000, temperature: float = 0.7) -> str:
        """Complete text with fallback providers"""
        provider_name = provider or self.default_provider

        if provider_name and provider_name in self.providers:
            try:
                result = await self.providers[provider_name]._arun(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                return result
            except Exception:
                pass

        # Try other providers as fallback
        for name, provider_tool in self.providers.items():
            if name != provider_name:
                try:
                    result = await provider_tool._arun(
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=max_tokens,
                        temperature=temperature
                    )
                    return result
                except Exception:
                    continue

        raise Exception("All LLM providers failed")

    @tool("chat_completion")
    async def chat_completion(self, messages: List[Dict[str, str]], provider: Optional[str] = None,
                             max_tokens: int = 1000, temperature: float = 0.7) -> str:
        """Chat completion with fallback providers"""
        provider_name = provider or self.default_provider

        if provider_name and provider_name in self.providers:
            try:
                result = await self.providers[provider_name]._arun(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                return result
            except Exception:
                pass

        # Try other providers as fallback
        for name, provider_tool in self.providers.items():
            if name != provider_name:
                try:
                    result = await provider_tool._arun(
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature
                    )
                    return result
                except Exception:
                    continue

        raise Exception("All LLM providers failed")

    @tool("analyze_sentiment")
    async def analyze_sentiment(self, text: str, provider: Optional[str] = None) -> str:
        """Analyze sentiment of text using LLM"""
        prompt = f"""
        Analyze the sentiment of the following text and respond with one word:
        positive, negative, or neutral.

        Text: {text}

        Sentiment:
        """

        result_json = await self.complete_text(prompt, provider=provider, temperature=0.1)
        result_data = json.loads(result_json)

        sentiment = result_data["content"].strip().lower()
        result_data["sentiment"] = sentiment
        result_data["confidence"] = 0.8  # Default confidence

        return json.dumps(result_data, default=str)

    @tool("extract_keywords")
    async def extract_keywords(self, text: str, max_keywords: int = 10, provider: Optional[str] = None) -> str:
        """Extract keywords from text using LLM"""
        prompt = f"""
        Extract the most important keywords from the following text.
        Return them as a comma-separated list, maximum {max_keywords} keywords.

        Text: {text}

        Keywords:
        """

        result_json = await self.complete_text(prompt, provider=provider, temperature=0.1)
        result_data = json.loads(result_json)

        keywords_text = result_data["content"].strip()
        keywords = [k.strip() for k in keywords_text.split(",") if k.strip()]
        result_data["keywords"] = keywords

        return json.dumps(result_data, default=str)

    async def _arun(self, **kwargs) -> str:
        """Main LangChain interface - routes to appropriate method"""
        task_type = kwargs.get("task", "complete")

        if task_type == "chat":
            return await self.chat_completion(**kwargs)
        elif task_type == "sentiment":
            return await self.analyze_sentiment(**kwargs)
        elif task_type == "keywords":
            return await self.extract_keywords(**kwargs)
        else:
            return await self.complete_text(**kwargs)

    def get_capabilities(self) -> List[str]:
        """Return multi-provider capabilities"""
        capabilities = ["multi_provider", "fallback_support", "text_completion", "chat_completion",
                       "sentiment_analysis", "keyword_extraction"]
        for provider in self.providers.values():
            capabilities.extend(provider.get_capabilities())
        return list(set(capabilities))
```

## Database Tool Interfaces

### 1. SQL Database Interface

```python
import asyncpg
import aiosqlite
from typing import List, Dict, Any, Optional, Union

class DatabaseTool(BaseTool):
    """Generic database tool interface"""
    
    def __init__(self, config: ToolConfig):
        super().__init__(config)
        self.connection_string = config.custom_params.get("connection_string")
        self.db_type = config.custom_params.get("db_type", "postgresql")
        self.connection = None
    
    async def initialize(self) -> bool:
        """Initialize database connection"""
        try:
            if self.db_type == "postgresql":
                self.connection = await asyncpg.connect(self.connection_string)
            elif self.db_type == "sqlite":
                self.connection = await aiosqlite.connect(self.connection_string)
            else:
                raise ValueError(f"Unsupported database type: {self.db_type}")
            
            # Test connection
            await self.connection.fetchval("SELECT 1")
            self.status = ToolStatus.AVAILABLE
            return True
        except Exception as e:
            self.status = ToolStatus.ERROR
            return False
    
    async def execute_query(self, query: str, params: Optional[List] = None) -> ToolResult:
        """Execute SQL query"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            if self.db_type == "postgresql":
                if params:
                    result = await self.connection.fetch(query, *params)
                else:
                    result = await self.connection.fetch(query)
                
                # Convert to list of dicts
                data = [dict(row) for row in result]
                
            elif self.db_type == "sqlite":
                cursor = await self.connection.execute(query, params or [])
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                data = [dict(zip(columns, row)) for row in rows]
            
            execution_time = asyncio.get_event_loop().time() - start_time
            
            return ToolResult(
                success=True,
                data={
                    "rows": data,
                    "row_count": len(data)
                },
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = asyncio.get_event_loop().time() - start_time
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """Execute database operation"""
        query = parameters["query"]
        params = parameters.get("params")
        return await self.execute_query(query, params)
    
    def get_capabilities(self) -> List[str]:
        """Return database capabilities"""
        return [
            "sql_query",
            "data_retrieval",
            "data_insertion",
            "data_update",
            "transaction_support"
        ]
```

## Tool Orchestration

### 1. DBOS Tool Chain Manager

```python
from dbos import DBOS
from langchain_core.tools import BaseTool as LangChainBaseTool
from typing import Dict, List, Any

class ToolChainManager:
    """Manages execution of tool chains with DBOS durability"""

    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry
        self.chains: Dict[str, List[str]] = {}

    def define_chain(self, name: str, tools: List[str]) -> None:
        """Define a tool chain"""
        self.chains[name] = tools

    @DBOS.workflow()
    def execute_chain_workflow(self, chain_name: str, initial_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool chain as a DBOS workflow"""
        chain_id = DBOS.workflow_id

        # Initialize chain execution
        chain_state = yield from self._initialize_chain_execution(chain_id, chain_name, initial_data)

        # Execute chain steps with durability
        final_result = yield from self._execute_chain_steps_durably(chain_state)

        return final_result

    @DBOS.step()
    def _initialize_chain_execution(self, chain_id: str, chain_name: str, initial_data: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize chain execution state atomically"""
        if chain_name not in self.chains:
            raise ValueError(f"Chain '{chain_name}' not found")

        return {
            'chain_id': chain_id,
            'chain_name': chain_name,
            'tools': self.chains[chain_name],
            'current_data': initial_data,
            'executed_tools': [],
            'results': [],
            'status': 'initialized',
            'started_at': datetime.now()
        }

    @DBOS.step()
    def _execute_chain_steps_durably(self, chain_state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute chain steps with automatic failure recovery"""
        current_data = chain_state['current_data']
        executed_tools = chain_state['executed_tools']
        results = chain_state['results']

        for tool_name in chain_state['tools']:
            # Check if tool already executed (resume from failure)
            if tool_name in executed_tools:
                continue

            tool = self.tool_registry.get_tool(tool_name)
            if not tool:
                raise ValueError(f"Tool '{tool_name}' not found")

            # Prepare parameters for this tool
            parameters = yield from self._prepare_tool_parameters_durably(tool_name, current_data)

            # Execute tool with DBOS durability
            result = yield from tool.durable_execute(parameters)

            if not result.success:
                # DBOS will handle retry and recovery
                raise Exception(f"Tool '{tool_name}' failed: {result.error}")

            # Update state atomically
            results.append(result)
            executed_tools.append(tool_name)
            current_data.update(result.data or {})

            # Record progress
            yield from self._record_chain_progress(chain_state['chain_id'], tool_name, 'completed')

        # Mark chain as completed
        chain_state.update({
            'status': 'completed',
            'completed_at': datetime.now(),
            'final_data': current_data,
            'results': results
        })

        return chain_state

    @DBOS.step()
    def _prepare_tool_parameters_durably(self, tool_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare parameters for specific tool with durability"""
        # This would contain logic to map data to tool-specific parameters
        # For now, just pass through the data
        return data

    @DBOS.step()
    def _record_chain_progress(self, chain_id: str, tool_name: str, status: str) -> None:
        """Record chain execution progress durably"""
        progress_data = {
            'chain_id': chain_id,
            'tool_name': tool_name,
            'status': status,
            'timestamp': datetime.now()
        }
        DBOS.set_event(chain_id, f'progress_{tool_name}', progress_data)
```

### 2. DBOS Tool Monitoring and Metrics

```python
from dbos import DBOS
from typing import Dict, List, Any, Optional

class ToolMonitor:
    """Monitor tool performance and health with DBOS durability"""

    @DBOS.step()
    def record_execution_durably(self, tool_name: str, result: ToolResult) -> None:
        """Record tool execution metrics with DBOS durability"""
        execution_data = {
            'tool_name': tool_name,
            'success': result.success,
            'execution_time': result.execution_time,
            'error': result.error,
            'tokens_used': result.tokens_used,
            'timestamp': datetime.now()
        }

        # DBOS ensures metrics are stored durably
        DBOS.set_event('tool_metrics', f'execution_{tool_name}', execution_data)

        # Check for alerts
        self._check_alerts_durably(tool_name, result)

    @DBOS.step()
    def _check_alerts_durably(self, tool_name: str, result: ToolResult) -> None:
        """Check for alert conditions with durable storage"""
        # Get recent metrics for this tool
        recent_metrics = self._get_recent_metrics(tool_name)

        # High error rate alert
        error_rate = self._calculate_error_rate(recent_metrics)
        if error_rate > 0.1:  # 10% error rate
            alert_data = {
                'type': 'high_error_rate',
                'tool_name': tool_name,
                'message': f"Tool '{tool_name}' has high error rate: {error_rate:.2%}",
                'severity': 'warning',
                'error_rate': error_rate,
                'timestamp': datetime.now()
            }
            DBOS.set_event('tool_alerts', f'alert_{tool_name}_error_rate', alert_data)

        # Slow execution alert
        avg_time = self._calculate_average_execution_time(recent_metrics)
        if avg_time > 30:  # 30 seconds
            alert_data = {
                'type': 'slow_execution',
                'tool_name': tool_name,
                'message': f"Tool '{tool_name}' has slow average execution: {avg_time:.2f}s",
                'severity': 'warning',
                'average_time': avg_time,
                'timestamp': datetime.now()
            }
            DBOS.set_event('tool_alerts', f'alert_{tool_name}_slow', alert_data)

    def _get_recent_metrics(self, tool_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent metrics for analysis"""
        # In a real implementation, this would query DBOS events
        # For now, return empty list as placeholder
        return []

    def _calculate_error_rate(self, metrics: List[Dict[str, Any]]) -> float:
        """Calculate error rate from recent metrics"""
        if not metrics:
            return 0.0

        failed = sum(1 for m in metrics if not m.get('success', True))
        return failed / len(metrics)

    def _calculate_average_execution_time(self, metrics: List[Dict[str, Any]]) -> float:
        """Calculate average execution time from recent metrics"""
        successful_metrics = [m for m in metrics if m.get('success', True) and m.get('execution_time')]
        if not successful_metrics:
            return 0.0

        total_time = sum(m['execution_time'] for m in successful_metrics)
        return total_time / len(successful_metrics)

    @DBOS.step()
    def get_metrics_summary(self, tool_name: Optional[str] = None, hours: int = 24) -> Dict[str, Any]:
        """Get metrics summary with DBOS durability"""
        # In a real implementation, this would aggregate DBOS events
        # For now, return placeholder
        return {
            'tool_name': tool_name,
            'period_hours': hours,
            'total_executions': 0,
            'success_rate': 0.0,
            'average_execution_time': 0.0,
            'error_rate': 0.0
        }

    @DBOS.step()
    def get_alerts_summary(self, severity: Optional[str] = None, hours: int = 24) -> List[Dict[str, Any]]:
        """Get alerts summary with DBOS durability"""
        # In a real implementation, this would query DBOS events
        # For now, return empty list
        return []
```

## Configuration and Deployment

### 1. Tool Configuration Schema

```python
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

class ToolConfigSchema(BaseModel):
    """Pydantic model for tool configuration"""
    name: str = Field(..., description="Tool name")
    version: str = Field(..., description="Tool version")
    type: str = Field(..., description="Tool type (search, llm, database, etc.)")
    enabled: bool = Field(True, description="Whether tool is enabled")
    
    # Connection settings
    api_key: Optional[str] = Field(None, description="API key")
    base_url: Optional[str] = Field(None, description="Base URL")
    timeout: int = Field(30, description="Timeout in seconds")
    max_retries: int = Field(3, description="Maximum retry attempts")
    
    # Rate limiting
    rate_limit: Optional[Dict[str, Any]] = Field(None, description="Rate limit settings")
    
    # Tool-specific parameters
    custom_params: Dict[str, Any] = Field(default_factory=dict, description="Custom parameters")
    
    # Dependencies
    depends_on: List[str] = Field(default_factory=list, description="Tool dependencies")
    
    class Config:
        extra = "allow"

class ToolsConfigSchema(BaseModel):
    """Configuration for all tools"""
    tools: List[ToolConfigSchema] = Field(default_factory=list)
    global_settings: Dict[str, Any] = Field(default_factory=dict)
```

This tool integration specification provides a comprehensive framework for integrating external tools and services with the modernized BettaFish system using LangChain tools within DBOS durable workflows. The hybrid approach ensures enterprise-grade reliability with ACID-compliant execution, automatic failure recovery, and flexible tool orchestration while maintaining consistency and maintainability across all tool integrations.