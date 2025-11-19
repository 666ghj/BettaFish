# BettaFish Western Media Monitoring - Project Structure

## Overview

BettaFish is a multi-agent public opinion analysis system for monitoring Western media sources (USA political news, social media, technical news) using specialized AI agents coordinated through a microservices-style architecture.

**Version:** 2.0 (Western Media Edition)
**Last Updated:** 2025-01-19
**Architecture:** Multi-Agent Microservices

---

## Project Directory Structure

```
BettaFish/
│
├── docs/                               # Project documentation
│   ├── PROJECT_STRUCTURE.md           # This file
│   ├── PROJECT_PLAN.md                # Detailed project plan with phases
│   ├── AGENT_PERSONAS.md              # Agent roles and responsibilities
│   ├── INTER_AGENT_COMMUNICATION.md   # Agent coordination protocols
│   ├── API_REFERENCE.md               # API documentation
│   └── DEPLOYMENT_GUIDE.md            # Deployment instructions
│
├── agents/                            # Multi-agent system components
│   ├── __init__.py
│   ├── coordinator/                   # Main orchestration agent
│   │   ├── __init__.py
│   │   ├── project_manager_agent.py   # Coordinates all agents
│   │   ├── task_dispatcher.py         # Distributes tasks to agents
│   │   └── status_tracker.py          # Tracks project status
│   │
│   ├── platform_agents/               # Platform-specific crawling agents
│   │   ├── __init__.py
│   │   ├── reddit_agent.py            # Reddit monitoring specialist
│   │   ├── twitter_agent.py           # Twitter/X monitoring specialist
│   │   ├── youtube_agent.py           # YouTube monitoring specialist
│   │   ├── hackernews_agent.py        # HackerNews monitoring specialist
│   │   ├── tiktok_agent.py            # TikTok monitoring specialist
│   │   └── news_rss_agent.py          # RSS news monitoring specialist
│   │
│   ├── data_agents/                   # Data processing agents
│   │   ├── __init__.py
│   │   ├── pipeline_agent.py          # Data pipeline orchestration
│   │   ├── storage_agent.py           # Database operations
│   │   ├── validation_agent.py        # Data validation and cleaning
│   │   └── deduplication_agent.py     # Remove duplicate content
│   │
│   ├── analysis_agents/               # Analysis and insights agents
│   │   ├── __init__.py
│   │   ├── sentiment_agent.py         # Sentiment analysis
│   │   ├── topic_agent.py             # Topic extraction
│   │   ├── trend_agent.py             # Trend detection
│   │   └── bias_agent.py              # Political bias detection
│   │
│   ├── protection_agents/             # IP and security agents
│   │   ├── __init__.py
│   │   ├── rate_limiter_agent.py      # Rate limiting management
│   │   ├── proxy_agent.py             # Proxy rotation (optional)
│   │   ├── health_monitor_agent.py    # System health monitoring
│   │   └── error_recovery_agent.py    # Error handling and recovery
│   │
│   ├── qa_agents/                     # Quality assurance agents
│   │   ├── __init__.py
│   │   ├── test_agent.py              # Automated testing
│   │   ├── validation_agent.py        # Data validation
│   │   └── monitoring_agent.py        # Performance monitoring
│   │
│   └── shared/                        # Shared utilities for agents
│       ├── __init__.py
│       ├── message_bus.py             # Inter-agent messaging
│       ├── state_store.py             # Shared state management
│       ├── config_manager.py          # Configuration management
│       └── logger.py                  # Centralized logging
│
├── MindSpider/                        # Existing crawler infrastructure
│   ├── BroadTopicExtraction/          # Topic extraction module
│   │   ├── get_today_news.py
│   │   ├── western_news_collector.py
│   │   └── database_manager.py
│   │
│   ├── DeepSentimentCrawling/         # Deep crawling module
│   │   ├── western_platforms/         # Western platform crawlers
│   │   │   ├── reddit_crawler.py
│   │   │   ├── twitter_crawler_v2.py
│   │   │   ├── youtube_crawler.py
│   │   │   ├── hackernews_crawler.py
│   │   │   ├── rate_limiter.py
│   │   │   └── config.py
│   │   │
│   │   └── MediaCrawler/              # Existing Chinese platforms
│   │
│   └── schema/                        # Database schemas
│       ├── mindspider_tables.sql
│       └── western_media_tables.sql
│
├── QueryEngine/                       # Search and query agent
│   └── (existing implementation)
│
├── MediaEngine/                       # Multimodal analysis agent
│   └── (existing implementation)
│
├── InsightEngine/                     # Database mining agent
│   └── (existing implementation)
│
├── ReportEngine/                      # Report generation agent
│   └── (existing implementation)
│
├── ForumEngine/                       # Agent collaboration forum
│   └── (existing implementation)
│
├── tests/                             # Test suite
│   ├── unit/                          # Unit tests
│   │   ├── test_reddit_agent.py
│   │   ├── test_twitter_agent.py
│   │   └── ...
│   ├── integration/                   # Integration tests
│   │   ├── test_agent_coordination.py
│   │   └── test_data_pipeline.py
│   └── e2e/                           # End-to-end tests
│       └── test_monitoring_workflow.py
│
├── config/                            # Configuration files
│   ├── agents/                        # Agent-specific configs
│   │   ├── reddit_agent.yaml
│   │   ├── twitter_agent.yaml
│   │   └── ...
│   ├── platforms/                     # Platform configs
│   │   ├── reddit.yaml
│   │   ├── twitter.yaml
│   │   └── ...
│   ├── rate_limits.yaml               # Rate limiting rules
│   ├── monitoring_schedule.yaml       # Monitoring schedules
│   └── ip_protection.yaml             # IP protection settings
│
├── scripts/                           # Utility scripts
│   ├── setup/                         # Setup scripts
│   │   ├── init_database.sh
│   │   ├── create_agents.py
│   │   └── validate_config.py
│   ├── deployment/                    # Deployment scripts
│   │   ├── deploy.sh
│   │   └── rollback.sh
│   └── maintenance/                   # Maintenance scripts
│       ├── cleanup_old_data.py
│       └── health_check.py
│
├── logs/                              # Application logs
│   ├── agents/                        # Agent-specific logs
│   ├── platforms/                     # Platform-specific logs
│   └── system/                        # System logs
│
├── data/                              # Data directory
│   ├── cache/                         # Cached data
│   ├── exports/                       # Data exports
│   └── temp/                          # Temporary files
│
├── .env.example                       # Environment variables template
├── .env                               # Environment variables (gitignored)
├── requirements.txt                   # Python dependencies
├── docker-compose.yml                 # Docker orchestration
├── Dockerfile                         # Docker image definition
├── README.md                          # Project overview
├── WESTERN_MEDIA_SETUP.md            # Western media setup guide
├── TWITTER_MIGRATION_GUIDE.md        # Twitter migration guide
└── test_western_crawlers.py          # Quick test script

```

---

## Core Components

### 1. Agent Coordinator (`agents/coordinator/`)

**Purpose:** Orchestrates all specialist agents, manages task distribution, and ensures system coherence.

**Key Files:**
- `project_manager_agent.py` - Main orchestration logic
- `task_dispatcher.py` - Routes tasks to appropriate agents
- `status_tracker.py` - Monitors overall system status

### 2. Platform Agents (`agents/platform_agents/`)

**Purpose:** Specialized agents for each social media platform, each with deep knowledge of their platform's API, rate limits, and best practices.

**Agents:**
- **Reddit Agent** - Monitors subreddits (politics, tech, news)
- **Twitter Agent** - Monitors Twitter accounts and hashtags
- **YouTube Agent** - Monitors YouTube channels and videos
- **HackerNews Agent** - Monitors HN stories and comments
- **TikTok Agent** - Monitors TikTok content (US)
- **News RSS Agent** - Monitors news RSS feeds

### 3. Data Agents (`agents/data_agents/`)

**Purpose:** Handle data pipeline, storage, validation, and deduplication.

**Agents:**
- **Pipeline Agent** - Orchestrates data flow
- **Storage Agent** - Database operations
- **Validation Agent** - Data quality checks
- **Deduplication Agent** - Prevents duplicate storage

### 4. Analysis Agents (`agents/analysis_agents/`)

**Purpose:** Perform sentiment analysis, topic extraction, trend detection, and bias analysis.

**Agents:**
- **Sentiment Agent** - Sentiment analysis
- **Topic Agent** - Topic extraction and clustering
- **Trend Agent** - Trend and anomaly detection
- **Bias Agent** - Political bias detection

### 5. Protection Agents (`agents/protection_agents/`)

**Purpose:** Protect against IP bans, manage rate limiting, handle errors, and ensure system health.

**Agents:**
- **Rate Limiter Agent** - Enforces rate limits
- **Proxy Agent** - Manages proxy rotation (if needed)
- **Health Monitor Agent** - System health checks
- **Error Recovery Agent** - Handles and recovers from errors

### 6. QA Agents (`agents/qa_agents/`)

**Purpose:** Automated testing, validation, and monitoring.

**Agents:**
- **Test Agent** - Runs automated tests
- **Validation Agent** - Validates configurations
- **Monitoring Agent** - Monitors performance metrics

---

## Communication Patterns

### Message Bus Architecture

All agents communicate through a centralized message bus:

```python
from agents.shared.message_bus import MessageBus

# Agent publishes a message
bus.publish('data.collected', {
    'platform': 'reddit',
    'posts': 150,
    'timestamp': '2025-01-19T10:00:00Z'
})

# Agent subscribes to messages
bus.subscribe('data.collected', process_collected_data)
```

### Agent States

Agents follow a standard state machine:

```
IDLE → INITIALIZING → READY → WORKING → COMPLETED → IDLE
                                   ↓
                               ERROR → RECOVERING → READY
```

---

## Configuration Management

### Hierarchical Configuration

1. **Global Config** (`.env`) - System-wide settings
2. **Agent Config** (`config/agents/*.yaml`) - Agent-specific settings
3. **Platform Config** (`config/platforms/*.yaml`) - Platform-specific settings
4. **Runtime Config** - Dynamic configuration from database

### Configuration Priority

```
Runtime Config > Platform Config > Agent Config > Global Config > Defaults
```

---

## Data Flow

```
┌──────────────────┐
│ Platform Agents  │
│ (Collect Data)   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Data Pipeline   │
│  Agent           │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Validation      │
│  Agent           │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Deduplication   │
│  Agent           │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Storage         │
│  Agent           │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Analysis        │
│  Agents          │
└──────────────────┘
```

---

## Deployment Architecture

### Local Development

```
Docker Compose:
- PostgreSQL (database)
- Redis (message bus)
- BettaFish API (Flask)
- Agent Services (multiple containers)
```

### Production

```
Kubernetes Cluster:
- Database (managed PostgreSQL)
- Message Queue (managed Redis/RabbitMQ)
- API Gateway
- Agent Pods (auto-scaling)
- Monitoring (Prometheus + Grafana)
```

---

## Development Workflow

### 1. Feature Development

```bash
# Create feature branch
git checkout -b feature/new-platform-agent

# Implement agent
cd agents/platform_agents/
touch new_platform_agent.py

# Write tests
cd ../../tests/unit/
touch test_new_platform_agent.py

# Run tests
pytest tests/unit/test_new_platform_agent.py

# Commit and push
git add .
git commit -m "Add new platform agent"
git push origin feature/new-platform-agent
```

### 2. Agent Testing

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# End-to-end tests
pytest tests/e2e/

# Coverage report
pytest --cov=agents tests/
```

### 3. Code Review

All changes require:
- Unit tests (>80% coverage)
- Integration tests
- Documentation updates
- Agent persona alignment check

---

## Monitoring and Observability

### Metrics

Each agent exposes metrics:
- Task completion rate
- Average processing time
- Error rate
- Resource usage

### Logging

Structured logging format:
```json
{
  "timestamp": "2025-01-19T10:00:00Z",
  "level": "INFO",
  "agent": "reddit_agent",
  "message": "Collected 150 posts from r/politics",
  "metadata": {
    "subreddit": "politics",
    "post_count": 150,
    "duration_ms": 2500
  }
}
```

### Health Checks

Each agent implements:
- `/health` - Basic health check
- `/ready` - Readiness check
- `/metrics` - Prometheus metrics

---

## Security Considerations

### IP Protection

- Rate limiting enforced by dedicated agent
- Proxy rotation (optional)
- User agent rotation
- Request spreading

### Data Security

- API keys stored in environment variables
- Database encryption at rest
- TLS for all external communication
- Regular security audits

### Account Safety

- Separate scraper accounts
- Account rotation for high-risk platforms
- Activity monitoring
- Automated account health checks

---

## Scalability

### Horizontal Scaling

Agents can be scaled independently:
```yaml
# docker-compose.yml
reddit_agent:
  replicas: 3  # Run 3 instances

twitter_agent:
  replicas: 5  # Run 5 instances
```

### Load Distribution

- Round-robin task distribution
- Platform-based partitioning
- Priority queues for urgent tasks

---

## Disaster Recovery

### Backup Strategy

- **Database**: Daily full backups, hourly incrementals
- **Configuration**: Version controlled in Git
- **Logs**: Archived to S3/cloud storage

### Recovery Procedures

1. **Agent Failure**: Auto-restart with exponential backoff
2. **Database Failure**: Restore from latest backup
3. **Complete System Failure**: Deploy from Docker images

---

## Documentation Standards

### Agent Documentation

Each agent must have:
```python
"""
Agent Name: Reddit Monitoring Agent
Purpose: Monitor Reddit subreddits for political and technical discussions
Inputs: List of subreddits, monitoring schedule
Outputs: Reddit posts and comments in standardized format
Dependencies: Reddit API credentials, rate limiter agent
Configuration: config/agents/reddit_agent.yaml
"""
```

### Code Comments

- Function docstrings (Google style)
- Inline comments for complex logic
- Type hints for all functions

---

## Change Management

### Version Control

- Main branch: Production-ready code
- Develop branch: Integration branch
- Feature branches: Individual features
- Hotfix branches: Emergency fixes

### Release Process

1. Create release branch
2. Run full test suite
3. Update CHANGELOG.md
4. Tag release
5. Deploy to staging
6. Validate staging
7. Deploy to production
8. Monitor metrics

---

## Contact and Support

**Project Lead:** (Your Name)
**Documentation:** See `docs/` directory
**Issues:** GitHub Issues
**Slack:** #bettafish-dev (if applicable)

---

## References

- [Project Plan](PROJECT_PLAN.md)
- [Agent Personas](AGENT_PERSONAS.md)
- [Inter-Agent Communication](INTER_AGENT_COMMUNICATION.md)
- [Western Media Setup Guide](../WESTERN_MEDIA_SETUP.md)
- [Anthropic Sub-Agent Best Practices](https://docs.anthropic.com/claude/docs/agents-and-tools/sub-agents)
