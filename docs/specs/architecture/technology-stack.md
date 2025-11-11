# Technology Stack Specification

## Core Framework Selection

### Hybrid Architecture: LangGraph + DBOS Python

**Rationale for Hybrid Approach**:
- **Agent Orchestration**: LangGraph provides superior agent workflow orchestration with StateGraph architecture
- **State Management**: DBOS Python offers proven durable execution and state persistence in production
- **Best of Both Worlds**: Combines LangGraph's agent coordination with DBOS's battle-tested state management
- **Production Maturity**: DBOS has been proven at scale with 99.9% uptime in enterprise deployments

**Framework Components**:

#### LangGraph 1.0+ (Agent Orchestration)
**Key Features**:
- StateGraph architecture for complex multi-agent workflows
- Human-in-the-loop support for oversight and intervention
- Built-in debugging with LangSmith integration
- Parallel agent execution with proper synchronization

#### DBOS Python (State Management & Durability)
**Key Features**:
- Durable execution with automatic failure recovery
- ACID-compliant state persistence
- Built-in workflow orchestration primitives
- Production-proven reliability (99.9% uptime SLA)

**Migration Benefits**:
- **Reliability**: DBOS provides enterprise-grade durability and recovery
- **Scalability**: LangGraph enables complex agent coordination at scale
- **Observability**: Combined tracing and monitoring capabilities
- **Performance**: Optimized state management with async processing

---

## Programming Language & Runtime

### Python 3.10+

**Selection Criteria**:
- **Async/Await Support**: Essential for I/O-bound operations
- **Type Hinting**: Comprehensive type safety and IDE support
- **Ecosystem Compatibility**: Full compatibility with LangGraph and dependencies
- **Performance**: Significant performance improvements over Python 3.8

**Key Features for BettaFish**:
- Async/await patterns for concurrent API calls
- Structural pattern matching for better error handling
- Improved error messages and debugging
- Better memory management and garbage collection

---

## State Management & Data Validation

### DBOS Python (Primary State Management)

**Role in Architecture**:
- Durable workflow execution with automatic persistence
- ACID-compliant state management across agent lifecycles
- Built-in recovery from failures and system restarts
- Optimized for high-throughput agent coordination

**Key Features**:
- **Durable Execution**: Automatic checkpointing and resume from failures
- **ACID Transactions**: Consistent state updates across distributed operations
- **Workflow Primitives**: Built-in support for complex agent coordination patterns
- **Production Reliability**: 99.9% uptime with enterprise-grade monitoring

**Implementation Pattern**:
```python
import os
from dbos import DBOS, WorkflowHandle
from typing import Dict, Any, List, Optional
from datetime import datetime

# DBOS workflow for agent orchestration
@DBOS.workflow()
def bettafish_agent_workflow(query: str, agent_config: Dict[str, Any]) -> Dict[str, Any]:
    # Durable state management with automatic persistence
    state = initialize_workflow_state(query)

    # Parallel agent execution with coordination
    results = yield from execute_agents_parallel(state)

    # Durable result aggregation
    final_result = yield from aggregate_results(results)

    return final_result

@DBOS.step()
def initialize_workflow_state(query: str) -> Dict[str, Any]:
    return {
        "query": query,
        "query_id": DBOS.workflow_id,
        "timestamp": datetime.utcnow(),
        "status": "initialized",
        "agent_results": {},
        "completed_steps": []
    }
```

### Pydantic v2 (Data Validation & Serialization)

**Integration with DBOS**:
- Input/output validation for all workflow steps
- Configuration management with environment variable support
- Type-safe interfaces between agents and tools
- JSON schema generation for API documentation

**Benefits**:
- **Type Safety**: Compile-time and runtime type checking
- **Validation**: Automatic input validation with clear error messages
- **DBOS Integration**: Seamless serialization for durable state persistence
- **Documentation**: Auto-generated API documentation

---

## Database Layer

### SQLAlchemy 2.0+ (Preserved)

**Rationale for Preservation**:
- **Existing Schema**: MindSpider database schema with 4 tables
- **Investment Protection**: Preserves existing data and migrations
- **Team Familiarity**: Current team expertise and tooling
- **Stability**: Mature, well-tested ORM with excellent performance

**Migration Enhancements**:
- **Async Support**: SQLAlchemy 2.0 async engine for better performance
- **Connection Pooling**: Improved connection management
- **Query Optimization**: Better query planning and execution
- **Type Integration**: Enhanced Pydantic integration

**Database Schema Preservation**:
```sql
-- Preserved Tables
daily_news              -- News articles and content
daily_topics            -- Topic classifications
topic_news_relation     -- News-topic relationships
crawling_tasks         -- Task tracking and status
```

---

## External API Integrations

### Tavily API (Web Search)

**Integration Details**:
- **Purpose**: Real-time web search for QueryEngine
- **Features**: AI-optimized search results with citations
- **Performance**: Sub-second response times
- **Reliability**: 99.9% uptime SLA

**Implementation**:
```python
class TavilySearchTool(BettaFishTool):
    async def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        # Existing Tavily integration with async wrapper
        pass
```

### Bocha AI (Multimodal Search)

**Integration Details**:
- **Purpose**: Multimodal content analysis for MediaEngine
- **Capabilities**: Image, video, and audio content processing
- **API**: RESTful API with JSON responses
- **Rate Limits**: Configurable with automatic backoff

### Multiple LLM Providers

**Provider Configuration**:
```python
LLM_PROVIDERS = {
    "insight": {
        "provider": "kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "kimi-k2-0711-preview"
    },
    "media": {
        "provider": "gemini",
        "base_url": "https://aihubmix.com/v1",
        "model": "gemini-2.5-pro"
    },
    "query": {
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-reasoner"
    },
    "report": {
        "provider": "gemini",
        "base_url": "https://aihubmix.com/v1",
        "model": "gemini-2.5-pro"
    },
    "forum": {
        "provider": "qwen3",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "Qwen/Qwen3-235B-A22B-Instruct-2507"
    }
}
```

---

## Web Framework & UI

### Flask (Preserved)

**Role**: Main orchestrator and API server
- **API Endpoints**: RESTful interfaces for system management
- **WebSocket Support**: Real-time updates via Flask-SocketIO
- **Static Content**: Serve web interfaces and documentation
- **Middleware**: Authentication, logging, and error handling

### Streamlit (Preserved)

**Role**: Individual agent interfaces
- **InsightEngine UI**: Database mining and analysis interface
- **MediaEngine UI**: Multimodal search and content analysis
- **QueryEngine UI**: Web search and result exploration
- **ReportEngine UI**: Report generation and template management

**Benefits of Preservation**:
- **User Familiarity**: Existing user workflows preserved
- **Development Speed**: Rapid prototyping and iteration
- **Integration**: Easy integration with Python backend
- **Deployment**: Simple containerization and scaling

---

## Deployment & Infrastructure

### Docker (Preserved & Enhanced)

**Container Strategy**:
```dockerfile
# Multi-stage build for optimization
FROM python:3.10-slim as builder
# Build dependencies and application

FROM python:3.10-slim as runtime
# Runtime container with minimal footprint
```

**Enhancements**:
- **Multi-stage Builds**: Optimized image sizes
- **Health Checks**: Built-in health monitoring
- **Resource Limits**: CPU and memory constraints
- **Security Scanning**: Automated vulnerability scanning

### Redis (New Addition)

**Purpose**: State persistence and caching
- **Session Storage**: User session and workflow state
- **Caching**: API response and database query caching
- **Message Queue**: Agent communication and coordination
- **Rate Limiting**: API rate limiting and throttling

**Configuration**:
```python
REDIS_CONFIG = {
    "host": "redis",
    "port": 6379,
    "db": 0,
    "password": None,  # Use environment variable
    "socket_timeout": 5,
    "socket_connect_timeout": 5,
    "retry_on_timeout": True,
    "health_check_interval": 30
}
```

---

## Monitoring & Observability

### LangSmith Integration

**Capabilities**:
- **Agent Tracing**: Complete execution path visualization
- **Performance Metrics**: Latency, token usage, and error rates
- **Debugging**: Step-by-step execution analysis
- **Comparison**: A/B testing for prompt and workflow changes

### Prometheus & Grafana

**Metrics Collection**:
- **System Metrics**: CPU, memory, disk, and network usage
- **Application Metrics**: Request rates, response times, error rates
- **Business Metrics**: Agent usage, report generation, user satisfaction
- **Custom Metrics**: Agent-specific performance indicators

**Dashboard Examples**:
- System Overview Dashboard
- Agent Performance Dashboard
- API Usage Dashboard
- Error Analysis Dashboard

---

## Security & Compliance

### Encryption & Security

**Data Protection**:
- **API Keys**: AES-256 encryption at rest
- **Network Traffic**: TLS 1.3 for all communications
- **Environment Variables**: Secure injection and management
- **Audit Logging**: Comprehensive security event logging

### Authentication & Authorization

**Implementation**:
```python
from flask_jwt_extended import JWTManager, create_access_token, jwt_required

# JWT-based authentication
@app.route('/api/agents/<agent_id>/execute')
@jwt_required()
def execute_agent(agent_id):
    # Agent execution with authentication
    pass
```

---

## Development & Testing Tools

### Pytest (Testing Framework)

**Testing Strategy**:
- **Unit Tests**: Individual component testing with mocks
- **Integration Tests**: Multi-component interaction testing
- **End-to-End Tests**: Complete workflow testing
- **Performance Tests**: Load and stress testing

### Black & Ruff (Code Quality)

**Code Formatting**:
- **Black**: Consistent code formatting
- **Ruff**: Fast linting and code analysis
- **mypy**: Static type checking
- **pre-commit**: Automated quality checks

### Development Environment

**Local Development**:
```bash
# Development setup
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

# Pre-commit hooks
pre-commit install

# Development server
python -m bettafish.main --dev
```

---

## Migration Compatibility Matrix

| Component | Current | Target | Migration Complexity | Risk Level |
|-----------|---------|--------|-------------------|------------|
| Agent Orchestration | Custom subprocess | LangGraph StateGraph | Medium | Low |
| State Management | Custom classes | DBOS Python | High | Medium |
| Language | Python 3.8+ | Python 3.10+ | Low | Low |
| Data Validation | Basic validation | Pydantic v2 | Low | Low |
| Database | SQLAlchemy 1.4 | SQLAlchemy 2.0 | Low | Low |
| Web Framework | Flask | Flask (preserved) | None | None |
| UI | Streamlit | Streamlit (preserved) | None | None |
| External APIs | Custom integrations | LangChain tools | Medium | Medium |
| Agent Communication | File-based | A2A Protocol | High | Medium |
| Observability | Basic logging | OpenTelemetry | Medium | Low |
| Deployment | Docker | Docker (enhanced) | Low | Low |
| Monitoring | Basic logging | OTEL + Prometheus | High | Medium |

---

## Technology Justification Summary

### Primary Benefits
1. **Enterprise Reliability**: DBOS provides production-proven durability with 99.9% uptime
2. **Advanced Orchestration**: LangGraph enables complex multi-agent coordination patterns
3. **Performance**: Optimized async processing with durable state persistence
4. **Scalability**: Horizontal scaling support with efficient resource utilization
5. **Observability**: Comprehensive tracing and monitoring across the entire stack

### Risk Mitigation
1. **Hybrid Approach**: Gradual migration leveraging strengths of both frameworks
2. **Backward Compatibility**: Preserved interfaces and existing functionality
3. **Comprehensive Testing**: Extensive test coverage with DBOS reliability guarantees
4. **Rollback Planning**: Clear procedures for reverting to previous architecture
5. **Team Training**: Dedicated time for learning LangGraph and DBOS patterns

### Success Criteria
1. **Performance**: 40% improvement in response times with durable execution
2. **Reliability**: 99.9% uptime matching DBOS production standards
3. **Maintainability**: 50% reduction in state management complexity
4. **Scalability**: Support for 20x current load with horizontal scaling
5. **Developer Experience**: Superior debugging with LangSmith + DBOS monitoring