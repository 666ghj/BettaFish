# BettaFish Quick Start Guide

## 🎯 What You Have Now

Your BettaFish system is now set up for Western media monitoring with a professional multi-agent architecture!

---

## 📁 Documentation Structure

### Core Documentation (Read in This Order)

1. **[docs/MULTI_AGENT_SYSTEM_README.md](docs/MULTI_AGENT_SYSTEM_README.md)** ⭐ **START HERE**
   - Complete overview of the multi-agent system
   - Quick start guide
   - Common workflows
   - Troubleshooting

2. **[docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)**
   - Full directory structure
   - Component descriptions
   - Data flow diagrams
   - Development workflow

3. **[docs/AGENT_PERSONAS.md](docs/AGENT_PERSONAS.md)**
   - All 20+ agent personas
   - Roles and responsibilities
   - Decision authority
   - Communication styles

4. **[docs/INTER_AGENT_COMMUNICATION.md](docs/INTER_AGENT_COMMUNICATION.md)**
   - Message formats and protocols
   - Communication patterns
   - Priority system
   - Security

5. **[docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md)**
   - 12-week implementation plan
   - Phase breakdown
   - Success metrics
   - Risk management

### Platform-Specific Guides

- **[WESTERN_MEDIA_SETUP.md](WESTERN_MEDIA_SETUP.md)** - Platform setup and API configuration
- **[TWITTER_MIGRATION_GUIDE.md](TWITTER_MIGRATION_GUIDE.md)** - Twitter/X scraping solutions

---

## 🚀 Getting Started (5 Steps)

### Step 1: Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Install Playwright browsers
playwright install
```

### Step 2: Set Up Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your API keys:
# - REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET (required for Reddit)
# - YOUTUBE_API_KEY (required for YouTube)
# - APIFY_API_KEY or twikit credentials (for Twitter)
nano .env
```

### Step 3: Set Up Database

```bash
# Create database (PostgreSQL recommended)
createdb bettafish

# Run migrations
psql -U your_user -d bettafish -f MindSpider/schema/western_media_tables.sql
```

### Step 4: Set Up Message Bus (Redis)

```bash
# Option A: Docker
docker run -d -p 6379:6379 redis:alpine

# Option B: Native install
# macOS: brew install redis && brew services start redis
# Ubuntu: sudo apt install redis-server && sudo systemctl start redis
```

### Step 5: Test Your Setup

```bash
# Test platform crawlers
python test_western_crawlers.py

# Test Reddit agent
python agents/platform_agents/reddit_agent.py
```

---

## 📊 System Architecture Overview

```
Project Manager Agent (Coordinator)
    │
    ├─── Platform Agents (Collect Data)
    │    ├─ Reddit Agent
    │    ├─ Twitter Agent
    │    ├─ YouTube Agent
    │    ├─ HackerNews Agent
    │    ├─ TikTok Agent
    │    └─ News RSS Agent
    │
    ├─── Data Agents (Process Data)
    │    ├─ Pipeline Agent
    │    ├─ Storage Agent
    │    ├─ Validation Agent
    │    └─ Deduplication Agent
    │
    ├─── Analysis Agents (Generate Insights)
    │    ├─ Sentiment Agent
    │    ├─ Topic Agent
    │    └─ Bias Agent
    │
    ├─── Protection Agents (Ensure Safety)
    │    ├─ Rate Limiter Agent
    │    ├─ Health Monitor Agent
    │    └─ Error Recovery Agent
    │
    └─── QA Agents (Quality Assurance)
         ├─ Test Agent
         └─ Monitoring Agent
```

---

## 🎯 What's Implemented vs. Planned

### ✅ Already Implemented

**Platform Crawlers:**
- [x] Reddit crawler with API
- [x] Twitter crawler (v2 with twikit/Apify)
- [x] YouTube crawler with API
- [x] HackerNews crawler
- [x] Western news RSS collector

**Infrastructure:**
- [x] Database schema for all platforms
- [x] Rate limiting framework
- [x] IP protection system
- [x] Configuration management
- [x] Comprehensive documentation

**Agent Framework:**
- [x] Base agent class template
- [x] Reddit agent (example implementation)
- [x] Agent lifecycle management
- [x] Message format standards

### 🔨 To Be Implemented (See PROJECT_PLAN.md)

**Phase 2 (Weeks 4-6):**
- [ ] Remaining platform agents (Twitter, YouTube, HackerNews, News RSS)
- [ ] Data processing agents (Pipeline, Storage, Validation, Deduplication)
- [ ] Analysis agents (Sentiment, Topic, Bias)
- [ ] Protection agents (Rate Limiter, Health Monitor, Error Recovery)

**Phase 3 (Weeks 7-9):**
- [ ] Message bus implementation (Redis)
- [ ] Project Manager Agent (coordinator)
- [ ] Agent-to-agent communication
- [ ] Integration testing

**Phase 4 (Weeks 10-12):**
- [ ] Production deployment
- [ ] Monitoring dashboards
- [ ] Performance optimization

---

## 🔧 Current Capabilities

### You Can Already Do:

1. **Collect Western News** (RSS-based, no rate limiting issues)
   ```python
   from MindSpider.BroadTopicExtraction.western_news_collector import WesternNewsCollector

   async with WesternNewsCollector() as collector:
       result = await collector.collect_by_political_spectrum()
   ```

2. **Monitor Reddit** (with API credentials)
   ```python
   from MindSpider.DeepSentimentCrawling.western_platforms import RedditCrawler

   crawler = RedditCrawler()
   result = crawler.crawl_politics(political_lean='all', posts_per_sub=10)
   ```

3. **Monitor HackerNews** (no API needed)
   ```python
   from MindSpider.DeepSentimentCrawling.western_platforms import HackerNewsCrawler

   async with HackerNewsCrawler() as crawler:
       result = await crawler.crawl_stories('top', limit=30)
   ```

4. **Monitor YouTube** (with API key)
   ```python
   from MindSpider.DeepSentimentCrawling.western_platforms import YouTubeCrawler

   crawler = YouTubeCrawler()
   result = crawler.search_videos('AI news', max_results=10)
   ```

5. **Use Agent Framework** (test with Reddit agent)
   ```python
   from agents.platform_agents.reddit_agent import RedditAgent

   agent = RedditAgent(config)
   await agent.initialize()
   result = await agent.execute_task(task)
   ```

---

## 📅 Implementation Roadmap

### Current Status: **Phase 1 Complete** ✅

**Phase 1: Foundation (Weeks 1-3)** ✅
- Database schema ✅
- Platform crawlers ✅
- IP protection ✅
- Documentation ✅

**Next: Phase 2 (Weeks 4-6)** 🔨
- Implement remaining agents
- Build agent coordination
- Set up message bus

**Then: Phase 3 (Weeks 7-9)** ⏳
- Integration testing
- Performance optimization
- Dashboard development

**Finally: Phase 4 (Weeks 10-12)** ⏳
- Production deployment
- Monitoring setup
- System optimization

---

## 🎓 Key Concepts

### Agent Types

**Platform Agents** - Each specializes in one platform
- Know platform's API/scraping methods
- Handle rate limiting
- Collect and format data

**Data Agents** - Process collected data
- Validate quality
- Remove duplicates
- Store in database
- Transform formats

**Analysis Agents** - Generate insights
- Sentiment analysis
- Topic extraction
- Bias detection
- Trend identification

**Protection Agents** - Ensure system safety
- Rate limiting (prevent IP bans)
- Health monitoring
- Error recovery
- Circuit breaking

### Communication Patterns

**Request-Response** - Synchronous operations
```python
response = await agent.request('rate_limiter', 'check', {...})
```

**Pub-Sub** - Event broadcasting
```python
await agent.publish('data.collected', {...})
```

**Task Queue** - Distributed work
```python
task = queue.dequeue()
result = await agent.execute(task)
```

---

## 🛠️ Common Tasks

### Add a New Platform

1. Create crawler in `MindSpider/DeepSentimentCrawling/western_platforms/`
2. Create agent in `agents/platform_agents/`
3. Add database schema
4. Write tests
5. Update documentation

### Modify Rate Limits

Edit `config/rate_limits.yaml`:
```yaml
reddit:
  requests_per_hour: 60
  min_delay: 2.0

twitter:
  requests_per_hour: 20  # Very conservative
  min_delay: 15.0
```

### Run Monitoring Task

```python
from agents.platform_agents.reddit_agent import RedditAgent

agent = RedditAgent(config)
await agent.initialize()

task = {
    'task_type': 'monitor_all',
    'task_id': 'daily-001'
}

result = await agent.execute_task(task)
```

---

## 📖 Learning Path

### For Understanding the System

1. Read **MULTI_AGENT_SYSTEM_README.md** (30 min)
2. Review **PROJECT_STRUCTURE.md** (20 min)
3. Skim **AGENT_PERSONAS.md** (15 min)
4. Try running **test_western_crawlers.py** (5 min)

### For Development

1. Study **base_agent.py** template (20 min)
2. Review **reddit_agent.py** example (15 min)
3. Read **INTER_AGENT_COMMUNICATION.md** (30 min)
4. Follow **PROJECT_PLAN.md** phases (ongoing)

### For API Setup

1. Read **WESTERN_MEDIA_SETUP.md** (20 min)
2. Read **TWITTER_MIGRATION_GUIDE.md** (15 min)
3. Get API credentials (30 min)
4. Test crawlers (10 min)

---

## 🎯 Recommended Next Steps

### Immediate (This Week)

1. **Set up Reddit API** (15 minutes)
   - Visit https://www.reddit.com/prefs/apps
   - Create app, get credentials
   - Add to `.env`
   - Test: `python agents/platform_agents/reddit_agent.py`

2. **Set up YouTube API** (15 minutes)
   - Visit https://console.cloud.google.com/
   - Enable YouTube Data API v3
   - Create API key
   - Add to `.env`

3. **Choose Twitter solution** (30 minutes)
   - Option A: Brand24 ($49/mo) - Best for you
   - Option B: Apify (~$10/mo) - Good value
   - Option C: twikit (free) - Requires maintenance

### Short-term (Next 2 Weeks)

1. **Implement remaining platform agents**
   - Twitter Agent
   - YouTube Agent
   - HackerNews Agent
   - News RSS Agent

2. **Set up Redis message bus**
   - Install Redis
   - Implement message bus class
   - Test agent communication

3. **Implement data pipeline agents**
   - Pipeline Agent
   - Storage Agent
   - Validation Agent

### Medium-term (Next Month)

1. **Complete agent system**
   - Analysis agents
   - Protection agents
   - QA agents

2. **Build coordinator**
   - Project Manager Agent
   - Task Dispatcher
   - Status Tracker

3. **Integration testing**
   - End-to-end workflows
   - Performance testing
   - Error scenarios

---

## 💡 Tips for Success

### IP Protection (Critical!)

- **Always use rate limiting** - Your home IP can be banned
- **Start conservative** - Use default rate limits first
- **Monitor for errors** - Watch for 429/403 errors
- **Twitter is highest risk** - Use Brand24 or very conservative limits
- **Consider Brand24** - $49/mo for zero IP ban risk

### Development

- **Follow the templates** - Use `base_agent.py` as blueprint
- **Test incrementally** - Test each agent independently
- **Log everything** - Helps with debugging
- **Use correlation IDs** - Track message flows
- **Monitor health** - Regular health checks

### Performance

- **Batch operations** - Don't make one API call per item
- **Cache where possible** - Reduce redundant API calls
- **Use async/await** - Maximize concurrency
- **Monitor quotas** - Don't exhaust API limits
- **Optimize queries** - Database performance matters

---

## 🆘 Getting Help

### Documentation

- Start with **MULTI_AGENT_SYSTEM_README.md**
- Check **troubleshooting** sections in each guide
- Review **example code** in agents/

### Community Resources

- **Anthropic Docs**: https://docs.anthropic.com/claude/docs
- **Sub-agents Guide**: https://code.claude.com/docs/en/sub-agents
- **Agent Skills**: https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices

### Debugging

1. Check logs in `logs/` directory
2. Run with `--verbose` flag
3. Test individual components
4. Review error messages carefully
5. Check API credentials

---

## 📊 Success Metrics

Track these KPIs (from PROJECT_PLAN.md):

**Data Collection:**
- Daily items collected: 10,000+ target
- Collection success rate: >95%
- Duplicate rate: <1%

**System Performance:**
- Uptime: >99%
- Response time: <10 seconds
- Error rate: <5%

**IP Protection:**
- IP bans: 0 target
- Rate limit violations: <10/month

---

## 🎉 You're Ready!

You now have:

✅ Complete multi-agent architecture
✅ Working platform crawlers
✅ Comprehensive documentation
✅ Agent framework and examples
✅ 12-week implementation plan
✅ Best practices and patterns

**Start with:** docs/MULTI_AGENT_SYSTEM_README.md

**Good luck building your Western media monitoring system!** 🚀

---

**Questions?** Review the documentation or check the code examples!
