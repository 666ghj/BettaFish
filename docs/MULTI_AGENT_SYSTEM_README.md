# BettaFish Multi-Agent System

## Overview

Welcome to BettaFish's multi-agent architecture for Western media monitoring! This system coordinates specialized AI agents to collect, process, and analyze news from across the political spectrum and social media platforms.

**Architecture:** Multi-Agent Microservices
**Communication:** Message Bus (Redis Pub/Sub)
**Based on:** Anthropic Agent Best Practices

---

## Quick Start

### 1. Read the Documentation

Start here in this order:

1. **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - Understand the overall architecture
2. **[AGENT_PERSONAS.md](AGENT_PERSONAS.md)** - Learn about each agent's role
3. **[INTER_AGENT_COMMUNICATION.md](INTER_AGENT_COMMUNICATION.md)** - Understand how agents talk
4. **[PROJECT_PLAN.md](PROJECT_PLAN.md)** - See the development roadmap

### 2. Set Up Your Environment

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# Set up database
psql -U your_user -d your_database -f MindSpider/schema/western_media_tables.sql

# Set up Redis (for message bus)
docker run -d -p 6379:6379 redis:alpine
```

### 3. Test Individual Agents

```bash
# Test Reddit agent
python agents/platform_agents/reddit_agent.py

# Test other agents as you build them
```

### 4. Start the System

```bash
# Start all agents (when fully implemented)
python start_agents.py
```

---

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  Project Manager Agent                       │
│              (Orchestrates everything)                       │
└────────────────┬────────────────────────────────────────────┘
                 │
        ┌────────┴────────┬──────────┬────────────┬──────────┐
        │                 │          │            │          │
   ┌────▼────┐      ┌────▼────┐  ┌─▼──┐    ┌────▼────┐  ┌──▼──┐
   │Platform │      │  Data   │  │Ana-│    │Protec-  │  │ QA  │
   │ Agents  │      │ Agents  │  │lysis│    │tion     │  │Agents│
   └─────────┘      └─────────┘  └────┘    └─────────┘  └─────┘
        │                 │          │            │          │
   ┌────┴────┐       ┌────┴────┐   │       ┌────┴────┐    │
   │ Reddit  │       │Pipeline │   │       │  Rate   │    │
   │ Twitter │       │Storage  │   │       │ Limiter │    │
   │ YouTube │       │Validate │   │       │  Health │    │
   │HackerNews│      │Dedupe   │   │       │  Error  │    │
   │  News   │       └─────────┘   │       │Recovery │    │
   └─────────┘                      │       └─────────┘    │
                                    │                       │
                               ┌────┴────┐           ┌─────┴────┐
                               │Sentiment│           │   Test   │
                               │  Topic  │           │ Monitor  │
                               │  Bias   │           └──────────┘
                               └─────────┘
```

### Data Flow

```
1. Project Manager assigns tasks
         │
         ▼
2. Platform Agents collect data (Reddit, Twitter, etc.)
         │
         ▼
3. Rate Limiter approves requests
         │
         ▼
4. Data collected and sent to Data Pipeline
         │
         ▼
5. Validation Agent checks quality
         │
         ▼
6. Deduplication Agent removes duplicates
         │
         ▼
7. Storage Agent saves to database
         │
         ▼
8. Analysis Agents process (Sentiment, Topic, Bias)
         │
         ▼
9. Results available for querying
```

---

## Agent Types

### Coordinator Agents (1)

**Project Manager Agent**
- Coordinates all other agents
- Distributes tasks
- Monitors system health
- Makes high-level decisions

### Platform Agents (6)

Each agent specializes in one platform:

1. **Reddit Agent** - Monitors subreddits
2. **Twitter Agent** - Monitors Twitter accounts
3. **YouTube Agent** - Monitors YouTube channels
4. **HackerNews Agent** - Monitors HN stories
5. **TikTok Agent** - Monitors TikTok content
6. **News RSS Agent** - Monitors news RSS feeds

### Data Agents (4)

Handle data processing:

1. **Pipeline Agent** - Orchestrates data flow
2. **Storage Agent** - Database operations
3. **Validation Agent** - Data quality checks
4. **Deduplication Agent** - Removes duplicates

### Analysis Agents (3)

Provide insights:

1. **Sentiment Agent** - Sentiment analysis
2. **Topic Agent** - Topic extraction
3. **Bias Agent** - Political bias detection

### Protection Agents (3)

Ensure system safety:

1. **Rate Limiter Agent** - Prevents IP bans
2. **Health Monitor Agent** - System health checks
3. **Error Recovery Agent** - Handles errors

### QA Agents (2)

Quality assurance:

1. **Test Agent** - Automated testing
2. **Monitoring Agent** - Performance metrics

---

## Creating a New Agent

### Step 1: Choose Agent Type

Determine which category your agent belongs to:
- Platform Agent (monitors a new platform)
- Data Agent (processes data)
- Analysis Agent (provides insights)
- Protection Agent (ensures safety)
- QA Agent (testing/monitoring)

### Step 2: Copy the Template

```bash
# For a platform agent
cp agents/shared/base_agent.py agents/platform_agents/my_new_agent.py
```

### Step 3: Implement Required Methods

```python
from agents.shared.base_agent import BaseAgent

class MyNewAgent(BaseAgent):
    def __init__(self, config):
        super().__init__("my_new_agent", config)

        # Define personality
        self.personality = {
            'trait1': 'description',
            'trait2': 'description'
        }

    async def _initialize(self):
        """Initialize resources"""
        # Connect to APIs
        # Load models
        # Set up connections
        pass

    async def _shutdown(self):
        """Cleanup resources"""
        # Close connections
        # Save state
        pass

    async def _execute_task(self, task):
        """Execute a task"""
        # Main task logic here
        result = await self._do_work(task)
        return result

    async def _custom_health_check(self):
        """Agent-specific health checks"""
        return {
            'custom_metric_1': value1,
            'custom_metric_2': value2
        }
```

### Step 4: Define in Personas Document

Add your agent to `AGENT_PERSONAS.md`:

```markdown
## X. My New Agent

### Role
[One-line description]

### Personality
- **Trait 1**: Description
- **Trait 2**: Description

### Expertise
- Skill 1
- Skill 2

### Responsibilities
- Responsibility 1
- Responsibility 2

### Configuration
```yaml
key1: value1
key2: value2
```
```

### Step 5: Write Tests

```python
# tests/unit/test_my_new_agent.py
import pytest
from agents.platform_agents.my_new_agent import MyNewAgent

@pytest.mark.asyncio
async def test_agent_initialization():
    config = {...}
    agent = MyNewAgent(config)
    await agent.initialize()
    assert agent.state == AgentState.READY

@pytest.mark.asyncio
async def test_agent_task_execution():
    agent = MyNewAgent(config)
    await agent.initialize()

    task = {'task_type': 'test'}
    result = await agent.execute_task(task)

    assert result['status'] == 'completed'
```

### Step 6: Update Project Plan

Add implementation tasks to `PROJECT_PLAN.md`

---

## Message Bus Communication

### Sending a Message

```python
# Send to specific agent
await agent.send_message(
    to='data_pipeline_agent',
    message_type='data_delivery',
    payload={
        'data': [...],
        'count': 100
    },
    priority=3
)

# Broadcast to all agents
await agent.broadcast_message(
    message_type='system_announcement',
    payload={
        'message': 'System maintenance in 10 minutes'
    }
)
```

### Message Types

See [INTER_AGENT_COMMUNICATION.md](INTER_AGENT_COMMUNICATION.md) for full list:

- `task_assignment` - Assign task to agent
- `task_ack` - Acknowledge task
- `task_status` - Update task progress
- `task_completed` - Task finished
- `data_delivery` - Send data to another agent
- `rate_limit_check` - Check rate limits
- `health_status` - Health check
- `error_report` - Report error
- `alert` - Urgent alert
- `command` - Control command

---

## Configuration

### Global Config (.env)

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_USER=bettafish
DB_PASSWORD=secret
DB_NAME=bettafish

# Message Bus
REDIS_HOST=localhost
REDIS_PORT=6379

# API Keys
REDDIT_CLIENT_ID=xxx
REDDIT_CLIENT_SECRET=yyy
YOUTUBE_API_KEY=zzz
```

### Agent Config (config/agents/*.yaml)

```yaml
# config/agents/reddit_agent.yaml
agent_name: reddit_agent
rate_limit_delay: 2.0
posts_per_subreddit: 25
fetch_comments: true
max_comments_per_post: 50

subreddits:
  political_left:
    - politics
    - democrats
  political_right:
    - conservative
    - republican
  tech:
    - technology
    - programming
```

### Platform Config (config/platforms/*.yaml)

```yaml
# config/platforms/reddit.yaml
platform: reddit
api_type: official
rate_limits:
  requests_per_minute: 30
  requests_per_hour: 60
  delay_between_requests: 2.0

auth:
  client_id: ${REDDIT_CLIENT_ID}
  client_secret: ${REDDIT_CLIENT_SECRET}
  user_agent: BettaFish/1.0
```

---

## Testing

### Unit Tests

```bash
# Test individual agents
pytest tests/unit/test_reddit_agent.py -v

# Test all units
pytest tests/unit/ -v

# With coverage
pytest tests/unit/ --cov=agents --cov-report=html
```

### Integration Tests

```bash
# Test agent coordination
pytest tests/integration/test_agent_coordination.py -v

# Test data pipeline
pytest tests/integration/test_data_pipeline.py -v
```

### End-to-End Tests

```bash
# Test complete workflows
pytest tests/e2e/test_monitoring_workflow.py -v
```

---

## Monitoring

### Health Checks

```bash
# Check all agents
curl http://localhost:5000/api/agents/health

# Check specific agent
curl http://localhost:5000/api/agents/reddit_agent/health
```

### Metrics Dashboard

Access at: http://localhost:3000/dashboard

Metrics include:
- Tasks completed per agent
- Error rates
- Response times
- Rate limit usage
- System health

### Logs

```bash
# View agent logs
tail -f logs/agents/reddit_agent.log

# View system logs
tail -f logs/system/system.log

# View all logs
tail -f logs/**/*.log
```

---

## Common Workflows

### Daily Monitoring

```python
# Triggered by scheduler at 8 AM
task = {
    'task_id': 'daily-monitoring-001',
    'task_type': 'monitor_all',
    'scheduled_time': '2025-01-19T08:00:00Z'
}

# Project Manager distributes to platform agents
await project_manager.execute_task(task)
```

### On-Demand Search

```python
# User requests search
task = {
    'task_id': 'search-001',
    'task_type': 'search',
    'query': 'artificial intelligence',
    'platforms': ['reddit', 'twitter', 'hackernews']
}

# Search across platforms
results = await project_manager.execute_task(task)
```

### Breaking News Detection

```python
# Continuous monitoring for breaking news
while True:
    news = await news_agent.check_breaking_news()

    if news:
        # Alert all stakeholders
        await project_manager.broadcast_alert(news)

    await asyncio.sleep(300)  # Check every 5 minutes
```

---

## Deployment

### Local Development

```bash
# Start services
docker-compose up -d

# Start agents
python start_agents.py
```

### Production (Docker)

```bash
# Build images
docker build -t bettafish/agents:latest .

# Deploy with docker-compose
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose ps
```

### Production (Kubernetes)

```bash
# Deploy to Kubernetes
kubectl apply -f k8s/

# Scale agents
kubectl scale deployment reddit-agent --replicas=3

# Check status
kubectl get pods -l app=bettafish
```

---

## Troubleshooting

### Agent Won't Start

**Problem:** Agent fails during initialization

**Solutions:**
1. Check API credentials in `.env`
2. Verify database connection
3. Check Redis connection
4. Review agent logs: `logs/agents/[agent_name].log`

### High Error Rate

**Problem:** Agent showing >10% error rate

**Solutions:**
1. Check rate limits - may be hitting API limits
2. Verify API credentials still valid
3. Check network connectivity
4. Review error logs for patterns
5. Consider reducing collection frequency

### IP Ban

**Problem:** IP banned from platform

**Solutions:**
1. Stop all crawling immediately
2. Wait 24-48 hours
3. Review rate limiting configuration
4. Consider using proxies
5. Reduce rate limits by 50%

### Agent Communication Failure

**Problem:** Agents not communicating

**Solutions:**
1. Check Redis is running: `redis-cli ping`
2. Verify message bus configuration
3. Check network connectivity
4. Review agent logs for connection errors

---

## Best Practices

### 1. Always Use Rate Limiting

```python
# GOOD: Check rate limit before request
await agent._check_rate_limit()
result = await make_api_call()

# BAD: No rate limiting
result = await make_api_call()  # Risk of ban!
```

### 2. Handle Errors Gracefully

```python
# GOOD: Try-except with reporting
try:
    result = await risky_operation()
except Exception as e:
    await agent._report_error(task_id, e)
    # Use fallback or skip

# BAD: Let exceptions crash agent
result = await risky_operation()  # Will crash!
```

### 3. Log Important Events

```python
# GOOD: Structured logging
agent.log_info(f"Collected {count} posts from r/{subreddit}")

# BAD: No logging
# (makes debugging impossible)
```

### 4. Use Correlation IDs

```python
# GOOD: Link related messages
await agent.send_message(
    to='pipeline',
    message_type='data',
    payload={...},
    correlation_id=original_task.correlation_id  # Links messages
)

# BAD: No correlation
await agent.send_message(...)  # Can't trace workflow
```

### 5. Validate Configuration

```python
# GOOD: Validate on startup
async def _initialize(self):
    if not self.config.get('api_key'):
        raise ValueError("API key required")

# BAD: Fail later during execution
async def _execute_task(self, task):
    api_key = self.config.get('api_key')  # Might be None!
```

---

## Resources

### Documentation

- [Project Structure](PROJECT_STRUCTURE.md)
- [Agent Personas](AGENT_PERSONAS.md)
- [Inter-Agent Communication](INTER_AGENT_COMMUNICATION.md)
- [Project Plan](PROJECT_PLAN.md)
- [Western Media Setup](../WESTERN_MEDIA_SETUP.md)
- [Twitter Migration](../TWITTER_MIGRATION_GUIDE.md)

### External References

- [Anthropic Sub-Agent Best Practices](https://code.claude.com/docs/en/sub-agents)
- [Anthropic Agent Skills](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices)
- [Redis Pub/Sub Documentation](https://redis.io/docs/manual/pubsub/)
- [Async/Await in Python](https://docs.python.org/3/library/asyncio.html)

---

## FAQ

**Q: How do I add a new platform to monitor?**

A: Create a new Platform Agent following the template in `agents/shared/base_agent.py`. See "Creating a New Agent" section above.

**Q: Can agents run on different machines?**

A: Yes! As long as they can all connect to the same Redis message bus and database.

**Q: How do I scale an agent horizontally?**

A: Deploy multiple instances of the same agent. The message bus will distribute tasks across instances.

**Q: What happens if an agent crashes?**

A: The Error Recovery Agent detects the crash and can restart the agent automatically. Configure auto-restart in the agent's deployment config.

**Q: How do I prioritize certain platforms over others?**

A: Set higher priorities in task assignments. The Task Dispatcher will process higher priority tasks first.

**Q: Can I run just one agent for testing?**

A: Yes! Each agent can run independently. Just initialize and execute tasks directly.

---

## Contributing

### Adding New Features

1. Create feature branch: `git checkout -b feature/new-agent`
2. Implement agent following template
3. Write tests (>80% coverage required)
4. Update documentation
5. Submit pull request

### Code Style

- Follow PEP 8
- Use type hints
- Write docstrings for all classes/methods
- Keep functions focused and small

### Testing Requirements

- Unit tests for all new code
- Integration tests for agent interactions
- >80% code coverage
- All tests must pass

---

## Support

- **Documentation**: See `docs/` directory
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions

---

**Version:** 1.0
**Last Updated:** 2025-01-19
**Status:** In Development
