# Testing Strategy

## Overview

This document defines a comprehensive testing strategy for the modernized BettaFish system, ensuring reliability, performance, and security throughout the migration process and in production.

## Testing Philosophy

### Core Principles
1. **Test-Driven Development**: Write tests before implementation
2. **Comprehensive Coverage**: Unit, integration, end-to-end, and performance testing
3. **Automation First**: Automated testing in CI/CD pipeline
4. **Continuous Validation**: Ongoing testing in production
5. **Risk-Based Testing**: Focus on high-risk areas and critical paths

### Testing Pyramid
```
    E2E Tests (10%)
   ┌─────────────────┐
  │  Integration    │ (20%)
 ┌─────────────────────┐
│    Unit Tests       │ (70%)
└─────────────────────┘
```

## Test Categories

### 1. Unit Testing

#### Scope
- Individual agent components
- Tool integrations
- Data models and state management
- Utility functions
- API endpoints

#### Framework Stack
- **pytest**: Primary testing framework
- **pytest-asyncio**: Async test support
- **pytest-mock**: Mocking and patching
- **pytest-cov**: Coverage reporting
- **factory-boy**: Test data factories

#### Test Structure
```python
# tests/unit/agents/test_insight_engine.py
import pytest
from unittest.mock import AsyncMock, patch
from src.agents.insight_engine import InsightEngine
from src.state.models import QueryState

class TestInsightEngine:
    @pytest.fixture
    def insight_engine(self):
        config = {
            "model_name": "gpt-4o-mini",
            "api_key": "test-key",
            "max_tokens": 1000
        }
        return InsightEngine(config)
    
    @pytest.fixture
    def sample_query_state(self):
        return {
            "query_id": "test-123",
            "user_query": "Analyze sentiment about electric vehicles",
            "status": "pending",
            "parameters": {"time_range": "7d"},
            "active_agents": ["insight-engine"],
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
    
    @pytest.mark.asyncio
    async def test_process_query_success(self, insight_engine, sample_query_state):
        """Test successful query processing"""
        with patch.object(insight_engine, '_search_for_data') as mock_search, \
             patch.object(insight_engine, '_analyze_sentiment') as mock_analyze:
            
            mock_search.return_value = {"results": [{"text": "Positive review"}]}
            mock_analyze.return_value = {"sentiment": "positive", "confidence": 0.9}
            
            result = await insight_engine.process(sample_query_state)
            
            assert result["status"] == "completed"
            assert "sentiment_data" in result
            assert result["sentiment_data"]["sentiment"] == "positive"
    
    @pytest.mark.asyncio
    async def test_process_query_with_search_error(self, insight_engine, sample_query_state):
        """Test handling of search errors"""
        with patch.object(insight_engine, '_search_for_data') as mock_search:
            mock_search.side_effect = Exception("Search API error")
            
            result = await insight_engine.process(sample_query_state)
            
            assert result["status"] == "failed"
            assert len(result["errors"]) > 0
            assert "Search API error" in result["errors"][0]["error"]
    
    def test_validate_parameters_valid(self, insight_engine):
        """Test parameter validation with valid input"""
        params = {"query": "test query", "max_results": 10}
        assert insight_engine.validate_parameters(params) is True
    
    def test_validate_parameters_invalid(self, insight_engine):
        """Test parameter validation with invalid input"""
        params = {"query": "", "max_results": -1}
        assert insight_engine.validate_parameters(params) is False
```

#### Coverage Requirements
- **Minimum Coverage**: 90% line coverage
- **Critical Components**: 95% coverage
- **Branch Coverage**: 85% minimum

### 2. Integration Testing

#### Scope
- Agent-to-agent communication
- Tool integration workflows
- Database operations
- External API interactions
- State management flows

#### Test Environment
- **Docker Compose**: Full stack testing environment
- **Test Database**: Isolated PostgreSQL instance
- **Mock External Services**: WireMock for API mocking
- **Redis Instance**: For state management testing

#### Test Examples
```python
# tests/integration/test_agent_coordination.py
import pytest
from src.orchestrator import BettaFishOrchestrator
from src.state.store import RedisStateStore

class TestAgentCoordination:
    @pytest.fixture
    async def orchestrator(self):
        state_store = RedisStateStore("redis://localhost:6379/1")
        return BettaFishOrchestrator(state_store)
    
    @pytest.mark.asyncio
    async def test_multi_agent_workflow(self, orchestrator):
        """Test coordination between multiple agents"""
        query = "Analyze electric vehicle sentiment across news and social media"
        parameters = {
            "agents": ["insight-engine", "media-engine"],
            "time_range": "7d",
            "sources": ["news", "social"]
        }
        
        result = await orchestrator.process_query(query, parameters)
        
        assert result["status"] == "completed"
        assert "insight-engine" in result["agent_results"]
        assert "media-engine" in result["agent_results"]
        assert result["agent_status"]["insight-engine"] == "completed"
        assert result["agent_status"]["media-engine"] == "completed"
    
    @pytest.mark.asyncio
    async def test_agent_failure_handling(self, orchestrator):
        """Test system behavior when an agent fails"""
        query = "Test query with failing agent"
        parameters = {
            "agents": ["insight-engine", "nonexistent-agent"],
            "fallback_enabled": True
        }
        
        result = await orchestrator.process_query(query, parameters)
        
        # Should continue with available agents
        assert result["status"] in ["completed", "partial"]
        assert "insight-engine" in result["agent_results"]
        assert len(result["errors"]) > 0
```

### 3. End-to-End Testing

#### Scope
- Complete user workflows
- API request/response cycles
- WebSocket streaming
- Report generation
- Data export functionality

#### Test Framework
- **Playwright**: Browser automation for UI testing
- **httpx**: Async HTTP client for API testing
- **websockets**: WebSocket client testing
- **pytest-playwright**: Playwright integration

#### Test Scenarios
```python
# tests/e2e/test_complete_workflows.py
import pytest
import asyncio
from httpx import AsyncClient
from websockets.client import connect

class TestCompleteWorkflows:
    @pytest.mark.asyncio
    async def test_sentiment_analysis_workflow(self):
        """Test complete sentiment analysis workflow"""
        async with AsyncClient() as client:
            # Submit query
            response = await client.post(
                "http://localhost:8000/api/v1/query",
                json={
                    "query": "Analyze sentiment about renewable energy",
                    "agents": ["insight-engine", "media-engine"],
                    "parameters": {
                        "time_range": "7d",
                        "sources": ["news", "social"]
                    }
                }
            )
            
            assert response.status_code == 200
            query_data = response.json()
            query_id = query_data["query_id"]
            
            # Monitor progress via WebSocket
            async with connect(f"ws://localhost:8000/ws/query/{query_id}") as ws:
                completed = False
                while not completed:
                    message = await ws.recv()
                    data = json.loads(message)
                    
                    if data["type"] == "completed":
                        completed = True
                        assert "results" in data
                    elif data["type"] == "error":
                        pytest.fail(f"Workflow failed: {data['error']}")
            
            # Verify final results
            response = await client.get(f"http://localhost:8000/api/v1/query/{query_id}")
            assert response.status_code == 200
            
            result = response.json()
            assert result["status"] == "completed"
            assert "summary" in result["results"]
            assert "detailed_analysis" in result["results"]
    
    @pytest.mark.asyncio
    async def test_report_generation_workflow(self):
        """Test complete report generation workflow"""
        async with AsyncClient() as client:
            # Generate report
            response = await client.post(
                "http://localhost:8000/api/v1/reports",
                json={
                    "query_id": "test-query-123",
                    "report_type": "sentiment_analysis",
                    "format": "html",
                    "template": "standard"
                }
            )
            
            assert response.status_code == 200
            report_data = response.json()
            report_id = report_data["report_id"]
            
            # Wait for generation
            await asyncio.sleep(5)
            
            # Download report
            response = await client.get(f"http://localhost:8000/api/v1/reports/{report_id}/download")
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/html"
```

### 4. Performance Testing

#### Scope
- Load testing
- Stress testing
- Scalability testing
- Response time validation
- Resource utilization monitoring

#### Tools
- **Locust**: Load testing framework
- **pytest-benchmark**: Microbenchmarking
- **Prometheus**: Metrics collection
- **Grafana**: Performance visualization

#### Test Scenarios
```python
# tests/performance/test_load.py
from locust import HttpUser, task, between

class BettaFishLoadTest(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Setup for each user"""
        response = self.client.post("/api/v1/auth/login", json={
            "username": "test_user",
            "password": "test_password"
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(3)
    def submit_sentiment_query(self):
        """Submit sentiment analysis query"""
        self.client.post("/api/v1/query", 
            json={
                "query": "Analyze market sentiment",
                "agents": ["insight-engine"],
                "parameters": {"time_range": "24h"}
            },
            headers=getattr(self, 'headers', {})
        )
    
    @task(2)
    def check_query_status(self):
        """Check query status"""
        self.client.get("/api/v1/query/test-query-123",
            headers=getattr(self, 'headers', {})
        )
    
    @task(1)
    def get_system_health(self):
        """Check system health"""
        self.client.get("/api/v1/health")
```

#### Performance Benchmarks
```python
# tests/performance/test_benchmarks.py
import pytest
from src.agents.insight_engine import InsightEngine

class TestPerformanceBenchmarks:
    @pytest.mark.benchmark
    def test_sentiment_analysis_performance(self, benchmark):
        """Benchmark sentiment analysis performance"""
        engine = InsightEngine(test_config)
        
        def run_analysis():
            return asyncio.run(engine.analyze_sentiment("Test text for analysis"))
        
        result = benchmark(run_analysis)
        
        # Performance assertions
        assert result["processing_time"] < 2.0  # 2 seconds max
        assert result["confidence"] > 0.8
    
    @pytest.mark.benchmark
    def test_search_performance(self, benchmark):
        """Benchmark search performance"""
        search_tool = TavilySearchTool(test_config)
        
        def run_search():
            return asyncio.run(search_tool.execute({
                "query": "electric vehicle news",
                "max_results": 10
            }))
        
        result = benchmark(run_search)
        
        # Performance assertions
        assert result["execution_time"] < 5.0  # 5 seconds max
        assert result["success"] is True
```

### 5. Security Testing

#### Scope
- Authentication and authorization
- Input validation and sanitization
- API rate limiting
- Data encryption
- SQL injection prevention
- XSS prevention

#### Tools
- **Bandit**: Static security analysis
- **Safety**: Dependency vulnerability scanning
- **OWASP ZAP**: Dynamic security testing
- **pytest-security**: Security test helpers

#### Security Tests
```python
# tests/security/test_authentication.py
import pytest
from httpx import AsyncClient

class TestAuthentication:
    @pytest.mark.asyncio
    async def test_valid_authentication(self):
        """Test valid user authentication"""
        async with AsyncClient() as client:
            response = await client.post("/api/v1/auth/login", json={
                "username": "valid_user",
                "password": "valid_password"
            })
            
            assert response.status_code == 200
            assert "access_token" in response.json()
            assert "refresh_token" in response.json()
    
    @pytest.mark.asyncio
    async def test_invalid_authentication(self):
        """Test invalid user authentication"""
        async with AsyncClient() as client:
            response = await client.post("/api/v1/auth/login", json={
                "username": "invalid_user",
                "password": "wrong_password"
            })
            
            assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_token_validation(self):
        """Test JWT token validation"""
        async with AsyncClient() as client:
            # Try to access protected endpoint without token
            response = await client.get("/api/v1/query/test-id")
            assert response.status_code == 401
            
            # Try with invalid token
            response = await client.get(
                "/api/v1/query/test-id",
                headers={"Authorization": "Bearer invalid_token"}
            )
            assert response.status_code == 401

# tests/security/test_input_validation.py
class TestInputValidation:
    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self):
        """Test SQL injection prevention"""
        malicious_input = "'; DROP TABLE users; --"
        
        async with AsyncClient() as client:
            response = await client.post("/api/v1/query", json={
                "query": malicious_input,
                "agents": ["insight-engine"]
            })
            
            # Should handle gracefully without database errors
            assert response.status_code in [200, 400, 422]
    
    @pytest.mark.asyncio
    async def test_xss_prevention(self):
        """Test XSS prevention"""
        xss_payload = "<script>alert('xss')</script>"
        
        async with AsyncClient() as client:
            response = await client.post("/api/v1/query", json={
                "query": xss_payload,
                "agents": ["insight-engine"]
            })
            
            assert response.status_code in [200, 400, 422]
            
            # If successful, response should not contain unescaped scripts
            if response.status_code == 200:
                content = response.text
                assert "<script>" not in content
```

## Test Data Management

### Test Data Strategy
1. **Factory Pattern**: Use factories for generating test data
2. **Fixtures**: Reusable test data setup
3. **Isolation**: Each test gets isolated data
4. **Cleanup**: Automatic cleanup after tests
5. **Realistic Data**: Use production-like data structures

### Data Factories
```python
# tests/factories.py
import factory
from datetime import datetime, timedelta
from src.state.models import QueryState, SentimentData

class QueryStateFactory(factory.Factory):
    class Meta:
        model = QueryState
    
    query_id = factory.Faker('uuid4')
    user_query = factory.Faker('sentence')
    status = "pending"
    created_at = factory.LazyFunction(datetime.now)
    updated_at = factory.LazyFunction(datetime.now)
    parameters = factory.LazyFunction(lambda: {"time_range": "7d"})
    active_agents = factory.LazyFunction(lambda: ["insight-engine"])
    agent_status = factory.LazyFunction(dict)
    agent_results = factory.LazyFunction(dict)
    search_results = factory.LazyFunction(dict)
    analysis_results = factory.LazyFunction(dict)
    sentiment_data = factory.LazyFunction(dict)
    media_data = factory.LazyFunction(dict)
    summary = None
    detailed_analysis = None
    report_data = None
    errors = factory.LazyFunction(list)
    warnings = factory.LazyFunction(list)
    processing_time = None
    tokens_used = None
    data_points_processed = None

class SentimentDataFactory(factory.Factory):
    class Meta:
        model = SentimentData
    
    text = factory.Faker('paragraph')
    sentiment = factory.Iterator(['positive', 'negative', 'neutral'])
    confidence = factory.Faker('pyfloat', min_value=0.0, max_value=1.0)
    source = factory.Faker('company')
    timestamp = factory.LazyFunction(datetime.now)
    entities = factory.LazyFunction(list)
    keywords = factory.LazyFunction(lambda: factory.Faker('words', nb=3).generate())
    metadata = factory.LazyFunction(dict)
```

## Continuous Integration

### CI/CD Pipeline
```yaml
# .github/workflows/test.yml
name: Test Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run unit tests
      run: |
        pytest tests/unit/ -v --cov=src --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: bettafish_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: 3.11
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run integration tests
      env:
        DATABASE_URL: postgresql://postgres:test@localhost:5432/bettafish_test
        REDIS_URL: redis://localhost:6379/0
      run: |
        pytest tests/integration/ -v

  e2e-tests:
    runs-on: ubuntu-latest
    needs: integration-tests
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: 3.11
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Start services
      run: |
        docker-compose -f docker-compose.test.yml up -d
        sleep 30  # Wait for services to be ready
    
    - name: Run E2E tests
      run: |
        pytest tests/e2e/ -v
    
    - name: Stop services
      run: |
        docker-compose -f docker-compose.test.yml down

  security-scan:
    runs-on: ubuntu-latest
    needs: unit-tests
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Run Bandit security scan
      run: |
        pip install bandit
        bandit -r src/ -f json -o bandit-report.json
    
    - name: Run Safety dependency scan
      run: |
        pip install safety
        safety check --json --output safety-report.json
    
    - name: Upload security reports
      uses: actions/upload-artifact@v3
      with:
        name: security-reports
        path: "*.json"
```

## Test Environment Management

### Environment Configuration
```python
# tests/conftest.py
import pytest
import asyncio
from docker import DockerClient
from src.state.store import RedisStateStore
from src.database.connection import DatabaseManager

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def docker_client():
    """Docker client for test container management."""
    client = DockerClient.from_env()
    yield client
    client.close()

@pytest.fixture(scope="session")
async def test_redis(docker_client):
    """Redis instance for testing."""
    container = docker_client.containers.run(
        "redis:7-alpine",
        ports={"6379/tcp": None},
        detach=True
    )
    
    # Get mapped port
    container.reload()
    port = container.ports["6379/tcp"][0]["HostPort"]
    
    # Wait for Redis to be ready
    await asyncio.sleep(2)
    
    yield f"redis://localhost:{port}"
    
    container.stop()
    container.remove()

@pytest.fixture(scope="session")
async def test_database(docker_client):
    """PostgreSQL instance for testing."""
    container = docker_client.containers.run(
        "postgres:15-alpine",
        environment={
            "POSTGRES_PASSWORD": "test",
            "POSTGRES_DB": "bettafish_test"
        },
        ports={"5432/tcp": None},
        detach=True
    )
    
    # Get mapped port
    container.reload()
    port = container.ports["5432/tcp"][0]["HostPort"]
    
    # Wait for database to be ready
    await asyncio.sleep(5)
    
    yield f"postgresql://postgres:test@localhost:{port}/bettafish_test"
    
    container.stop()
    container.remove()

@pytest.fixture
async def state_store(test_redis):
    """Redis state store for testing."""
    store = RedisStateStore(test_redis)
    await store.initialize()
    yield store
    await store.cleanup()

@pytest.fixture
async def database_manager(test_database):
    """Database manager for testing."""
    manager = DatabaseManager(test_database)
    await manager.initialize()
    await manager.create_tables()
    yield manager
    await manager.cleanup()
```

## Quality Gates

### Test Success Criteria
1. **Unit Tests**: 100% pass rate, 90%+ coverage
2. **Integration Tests**: 100% pass rate
3. **E2E Tests**: 95%+ pass rate
4. **Performance Tests**: Meet defined benchmarks
5. **Security Tests**: No high-severity vulnerabilities

### Release Criteria
- All test suites passing
- Performance benchmarks met
- Security scan clean
- Documentation updated
- Code review completed

This comprehensive testing strategy ensures the modernized BettaFish system meets high standards for reliability, performance, and security throughout its lifecycle.