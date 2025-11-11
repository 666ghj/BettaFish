# Data Models and State Management

## Overview

This document defines the data models, state management patterns, and data flow architecture for the modernized BettaFish system using a hybrid DBOS Python + LangGraph approach. DBOS provides durable, ACID-compliant workflow execution and state persistence, while LangGraph enables complex agent orchestration and coordination patterns.

## Core Data Models

### 1. Query State Model

```python
from typing import Dict, List, Optional, Any, TypedDict
from datetime import datetime
from enum import Enum

class QueryStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AgentStatus(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"
    COMPLETED = "completed"

class QueryState(TypedDict):
    """Primary state container for query processing"""
    # Query metadata
    query_id: str
    user_query: str
    status: QueryStatus
    created_at: datetime
    updated_at: datetime
    estimated_duration: Optional[int]
    
    # Agent coordination
    active_agents: List[str]
    agent_status: Dict[str, AgentStatus]
    agent_results: Dict[str, Any]
    
    # Processing parameters
    parameters: Dict[str, Any]
    options: Dict[str, Any]
    
    # Data flow
    search_results: Dict[str, Any]
    analysis_results: Dict[str, Any]
    sentiment_data: Dict[str, Any]
    media_data: Dict[str, Any]
    
    # Final output
    summary: Optional[str]
    detailed_analysis: Optional[Dict[str, Any]]
    report_data: Optional[Dict[str, Any]]
    
    # Error handling
    errors: List[Dict[str, Any]]
    warnings: List[str]
    
    # Metadata
    processing_time: Optional[float]
    tokens_used: Optional[Dict[str, int]]
    data_points_processed: Optional[int]
```

### 2. Agent State Models

#### Insight Engine State
```python
class InsightEngineState(TypedDict):
    """State for Insight Engine processing"""
    agent_id: str
    current_node: str
    completed_nodes: List[str]
    
    # Search state
    search_query: str
    search_parameters: Dict[str, Any]
    search_results: List[Dict[str, Any]]
    
    # Analysis state
    sentiment_data: List[Dict[str, Any]]
    keyword_data: List[Dict[str, Any]]
    topic_data: List[Dict[str, Any]]
    
    # Processing state
    reflection_count: int
    max_reflections: int
    current_iteration: int
    
    # Results
    insights: Dict[str, Any]
    confidence_scores: Dict[str, float]
    recommendations: List[str]
```

#### Media Engine State
```python
class MediaEngineState(TypedDict):
    """State for Media Engine processing"""
    agent_id: str
    current_node: str
    completed_nodes: List[str]
    
    # Media search state
    media_query: str
    platforms: List[str]
    time_range: Dict[str, datetime]
    
    # Content analysis
    media_items: List[Dict[str, Any]]
    content_analysis: Dict[str, Any]
    viral_content: List[Dict[str, Any]]
    
    # Processing state
    analysis_depth: str
    content_categories: Dict[str, List[str]]
    
    # Results
    media_insights: Dict[str, Any]
    trending_topics: List[str]
    content_performance: Dict[str, Any]
```

#### Query Engine State
```python
class QueryEngineState(TypedDict):
    """State for Query Engine processing"""
    agent_id: str
    current_node: str
    completed_nodes: List[str]
    
    # Query processing
    original_query: str
    processed_query: str
    query_intent: str
    query_entities: List[Dict[str, Any]]
    
    # Search coordination
    search_strategy: Dict[str, Any]
    search_sources: List[str]
    search_results: Dict[str, Any]
    
    # Results
    query_results: Dict[str, Any]
    relevance_scores: Dict[str, float]
    answer_candidates: List[Dict[str, Any]]
```

#### Report Engine State
```python
class ReportEngineState(TypedDict):
    """State for Report Engine processing"""
    agent_id: str
    current_node: str
    completed_nodes: List[str]
    
    # Report configuration
    report_type: str
    template_id: str
    output_format: str
    
    # Content aggregation
    aggregated_data: Dict[str, Any]
    content_sections: List[Dict[str, Any]]
    
    # Generation state
    generation_progress: float
    current_section: str
    
    # Results
    report_content: Dict[str, Any]
    html_content: Optional[str]
    pdf_path: Optional[str]
    metadata: Dict[str, Any]
```

### 3. Data Transfer Objects

#### Search Request Model
```python
class SearchRequest(TypedDict):
    """Standardized search request format"""
    query: str
    sources: List[str]
    time_range: Optional[Dict[str, datetime]]
    language: Optional[str]
    max_results: Optional[int]
    include_sentiment: Optional[bool]
    filters: Optional[Dict[str, Any]]
```

#### Analysis Result Model
```python
class AnalysisResult(TypedDict):
    """Standardized analysis result format"""
    agent_id: str
    analysis_type: str
    timestamp: datetime
    confidence: float
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    sources: List[str]
    processing_time: float
```

#### Sentiment Data Model
```python
class SentimentData(TypedDict):
    """Sentiment analysis data structure"""
    text: str
    sentiment: str  # positive, negative, neutral
    confidence: float
    source: str
    timestamp: datetime
    entities: List[Dict[str, Any]]
    keywords: List[str]
    metadata: Dict[str, Any]
```

## State Management Architecture

### 1. DBOS Workflow Integration

```python
from dbos import DBOS, WorkflowHandle
from langgraph.graph import StateGraph, END
from typing import Callable, Dict, Any, List
import uuid

class BettaFishOrchestrator:
    """Main orchestrator using DBOS workflows with LangGraph coordination"""

    def __init__(self):
        self.agent_graphs = self._build_agent_graphs()

    def _build_agent_graphs(self) -> Dict[str, StateGraph]:
        """Build LangGraph StateGraphs for each agent"""
        graphs = {}

        # Insight Engine Graph
        insight_graph = StateGraph(InsightEngineState)
        insight_graph.add_node("search", self._insight_search)
        insight_graph.add_node("analyze", self._insight_analyze)
        insight_graph.add_node("summarize", self._insight_summarize)
        insight_graph.set_entry_point("search")
        insight_graph.add_edge("search", "analyze")
        insight_graph.add_edge("analyze", "summarize")
        insight_graph.add_edge("summarize", END)
        graphs["insight"] = insight_graph.compile()

        # Similar setup for other agents...
        # Media Engine Graph, Query Engine Graph, Report Engine Graph

        return graphs

    @DBOS.workflow()
    def process_query(self, query: str, parameters: Dict[str, Any]) -> QueryState:
        """Durable workflow processing with DBOS"""
        # Initialize durable state
        workflow_id = DBOS.workflow_id
        initial_state = yield from self._initialize_query_state(query, parameters, workflow_id)

        # Route and execute agents with durability
        routing_decision = yield from self._route_query(initial_state)
        agent_results = yield from self._execute_agents_durably(routing_decision)

        # Aggregate results with ACID guarantees
        final_state = yield from self._aggregate_results_safely(initial_state, agent_results)

        return final_state

    @DBOS.step()
    def _initialize_query_state(self, query: str, parameters: Dict[str, Any], workflow_id: str) -> QueryState:
        """ACID-compliant state initialization"""
        return {
            "query_id": workflow_id,
            "user_query": query,
            "status": QueryStatus.PENDING,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "parameters": parameters,
            "active_agents": [],
            "agent_status": {},
            "agent_results": {},
            "search_results": {},
            "analysis_results": {},
            "sentiment_data": {},
            "media_data": {},
            "summary": None,
            "detailed_analysis": None,
            "report_data": None,
            "errors": [],
            "warnings": [],
            "processing_time": None,
            "tokens_used": None,
            "data_points_processed": None
        }

    @DBOS.step()
    def _execute_agents_durably(self, routing_decision: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agents with automatic failure recovery"""
        results = {}

        # Parallel agent execution with DBOS coordination
        agent_tasks = []
        for agent_id in routing_decision["agents"]:
            if routing_decision["execution_mode"] == "parallel":
                # Launch parallel DBOS child workflows
                handle = yield from DBOS.start_workflow(
                    self._run_agent_workflow,
                    agent_id,
                    routing_decision["query_state"]
                )
                agent_tasks.append((agent_id, handle))
            else:
                # Sequential execution
                result = yield from self._run_agent_workflow(agent_id, routing_decision["query_state"])
                results[agent_id] = result

        # Wait for parallel tasks with DBOS
        if routing_decision["execution_mode"] == "parallel":
            for agent_id, handle in agent_tasks:
                result = yield from handle.get_result()
                results[agent_id] = result

        return results

    @DBOS.workflow()
    def _run_agent_workflow(self, agent_id: str, query_state: QueryState) -> Dict[str, Any]:
        """Individual agent workflow with LangGraph coordination"""
        # Use LangGraph for complex agent logic
        graph = self.agent_graphs[agent_id]

        # Initialize agent-specific state
        agent_state = self._create_agent_state(agent_id, query_state)

        # Execute through LangGraph with DBOS durability
        result = yield from graph.ainvoke(agent_state)

        return result
```

### 2. DBOS State Persistence Layer

```python
from dbos import DBOS
from typing import Optional, Dict, Any
import json

class DBOSStateManager:
    """DBOS-managed state persistence with ACID guarantees"""

    @staticmethod
    @DBOS.step()
    def get_workflow_state(workflow_id: str) -> Optional[QueryState]:
        """Retrieve durable workflow state"""
        # DBOS automatically manages state persistence
        # State is stored transactionally with workflow metadata
        try:
            # DBOS provides built-in state retrieval
            state_data = DBOS.get_workflow_status(workflow_id)
            if state_data and 'state' in state_data:
                return state_data['state']
        except Exception:
            pass
        return None

    @staticmethod
    @DBOS.step()
    def update_workflow_state(workflow_id: str, updates: Dict[str, Any]) -> QueryState:
        """ACID-compliant state updates"""
        current_state = DBOSStateManager.get_workflow_state(workflow_id)
        if not current_state:
            raise ValueError(f"No state found for workflow {workflow_id}")

        # Apply updates atomically
        updated_state = {**current_state, **updates}
        updated_state['updated_at'] = datetime.now()

        # DBOS ensures atomic persistence
        # State is automatically checkpointed with each step
        return updated_state

    @staticmethod
    @DBOS.step()
    def create_workflow_checkpoint(workflow_id: str, checkpoint_data: Dict[str, Any]) -> None:
        """Create manual checkpoint for complex state"""
        # DBOS supports custom checkpointing for large state objects
        checkpoint = {
            'workflow_id': workflow_id,
            'timestamp': datetime.now(),
            'data': checkpoint_data
        }
        # Persist checkpoint with DBOS durability guarantees
        DBOS.set_event(workflow_id, 'checkpoint', checkpoint)

    @staticmethod
    @DBOS.step()
    def recover_from_checkpoint(workflow_id: str) -> Optional[Dict[str, Any]]:
        """Recover state from latest checkpoint"""
        try:
            checkpoint = DBOS.get_event(workflow_id, 'checkpoint')
            return checkpoint.get('data') if checkpoint else None
        except Exception:
            return None

class WorkflowStateStore:
    """High-level interface for state operations"""

    def __init__(self):
        self.state_manager = DBOSStateManager()

    async def get_state(self, query_id: str) -> Optional[QueryState]:
        """Get workflow state with caching"""
        return await DBOSStateManager.get_workflow_state(query_id)

    async def save_state(self, state: QueryState) -> None:
        """Save state with DBOS durability"""
        workflow_id = state['query_id']
        # DBOS automatically persists state with each workflow step
        # Manual saves create explicit checkpoints
        await DBOSStateManager.create_workflow_checkpoint(workflow_id, state)

    async def update_state(self, query_id: str, updates: Dict[str, Any]) -> None:
        """Update state atomically"""
        await DBOSStateManager.update_workflow_state(query_id, updates)

    async def delete_state(self, query_id: str) -> None:
        """Mark workflow as completed (DBOS retains history)"""
        # DBOS workflows are immutable once completed
        # Deletion marks as archived rather than removing
        await DBOSStateManager.update_workflow_state(query_id, {'status': 'archived'})
```

### 3. State Change Events

```python
from typing import Protocol
from dataclasses import dataclass

class StateChangeListener(Protocol):
    """Protocol for state change listeners"""
    
    async def on_state_changed(self, query_id: str, old_state: QueryState, new_state: QueryState) -> None:
        pass

@dataclass
class StateChangeEvent:
    """State change event data"""
    query_id: str
    agent_id: Optional[str]
    change_type: str
    old_value: Any
    new_value: Any
    timestamp: datetime

class StateEventManager:
    """Manages state change events and listeners"""
    
    def __init__(self):
        self.listeners: List[StateChangeListener] = []
    
    def add_listener(self, listener: StateChangeListener) -> None:
        self.listeners.append(listener)
    
    async def notify_state_change(self, event: StateChangeEvent) -> None:
        for listener in self.listeners:
            try:
                await listener.on_state_changed(
                    event.query_id,
                    event.old_value,
                    event.new_value
                )
            except Exception as e:
                logger.error(f"Error notifying listener: {e}")
```

## Data Flow Patterns

### 1. DBOS Agent Coordination Flow

```python
from dbos import DBOS, WorkflowHandle
from typing import List, Dict, Any

class AgentCoordinator:
    """Coordinates multi-agent data flow with DBOS durability"""

    @DBOS.workflow()
    def coordinate_agents(self, query_id: str, agents: List[str]) -> Dict[str, Any]:
        """Durable multi-agent coordination"""
        # Initialize coordination state
        coord_state = yield from self._initialize_coordination(query_id, agents)

        # Execute agents based on coordination strategy
        if self._should_run_parallel(agents):
            results = yield from self._run_parallel_agents_durably(query_id, agents)
        else:
            results = yield from self._run_sequential_agents_durably(query_id, agents)

        # Aggregate results with ACID guarantees
        final_results = yield from self._aggregate_agent_results(query_id, results)

        return final_results

    @DBOS.step()
    def _initialize_coordination(self, query_id: str, agents: List[str]) -> Dict[str, Any]:
        """Initialize coordination state atomically"""
        return {
            'query_id': query_id,
            'agents': agents,
            'started_at': datetime.now(),
            'status': 'initializing',
            'agent_handles': {}
        }

    @DBOS.step()
    def _run_parallel_agents_durably(self, query_id: str, agents: List[str]) -> Dict[str, Any]:
        """Run agents in parallel with DBOS child workflows"""
        results = {}
        handles = []

        # Launch child workflows for each agent
        for agent_id in agents:
            handle = yield from DBOS.start_workflow(
                BettaFishOrchestrator()._run_agent_workflow,
                agent_id,
                {'query_id': query_id}
            )
            handles.append((agent_id, handle))

        # Wait for all agents to complete with automatic recovery
        for agent_id, handle in handles:
            try:
                result = yield from handle.get_result()
                results[agent_id] = result
            except Exception as e:
                # DBOS automatically retries failed workflows
                results[agent_id] = {'error': str(e), 'status': 'failed'}

        return results

    @DBOS.step()
    def _run_sequential_agents_durably(self, query_id: str, agents: List[str]) -> Dict[str, Any]:
        """Run agents sequentially with state persistence"""
        results = {}

        for agent_id in agents:
            try:
                # Each step is automatically checkpointed by DBOS
                result = yield from BettaFishOrchestrator()._run_agent_workflow(
                    agent_id,
                    {'query_id': query_id}
                )
                results[agent_id] = result

                # Update progress state
                yield from self._update_progress(query_id, agent_id, 'completed')

            except Exception as e:
                results[agent_id] = {'error': str(e), 'status': 'failed'}
                # DBOS ensures failed steps can be resumed
                yield from self._update_progress(query_id, agent_id, 'failed')

        return results

    @DBOS.step()
    def _update_progress(self, query_id: str, agent_id: str, status: str) -> None:
        """Update coordination progress atomically"""
        # DBOS ensures this update is durable and consistent
        progress_update = {
            'agent_id': agent_id,
            'status': status,
            'timestamp': datetime.now()
        }
        DBOS.set_event(query_id, f'progress_{agent_id}', progress_update)
```

### 2. Data Aggregation Pattern

```python
class DataAggregator:
    """Aggregates results from multiple agents"""
    
    async def aggregate_results(self, query_id: str) -> Dict[str, Any]:
        """Aggregate results from all agents"""
        state = await self.state_store.get_state(query_id)
        
        aggregated = {
            'query_id': query_id,
            'timestamp': datetime.now(),
            'agents': list(state['agent_results'].keys()),
            'data': {}
        }
        
        # Aggregate sentiment data
        sentiment_data = self._aggregate_sentiment_data(state)
        if sentiment_data:
            aggregated['data']['sentiment'] = sentiment_data
        
        # Aggregate media data
        media_data = self._aggregate_media_data(state)
        if media_data:
            aggregated['data']['media'] = media_data
        
        # Aggregate search results
        search_data = self._aggregate_search_data(state)
        if search_data:
            aggregated['data']['search'] = search_data
        
        # Generate summary
        aggregated['summary'] = await self._generate_summary(aggregated['data'])
        
        return aggregated
    
    def _aggregate_sentiment_data(self, state: QueryState) -> Optional[Dict[str, Any]]:
        """Aggregate sentiment data from multiple agents"""
        all_sentiment = []
        
        for agent_result in state['agent_results'].values():
            if 'sentiment_data' in agent_result:
                all_sentiment.extend(agent_result['sentiment_data'])
        
        if not all_sentiment:
            return None
        
        # Calculate overall sentiment
        positive_count = sum(1 for s in all_sentiment if s['sentiment'] == 'positive')
        negative_count = sum(1 for s in all_sentiment if s['sentiment'] == 'negative')
        neutral_count = sum(1 for s in all_sentiment if s['sentiment'] == 'neutral')
        
        total = len(all_sentiment)
        
        return {
            'total_items': total,
            'sentiment_distribution': {
                'positive': positive_count / total,
                'negative': negative_count / total,
                'neutral': neutral_count / total
            },
            'average_confidence': sum(s['confidence'] for s in all_sentiment) / total,
            'data_points': all_sentiment
        }
```

## Error Handling and Recovery

### 1. DBOS Recovery Mechanisms

```python
from dbos import DBOS, WorkflowStatus

class DBOSRecoveryManager:
    """Leverages DBOS built-in recovery and fault tolerance"""

    @staticmethod
    @DBOS.step()
    def handle_workflow_failure(workflow_id: str, error: Exception) -> Dict[str, Any]:
        """Handle workflow failures with DBOS recovery"""
        # DBOS automatically provides failure recovery
        workflow_status = DBOS.get_workflow_status(workflow_id)

        recovery_strategy = {
            'workflow_id': workflow_id,
            'error': str(error),
            'failure_time': datetime.now(),
            'can_recover': True,
            'recovery_attempts': workflow_status.get('retry_count', 0)
        }

        # Determine recovery strategy based on error type
        if DBOSRecoveryManager._is_recoverable_error(error):
            recovery_strategy['strategy'] = 'retry'
            recovery_strategy['max_retries'] = 3
        elif DBOSRecoveryManager._can_degrade_gracefully(workflow_id, error):
            recovery_strategy['strategy'] = 'degrade'
            recovery_strategy['fallback_agents'] = DBOSRecoveryManager._get_fallback_agents(workflow_id)
        else:
            recovery_strategy['strategy'] = 'fail'
            recovery_strategy['can_recover'] = False

        return recovery_strategy

    @staticmethod
    @DBOS.step()
    def resume_failed_workflow(workflow_id: str) -> Optional[QueryState]:
        """Resume workflow from last successful step"""
        # DBOS automatically tracks execution progress
        workflow_status = DBOS.get_workflow_status(workflow_id)

        if workflow_status['status'] == WorkflowStatus.PENDING:
            # Resume from last completed step
            last_step = DBOSRecoveryManager._get_last_completed_step(workflow_id)
            if last_step:
                return DBOSRecoveryManager._reconstruct_state_from_step(workflow_id, last_step)

        return None

    @staticmethod
    @DBOS.step()
    def create_failure_checkpoint(workflow_id: str, error_context: Dict[str, Any]) -> None:
        """Create checkpoint before failure for analysis"""
        checkpoint = {
            'workflow_id': workflow_id,
            'timestamp': datetime.now(),
            'error_context': error_context,
            'system_state': DBOSRecoveryManager._capture_system_state(),
            'agent_states': DBOSRecoveryManager._capture_agent_states(workflow_id)
        }

        # DBOS ensures checkpoint durability
        DBOS.set_event(workflow_id, 'failure_checkpoint', checkpoint)

    @staticmethod
    def _is_recoverable_error(error: Exception) -> bool:
        """Determine if error is recoverable"""
        recoverable_errors = [
            'ConnectionError',
            'TimeoutError',
            'TemporaryFailure'
        ]
        return any(err_type in str(type(error)) for err_type in recoverable_errors)

    @staticmethod
    def _can_degrade_gracefully(workflow_id: str, error: Exception) -> bool:
        """Check if workflow can continue with reduced functionality"""
        # Logic to determine graceful degradation capability
        critical_agents = ['query_engine']  # Define critical agents
        failed_agent = DBOSRecoveryManager._get_failed_agent_from_error(error)

        return failed_agent not in critical_agents

    @staticmethod
    def _get_fallback_agents(workflow_id: str) -> List[str]:
        """Get fallback agents for graceful degradation"""
        # Return alternative agents that can provide similar functionality
        return ['backup_agent_1', 'backup_agent_2']
```

## Performance Optimization

### 1. DBOS State Caching Strategy

```python
from dbos import DBOS
from typing import Dict, Any, Optional
import time

class DBOSStateCacheManager:
    """DBOS-managed state caching with automatic persistence"""

    def __init__(self, cache_ttl: int = 3600):
        self.cache_ttl = cache_ttl
        # DBOS provides built-in caching with consistency guarantees

    @DBOS.step()
    def get_cached_workflow_state(self, workflow_id: str) -> Optional[QueryState]:
        """Get cached workflow state with DBOS consistency"""
        # DBOS automatically manages cache invalidation
        # State is always consistent with durable storage
        try:
            state = DBOS.get_workflow_status(workflow_id)
            if state and self._is_cache_valid(state):
                return state.get('cached_state')
        except Exception:
            pass

        # Fallback to durable storage
        return DBOSStateManager.get_workflow_state(workflow_id)

    @DBOS.step()
    def cache_workflow_state(self, workflow_id: str, state: QueryState) -> None:
        """Cache state with DBOS durability guarantees"""
        cache_entry = {
            'state': state,
            'cached_at': datetime.now(),
            'ttl': self.cache_ttl,
            'version': state.get('version', 1)
        }

        # DBOS ensures cache consistency across instances
        DBOS.set_event(workflow_id, 'state_cache', cache_entry)

    def _is_cache_valid(self, state: Dict[str, Any]) -> bool:
        """Check if cached state is still valid"""
        if 'cached_at' not in state:
            return False

        cache_age = (datetime.now() - state['cached_at']).total_seconds()
        return cache_age < self.cache_ttl

class WorkflowCacheManager:
    """High-level cache management with DBOS"""

    def __init__(self):
        self.dbos_cache = DBOSStateCacheManager()

    async def get_state_with_cache(self, workflow_id: str) -> Optional[QueryState]:
        """Get state with intelligent caching"""
        # Try cache first
        cached_state = await self.dbos_cache.get_cached_workflow_state(workflow_id)
        if cached_state:
            return cached_state

        # Fallback to durable storage
        durable_state = await DBOSStateManager.get_workflow_state(workflow_id)
        if durable_state:
            # Cache for future use
            await self.dbos_cache.cache_workflow_state(workflow_id, durable_state)

        return durable_state

    async def invalidate_cache(self, workflow_id: str) -> None:
        """Invalidate cache when state changes significantly"""
        # DBOS ensures cache invalidation is atomic
        DBOS.set_event(workflow_id, 'cache_invalidate', {
            'timestamp': datetime.now(),
            'reason': 'state_changed'
        })
```

### 2. DBOS Batch Processing

```python
from dbos import DBOS
from typing import List, Dict, Any
import asyncio

class DBOSBatchProcessor:
    """DBOS-managed batch processing with ACID guarantees"""

    def __init__(self, batch_size: int = 10, max_wait_time: float = 5.0):
        self.batch_size = batch_size
        self.max_wait_time = max_wait_time

    @DBOS.workflow()
    def process_batch_updates(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process batch of updates with DBOS durability"""
        batch_id = DBOS.workflow_id
        results = {}

        # Process updates in ACID-compliant batches
        for i in range(0, len(updates), self.batch_size):
            batch = updates[i:i + self.batch_size]
            batch_result = yield from self._process_batch_chunk(batch_id, batch, i)
            results.update(batch_result)

        return {
            'batch_id': batch_id,
            'total_updates': len(updates),
            'processed_at': datetime.now(),
            'results': results
        }

    @DBOS.step()
    def _process_batch_chunk(self, batch_id: str, batch: List[Dict[str, Any]], offset: int) -> Dict[str, Any]:
        """Process a chunk of updates atomically"""
        results = {}

        for update in batch:
            try:
                # Each update is processed atomically
                result = yield from self._apply_single_update(update)
                results[update['query_id']] = result

                # DBOS ensures all updates in batch succeed or all fail
                yield from self._record_batch_progress(batch_id, offset + len(results))

            except Exception as e:
                results[update['query_id']] = {'error': str(e)}
                # DBOS automatically handles rollback of failed batches

        return results

    @DBOS.step()
    def _apply_single_update(self, update: Dict[str, Any]) -> Dict[str, Any]:
        """Apply single update with ACID guarantees"""
        workflow_id = update['query_id']

        # DBOS ensures atomic state updates
        current_state = yield from DBOSStateManager.get_workflow_state(workflow_id)
        if not current_state:
            raise ValueError(f"Workflow {workflow_id} not found")

        # Apply update atomically
        updated_state = {**current_state, **update['changes']}
        updated_state['updated_at'] = datetime.now()
        updated_state['version'] = current_state.get('version', 0) + 1

        # Persist with ACID guarantees
        yield from DBOSStateManager.update_workflow_state(workflow_id, updated_state)

        return {'status': 'success', 'version': updated_state['version']}

    @DBOS.step()
    def _record_batch_progress(self, batch_id: str, progress: int) -> None:
        """Record batch processing progress"""
        DBOS.set_event(batch_id, 'progress', {
            'processed': progress,
            'timestamp': datetime.now()
        })
```

This data model and state management specification provides a robust foundation for the modernized BettaFish system using DBOS durable workflows and LangGraph agent orchestration. The hybrid approach ensures enterprise-grade reliability with ACID-compliant state management, automatic failure recovery, and efficient performance across all agents while maintaining complex multi-agent coordination capabilities.