# BettaFish USA - Team Quick Start Guide

Welcome to the BettaFish USA project! This guide will get you up and running in your first day.

---

## Day 1: Getting Set Up

### 1. Access & Accounts

**Required Access:**
- [ ] GitHub repository: `github.com/[org]/BettaFish`
- [ ] Slack workspace: Join `#bettafish-usa`, `#bettafish-dev`, `#bettafish-standup`
- [ ] Project management: [Jira/Trello board link]
- [ ] Shared documentation: [Google Drive/Notion link]
- [ ] Cloud infrastructure: AWS/GCP console access (DevOps/Backend only)

**API Accounts to Create:**
- [ ] Twitter Developer Account: https://developer.twitter.com/
- [ ] Reddit API: https://www.reddit.com/prefs/apps
- [ ] YouTube Data API: https://console.cloud.google.com/
- [ ] Tavily Search: https://www.tavily.com/
- [ ] LLM APIs: OpenAI, Anthropic, or alternatives

### 2. Development Environment Setup

**Prerequisites:**
```bash
# Required software
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Node.js 18+ (frontend developers)
- Docker & Docker Compose
- Git
```

**Clone & Setup:**
```bash
# Clone the repository
git clone https://github.com/[org]/BettaFish.git
cd BettaFish

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Copy environment template
cp .env.example .env
# IMPORTANT: Edit .env with your API keys!

# Initialize database
python MindSpider/schema/init_database.py

# Run tests to verify setup
pytest tests/ -v
```

**Verify Installation:**
```bash
# Should see all tests passing
pytest tests/

# Start the application
python app.py

# Visit http://localhost:5000
# You should see the BettaFish interface
```

### 3. Code Standards & Tools

**Linting & Formatting:**
```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Format code with black
black .

# Check linting
flake8 .

# Type checking
mypy .
```

**Git Workflow:**
```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes, commit with conventional commits
git commit -m "feat: add Twitter crawler"
git commit -m "fix: resolve rate limiting issue"
git commit -m "docs: update API documentation"

# Push and create PR
git push -u origin feature/your-feature-name
```

### 4. Team Rituals

**Daily Standup:** 9:00 AM EST (15 minutes)
- What did you do yesterday?
- What will you do today?
- Any blockers?

**Sprint Planning:** Monday 10:00 AM (1 hour)
- Review sprint goals
- Assign tasks
- Clarify requirements

**Demo & Retrospective:** Friday 4:00 PM (1 hour)
- Demo completed work
- Discuss what went well / what to improve

---

## Understanding the Codebase

### Project Structure

```
BettaFish/
├── QueryEngine/          # Web search agent (news, blogs)
├── MediaEngine/          # Multimodal content agent (videos, images)
├── InsightEngine/        # Database mining agent (deep analysis)
├── ReportEngine/         # Report generation agent
├── ForumEngine/          # Agent collaboration orchestrator
├── MindSpider/           # Web crawlers (will add USA platforms here)
├── SentimentAnalysisModel/  # Sentiment analysis models
├── templates/            # Flask HTML templates
├── static/               # CSS, JS, images
├── utils/                # Shared utilities
├── config.py             # Global configuration
├── app.py                # Flask application entry point
└── requirements.txt      # Python dependencies
```

### Key Files to Read First

1. **`USA_IMPLEMENTATION_PLAN.md`** - Full project roadmap (READ THIS!)
2. **`ADAPTATION_GUIDE_USA_PLATFORMS.md`** - Technical adaptation details
3. **`config.py`** - Configuration management
4. **`app.py`** - Application entry point
5. **`README.md`** - Original project documentation

### Architecture Overview

```
User Query
    ↓
Flask Web App (app.py)
    ↓
Agent Orchestration
    ├─→ QueryEngine (searches news/web)
    ├─→ MediaEngine (analyzes videos/images)
    ├─→ InsightEngine (queries database)
    └─→ ForumEngine (agents debate findings)
    ↓
ReportEngine (generates HTML report)
    ↓
User receives report
```

---

## Your Role-Specific Guide

### Backend Developers

**Your Focus:** Build platform crawlers and APIs

**Key Tasks (First Week):**
1. Read `MindSpider/DeepSentimentCrawling/MediaCrawler/` to understand existing crawlers
2. Set up Twitter/Reddit/YouTube API accounts
3. Review database schema in `MindSpider/schema/mindspider_tables.sql`
4. Start with Task 2.1 in USA_IMPLEMENTATION_PLAN.md

**Helpful Resources:**
- Twitter API docs: https://developer.twitter.com/en/docs
- Reddit API (PRAW): https://praw.readthedocs.io/
- YouTube API: https://developers.google.com/youtube/v3

**Code You'll Work On:**
```
MindSpider/DeepSentimentCrawling/MediaCrawler/media_platform/usa/
├── twitter/
│   ├── client.py        # Twitter API client
│   ├── core.py          # Crawler logic
│   └── field.py         # Data models
├── reddit/
│   ├── client.py        # Reddit API client (PRAW)
│   └── core.py          # Crawler logic
└── youtube/
    ├── client.py        # YouTube API client
    └── core.py          # Crawler logic
```

### ML/NLP Engineers

**Your Focus:** Sentiment analysis and text processing

**Key Tasks (First Week):**
1. Review `SentimentAnalysisModel/WeiboMultilingualSentiment/`
2. Test existing model on English samples
3. Create USA sentiment test dataset (1,000 samples)
4. Benchmark accuracy on English vs. Chinese

**Helpful Resources:**
- Hugging Face Transformers: https://huggingface.co/transformers/
- Sentiment analysis guide: https://huggingface.co/tasks/sentiment-analysis

**Code You'll Work On:**
```
InsightEngine/tools/sentiment_analyzer.py
SentimentAnalysisModel/WeiboMultilingualSentiment/
```

### Frontend Developers

**Your Focus:** Web interface and report visualization

**Key Tasks (First Week):**
1. Review `templates/index.html` (current interface)
2. Explore `ReportEngine/report_template/` (report generation)
3. Set up React development environment
4. Design mockups for modernized UI

**Helpful Resources:**
- Chart.js: https://www.chartjs.org/
- D3.js: https://d3js.org/
- React: https://react.dev/

**Code You'll Work On:**
```
templates/           # Current Flask templates
static/              # CSS, JavaScript
ReportEngine/        # Report generation
```

### Bilingual Developers

**Your Focus:** Translation and cultural adaptation

**Key Tasks (First Week):**
1. Audit all Chinese prompts in `*/prompts/prompts.py` files
2. Create translation tracking spreadsheet
3. Translate InsightEngine prompts (start here - highest impact)
4. Review with USA culture expert

**Translation Checklist for Each Prompt:**
- [ ] Translate Chinese to English
- [ ] Replace platform names (Weibo → Twitter)
- [ ] Adapt cultural references (Chinese holidays → USA events)
- [ ] Update metrics (转发 → retweets, 点赞 → likes)
- [ ] Test with LLM to ensure it works

**Code You'll Work On:**
```
InsightEngine/prompts/prompts.py    (402 lines)
MediaEngine/prompts/prompts.py      (417 lines)
QueryEngine/prompts/prompts.py      (428 lines)
ReportEngine/report_template/*.md   (419 lines)
```

### QA Engineers

**Your Focus:** Test automation and quality assurance

**Key Tasks (First Week):**
1. Set up test environment with Docker Compose
2. Review existing tests in `tests/` directory
3. Create test plan for USA platform crawlers
4. Set up CI/CD pipeline (GitHub Actions)

**Testing Stack:**
- Unit tests: pytest
- Integration tests: pytest + Docker Compose
- E2E tests: Selenium or Playwright
- Load testing: Locust
- API testing: Postman/newman

**Code You'll Work On:**
```
tests/
├── unit/
│   ├── test_twitter_crawler.py
│   ├── test_reddit_crawler.py
│   └── test_sentiment_analyzer.py
├── integration/
│   ├── test_agent_workflows.py
│   └── test_database.py
└── e2e/
    └── test_complete_query.py
```

### DevOps Engineers

**Your Focus:** Infrastructure, deployment, monitoring

**Key Tasks (First Week):**
1. Set up AWS/GCP accounts and staging environment
2. Configure CI/CD pipeline (GitHub Actions)
3. Set up monitoring (Prometheus, Grafana, Sentry)
4. Review `docker-compose.yml` and create production version

**Infrastructure Stack:**
- Cloud: AWS or GCP
- Container: Docker, Kubernetes (optional)
- CI/CD: GitHub Actions
- Monitoring: Prometheus, Grafana, Sentry
- Logs: ELK stack or CloudWatch

**Key Files:**
```
docker-compose.yml
.github/workflows/
k8s/                    # Kubernetes manifests (to create)
infrastructure/         # Terraform/CloudFormation (to create)
```

---

## Common Tasks & Recipes

### Running the Full System Locally

```bash
# Terminal 1: Start database and Redis
docker-compose up -d db redis

# Terminal 2: Start Flask app
python app.py

# Terminal 3: Start crawler (optional)
cd MindSpider
python main.py --setup

# Visit http://localhost:5000
```

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/unit/test_crawler.py

# With coverage report
pytest --cov=. --cov-report=html
open htmlcov/index.html

# Integration tests (requires Docker)
docker-compose -f docker-compose.test.yml up
pytest tests/integration/
```

### Debugging Tips

```python
# Add breakpoint in code
import pdb; pdb.set_trace()

# Or use ipdb (better interface)
import ipdb; ipdb.set_trace()

# Check logs
tail -f logs/app.log
tail -f logs/agent.log
```

### Database Operations

```bash
# Connect to database
psql -h localhost -U bettafish -d bettafish

# Run migrations
alembic upgrade head

# Create new migration
alembic revision -m "add twitter tables"

# Reset database (CAUTION!)
python MindSpider/schema/init_database.py --reset
```

---

## Communication Guidelines

### Slack Channels

- **#bettafish-usa**: General project discussion
- **#bettafish-dev**: Technical discussions, code questions
- **#bettafish-standup**: Daily standup posts
- **#bettafish-random**: Memes, celebrations, off-topic

### Asking for Help

Good question format:
```
**Issue**: Twitter crawler rate limit exceeded
**What I tried**: Added rate limiter with 450/15min limit
**Error message**: [paste error]
**Code**: [link to GitHub or code snippet]
**Question**: Should we use exponential backoff or queue-based throttling?
```

### Code Review Etiquette

**As Author:**
- Write clear PR description with context
- Keep PRs small (<500 lines if possible)
- Respond to feedback within 24 hours
- Don't take feedback personally

**As Reviewer:**
- Be kind and constructive
- Ask questions, don't make demands
- Approve quickly if no major issues
- Suggest improvements for "nice to have" items

---

## Resources & Links

### Documentation
- [USA Implementation Plan](USA_IMPLEMENTATION_PLAN.md) - Full project plan
- [Adaptation Guide](ADAPTATION_GUIDE_USA_PLATFORMS.md) - Technical details
- [Executive Summary](EXECUTIVE_SUMMARY.md) - One-page overview

### Tools
- Project Board: [Jira/Trello link]
- Design Mockups: [Figma link]
- API Documentation: [Swagger/Postman link]
- Team Calendar: [Google Calendar link]

### External Resources
- Twitter API: https://developer.twitter.com/
- Reddit API: https://www.reddit.com/dev/api/
- YouTube API: https://developers.google.com/youtube
- OpenAI API: https://platform.openai.com/docs
- Anthropic Claude: https://docs.anthropic.com/

---

## Week 1 Checklist

By end of Week 1, you should have:

**Everyone:**
- [ ] All access and accounts created
- [ ] Development environment working
- [ ] Attended all team meetings
- [ ] Read USA_IMPLEMENTATION_PLAN.md
- [ ] Understood project goals and timeline
- [ ] Met entire team

**Backend Developers:**
- [ ] Database schema reviewed
- [ ] API credentials obtained
- [ ] First crawler prototype started
- [ ] Contributed first PR

**ML Engineers:**
- [ ] Sentiment model tested on English
- [ ] Test dataset creation started
- [ ] Benchmarking framework set up

**Frontend Developers:**
- [ ] Current UI explored and understood
- [ ] Design mockups created
- [ ] React environment configured

**QA Engineers:**
- [ ] Test plan drafted
- [ ] CI/CD pipeline configured
- [ ] First automated tests written

**DevOps Engineers:**
- [ ] Staging environment deployed
- [ ] Monitoring dashboards created
- [ ] CI/CD pipeline operational

---

## Getting Help

**Stuck? Here's who to ask:**

- **Architecture questions**: Tech Lead
- **Platform API issues**: Backend Developers
- **ML/sentiment questions**: ML Engineer
- **UI/UX questions**: Frontend Developer
- **Testing questions**: QA Engineer
- **Infrastructure questions**: DevOps Engineer
- **Chinese translation**: Bilingual Developer
- **Timeline/process questions**: Project Manager

**Emergency contacts**:
- Tech Lead: [Slack/Phone]
- Project Manager: [Slack/Phone]

---

## Final Tips

✅ **Read the code** - Best way to understand the system
✅ **Ask questions** - No question is too basic
✅ **Test everything** - Write tests as you code
✅ **Document as you go** - Update docs when you change code
✅ **Commit often** - Small commits are easier to review
✅ **Celebrate wins** - Share your progress in #bettafish-usa

**Welcome to the team! Let's build something amazing. 🚀**
