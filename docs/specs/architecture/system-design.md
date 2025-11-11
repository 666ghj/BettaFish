# System Architecture Design

## Architecture Overview

The BettaFish system will be migrated from a subprocess-based architecture to a hybrid LangGraph + DBOS Python orchestration system. This approach combines LangGraph's superior agent workflow coordination with DBOS's proven durable execution and state management, ensuring enterprise-grade reliability while maintaining all existing functionality.

### Current Architecture

```
┌─────────────────┐    ┌─────────────────┐
│   Flask App     │    │  ForumEngine    │
│  (Orchestrator) │◄──►│ (File-based)    │
└─────────┬───────┘    └─────────────────┘
          │
    ┌─────┴─────┐
    │             │
┌───▼───┐   ┌───▼───┐   ┌───▼───┐   ┌───▼───┐
│Insight │   │ Media │   │ Query │   │Report │
│Engine │   │Engine │   │Engine │   │Engine │
└───┬───┘   └───┬───┘   └───┬───┘   └───┬───┘
    │           │           │           │
┌───▼───┐   ┌───▼───┐   ┌───▼───┐   ┌───▼───┐
│Streamlit│   │Streamlit│   │Streamlit│   │Streamlit│
│   UI   │   │   UI   │   │   UI   │   │   UI   │
└───────┘   └───────┘   └───────┘   └───────┘
```

### Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                DBOS Workflow Orchestrator                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │   Router    │  │ Coordinator │  │ Aggregator  │   │
│  │  Workflow   │  │  Workflow   │  │  Workflow   │   │
│  └─────────────┘  └─────────────┘  └─────────────┘   │
└─────────────────────┬───────────────────────────────────┘
                      │ Durable State
        ┌─────────────┼─────────────┐
        │             │             │
┌───────▼──────┐ ┌───▼───┐ ┌─────▼──────┐
│ Insight      │ │Media   │ │ Query      │
│ LangGraph    │ │LangGraph│ │ LangGraph  │
│ StateGraph   │ │State-  │ │ StateGraph │
└───────┬──────┘ │Graph   │ └─────┬──────┘
        │        └────┬───┘       │
┌───────▼──────┐      │    ┌─────▼──────┐
│ Report       │ ┌───▼───┐ │ Tool Layer │
│ LangGraph    │ │Forum   │ │ (LangChain)│
│ StateGraph   │ │Events  │ │            │
└───────┬──────┘ └───────┘ └─────┬──────┘
        │                        │
┌───────▼──────┐           ┌─────▼──────┐
│ DBOS Durable │           │ External   │
│ State        │           │ APIs       │
│ Persistence  │           │            │
└──────────────┘           └───────────┘
```

---

## Core Components

### 1. DBOS Workflow Orchestrator (Primary Orchestration Layer)

**Purpose**: Durable workflow execution with LangGraph agent coordination

**Key Features**:
- ACID-compliant workflow execution with automatic persistence
- Request routing based on query type and complexity
- Agent selection and parallel execution coordination
- Result aggregation and formatting with failure recovery
- Enterprise-grade reliability with 99.9% uptime

**Implementation**:
```python
from dbos import DBOS, WorkflowHandle
from langgraph.graph import StateGraph, END
from typing import TypedDict, Literal, Dict, Any, List, Optional

class MasterState(TypedDict):
    query: str
    query_type: Literal["search", "analysis", "report", "multimodal"]
    selected_agents: List[str]
    agent_results: Dict[str, Any]
    final_result: Dict[str, Any]
    error: Optional[str]
    workflow_id: str

@DBOS.workflow()
def bettafish_master_workflow(query: str) -> Dict[str, Any]:
    """Durable master workflow with LangGraph coordination"""
    # Initialize durable state
    state = yield from initialize_master_state(query)

    # Route query using LangGraph router
    routing_result = yield from route_query_with_langgraph(state)

    # Execute agents in parallel with durability
    agent_results = yield from execute_agents_durably(routing_result)

    # Aggregate results with error recovery
    final_result = yield from aggregate_results_safely(agent_results)

    return final_result

@DBOS.step()
def initialize_master_state(query: str) -> MasterState:
    return {
        "query": query,
        "query_type": "search",  # Will be determined by router
        "selected_agents": [],
        "agent_results": {},
        "final_result": {},
        "error": None,
        "workflow_id": DBOS.workflow_id
    }
```

### 2. Agent StateGraphs (Specialized Processing)

Each agent is implemented as a LangGraph StateGraph, orchestrated by durable DBOS workflows:

#### InsightEngine StateGraph
```
Input → Structure Planning → Database Search → Analysis → Summary → Output
├── Durable state persistence via DBOS
├── Automatic failure recovery
└── Parallel processing optimization
```

#### MediaEngine StateGraph
```
Input → Multimodal Processing → Content Analysis → Sentiment → Output
├── DBOS-managed state transitions
├── Async API coordination
└── Result caching and reuse
```

#### QueryEngine StateGraph
```
Input → Web Search → Result Filtering → Ranking → Output
├── Durable search state management
├── Rate limiting and retry logic
└── Result deduplication
```

#### ReportEngine StateGraph
```
Input → Template Selection → Content Generation → Formatting → Output
├── DBOS workflow composition
├── Template state persistence
└── Multi-format output handling
```

### 3. Tool Layer (External Integrations)

**Unified Tool Interface**:
```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BettaFishTool(ABC):
    @abstractmethod
    async def execute(self, *args, **kwargs) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def validate_params(self, params: Dict[str, Any]) -> bool:
        pass

class TavilySearchTool(BettaFishTool):
    async def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        # Existing Tavily integration
        pass

class BochaSearchTool(BettaFishTool):
    async def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        # Existing Bocha integration
        pass
```

### 4. DBOS State Management (Durable & ACID-compliant)

**Central State Definition with DBOS Persistence**:
```python
from dbos import DBOS
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime

class BettaFishState(TypedDict):
    # Query Information
    query: str
    query_id: str
    timestamp: datetime

    # Agent Results
    agent_results: Dict[str, Any]
    search_results: List[Dict[str, Any]]
    analysis_results: Dict[str, Any]

    # Processing State (DBOS-managed)
    current_step: str
    completed_steps: List[str]
    error_info: Optional[Dict[str, Any]]

    # Configuration
    agent_config: Dict[str, Dict[str, Any]]
    tool_config: Dict[str, Dict[str, Any]]

    # Metadata
    sentiment_analysis: Dict[str, float]
    confidence_scores: Dict[str, float]
    processing_time: Dict[str, float]

# DBOS-managed state operations
@DBOS.step()
def update_workflow_state(workflow_id: str, updates: Dict[str, Any]) -> BettaFishState:
    """ACID-compliant state updates with automatic persistence"""
    current_state = get_workflow_state(workflow_id)
    new_state = {**current_state, **updates}

    # DBOS ensures atomic updates with rollback on failure
    save_workflow_state(workflow_id, new_state)
    return new_state

@DBOS.step()
def get_workflow_state(workflow_id: str) -> BettaFishState:
    """Durable state retrieval with consistency guarantees"""
    # DBOS handles caching, consistency, and failure recovery
    pass
```

### 5. Communication Layer (Events & Messaging)

**Replace File-based ForumEngine**:
```python
from langgraph.graph import GraphEvent
from typing import Dict, Any

class AgentMessage(GraphEvent):
    agent_id: str
    message_type: str  # "status", "result", "error", "coordination"
    content: Dict[str, Any]
    timestamp: datetime
    target_agent: Optional[str] = None

class ForumEvent(GraphEvent):
    event_type: str  # "agent_join", "agent_leave", "broadcast", "moderation"
    agent_id: str
    content: Dict[str, Any]
    timestamp: datetime
```

---

## Data Flow Architecture

### Request Processing Flow

1. **Request Reception**
   ```
   User Request → Flask API → Master Graph
   ```

2. **Query Routing**
   ```
   Master Graph → Route Node → Agent Selection
   ```

3. **Agent Dispatch**
   ```
   Master Graph → Agent Graphs → Parallel Execution
   ```

4. **Tool Execution**
   ```
   Agent Graphs → Tool Layer → External APIs
   ```

5. **Result Aggregation**
   ```
   Agent Graphs → Master Graph → Aggregation Node
   ```

6. **Response Formatting**
   ```
   Master Graph → Format Node → User Response
   ```

### State Transitions

```
Initial → Routing → Dispatched → Processing → Aggregating → Complete
    ↓         ↓         ↓          ↓           ↓
  Error    Error     Error      Error       Error
```

---

## Migration Strategy

### Phase 1: Foundation (Weeks 1-2)
- Implement LangGraph StateGraph base architecture
- Create unified tool interface layer
- Migrate configuration system to TypedDict state
- Implement basic agent communication

### Phase 2: Agent Migration (Weeks 3-4)
- Migrate InsightEngine to LangGraph nodes
- Migrate QueryEngine and MediaEngine
- Implement async processing patterns
- Add error handling and retry logic

### Phase 3: Coordination (Weeks 5-6)
- Replace ForumEngine file-based communication
- Implement LangGraph events for coordination
- Add master graph for agent orchestration
- Integrate ReportEngine with new architecture

### Phase 4: Integration (Weeks 7-8)
- Comprehensive testing across all components
- Performance optimization and monitoring
- Documentation and deployment guides
- Cut-over to new architecture

---

## Technology Integration

### Framework Stack
- **DBOS Python**: Durable workflow execution and state management
- **LangGraph 1.0+**: Agent orchestration and complex workflow coordination
- **Python 3.10+**: Async/await support and type hints
- **Pydantic**: Configuration and data validation
- **SQLAlchemy**: Database ORM (preserved)

### External Services (Preserved)
- **Tavily API**: Web search functionality
- **Bocha AI**: Multimodal search capabilities
- **Multiple LLM Providers**: Kimi, Gemini, DeepSeek, Qwen3
- **MySQL/PostgreSQL**: Database layer (preserved schema)

### Deployment Infrastructure
- **Docker**: Containerization (preserved)
- **Flask**: Web interface (preserved)
- **Streamlit**: Individual agent UIs (preserved)
- **Redis**: State persistence and caching (new)

---

## Benefits of Hybrid Architecture

### Reliability Improvements
- **Enterprise-grade durability** with DBOS ACID compliance and 99.9% uptime
- **Automatic failure recovery** across system restarts and network issues
- **State consistency** guaranteed even during partial failures
- **Framework-native error handling** with comprehensive retry mechanisms

### Performance Enhancements
- **Durable async processing** combining DBOS efficiency with async I/O
- **Parallel agent execution** coordinated through LangGraph StateGraphs
- **Optimized state persistence** with DBOS-managed caching and indexing
- **Resource pooling** with intelligent load balancing across agents

### Scalability Features
- **Horizontal scaling** of DBOS workflows with automatic load distribution
- **Dynamic resource allocation** based on query complexity and load
- **Multi-instance coordination** with consistent state across deployments
- **Efficient state management** with DBOS-managed data partitioning

### Maintainability Gains
- **Clear separation of concerns** between orchestration (DBOS) and coordination (LangGraph)
- **Type safety** with comprehensive type hints and Pydantic validation
- **Modular architecture** enabling independent agent development and deployment
- **Standardized patterns** with DBOS workflow primitives and LangGraph StateGraphs

---

## Risk Mitigation

### Technical Risks
- **Async migration complexity** → Start with sync-to-async wrapper patterns
- **State management compatibility** → Use TypedDict for gradual migration
- **Tool integration breaking changes** → Maintain adapter pattern

### Operational Risks
- **Downtime during migration** → Implement blue-green deployment
- **Performance regression** → Establish baseline benchmarks
- **Team learning curve** → Allocate 20% time for framework training

### Validation Approach
- **Comprehensive testing** at each migration phase
- **Performance benchmarking** against current system
- **User acceptance testing** before final cut-over
- **Rollback procedures** for each migration phase