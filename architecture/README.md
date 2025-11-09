# BettaFish USA - Architecture Diagrams

This directory contains comprehensive architecture diagrams for the BettaFish USA platform. All diagrams are in **draw.io format** (.drawio files) and can be viewed/edited using:
- [draw.io web app](https://app.diagrams.net/)
- [draw.io desktop app](https://github.com/jgraph/drawio-desktop/releases)
- VS Code with [Draw.io Integration extension](https://marketplace.visualstudio.com/items?itemName=hediet.vscode-drawio)

---

## 📊 Available Diagrams

### 1. Overall System Architecture
**File:** `01_SYSTEM_ARCHITECTURE.drawio`

**Purpose:** High-level view of the entire BettaFish USA system

**Shows:**
- User interaction layer (Web, Mobile, API clients)
- Application layer with multi-agent system (Query, Media, Insight, Report agents)
- Forum Engine coordination mechanism
- Data processing layer with crawlers
- Database and storage components
- External service integrations (Twitter API, Reddit API, etc.)

**Key Components:**
- 5 platform crawlers (Twitter, Reddit, YouTube, Instagram, LinkedIn)
- 4 AI agents with specialized roles
- PostgreSQL + Redis data layer
- ML models for sentiment analysis

**Best For:** Understanding system overview, presenting to stakeholders

---

### 2. Multi-Agent Workflow
**File:** `02_MULTI_AGENT_WORKFLOW.drawio`

**Purpose:** Detailed view of how AI agents collaborate to process a query

**Shows:**
- Step-by-step workflow from user query to report delivery
- Parallel agent execution
- Forum-based collaboration mechanism
- Multi-round debate and refinement process
- Report generation pipeline

**Workflow Stages:**
1. User submits query
2. Agents launch in parallel
3. Initial research phase (each agent gathers data)
4. Forum collaboration (agents debate findings, 2+ rounds)
5. Report generation with visualizations
6. Delivery to user (~5 minutes total)

**Key Features Highlighted:**
- Parallel processing efficiency
- Agent debate and consensus building
- Cross-platform data synthesis

**Best For:** Understanding agent collaboration, explaining the "forum" mechanism

---

### 3. Platform Crawler Architecture
**File:** `03_CRAWLER_ARCHITECTURE.drawio`

**Purpose:** Technical details of the crawler system

**Shows:**
- Crawler Factory orchestration
- Individual crawler implementations (Twitter, Reddit, YouTube)
- Rate limiting mechanisms
- Error handling and retry logic
- Data validation pipeline
- Database storage layer

**Technical Details:**
- **Twitter Crawler:** tweepy client, 450 requests/15min limit
- **Reddit Crawler:** PRAW client, 60 requests/min limit
- **YouTube Crawler:** Google API client, 10K units/day quota
- **Common Components:** BaseCrawler, retry logic, error handlers, data validators

**Performance Targets:**
- 10,000+ posts/hour throughput
- 98%+ API success rate
- <500ms database writes

**Best For:** Developer onboarding, crawler implementation planning

---

### 4. Data Flow Pipeline
**File:** `04_DATA_FLOW_PIPELINE.drawio`

**Purpose:** End-to-end data journey from APIs to user reports

**Shows:**
- **Stage 1:** Data ingestion from 5 platforms
- **Stage 2:** Processing & enrichment (validation, sentiment analysis, entity extraction)
- **Stage 3:** Storage & indexing (PostgreSQL + Redis)
- **Stage 4:** Multi-agent analysis
- **Stage 5:** Report generation & visualization

**Data Transformations:**
- Raw JSON → Validated data → Enriched with ML → Stored → Analyzed → Visualized

**Metrics Included:**
- Throughput: 10K+ posts/hour
- Latency: 2-5 sec per post
- Accuracy: 85%+ sentiment, 80%+ entity extraction
- Reliability: 98%+ API success rate

**Best For:** Understanding data lifecycle, performance optimization

---

### 5. Deployment Architecture
**File:** `05_DEPLOYMENT_ARCHITECTURE.drawio`

**Purpose:** Production infrastructure setup (AWS/GCP)

**Shows:**
- CDN & load balancing layer (CloudFlare, ALB/GCLB)
- Application tier (Kubernetes pods with auto-scaling)
  - Flask web servers (3-10 pods)
  - Celery workers (3-20 pods)
  - ML service (2-5 pods)
- Data tier (managed services)
  - PostgreSQL (RDS/Cloud SQL) with read replicas
  - Redis (ElastiCache/Memorystore) cluster
  - S3/Cloud Storage for objects
  - Secrets Manager
- Monitoring & logging (Prometheus, Grafana, ELK, Sentry, PagerDuty)
- CI/CD pipeline (GitHub Actions, ArgoCD, Blue-Green deployment)

**Infrastructure Specs:**
- Compute: ~200 CPU, 500GB RAM (peak)
- Storage: 500GB PostgreSQL + 6.4GB Redis + unlimited S3
- Network: 100 Gbps burst, multi-AZ deployment
- Cost: $1,100-2,850/month

**Availability:**
- Multi-AZ across 3 availability zones
- RTO: <1 hour, RPO: <15 minutes
- Uptime SLA: 99.9%

**Best For:** DevOps planning, infrastructure provisioning, cost estimation

---

## 🎨 Diagram Viewing Guide

### Opening Diagrams

**Option 1: draw.io Web (Recommended for quick viewing)**
1. Go to [https://app.diagrams.net/](https://app.diagrams.net/)
2. Click "Open Existing Diagram"
3. Select file from this directory
4. View and edit as needed

**Option 2: draw.io Desktop (Recommended for editing)**
1. Download from [https://github.com/jgraph/drawio-desktop/releases](https://github.com/jgraph/drawio-desktop/releases)
2. Install and open application
3. Open .drawio file
4. Edit and save

**Option 3: VS Code (Recommended for developers)**
1. Install extension: [Draw.io Integration](https://marketplace.visualstudio.com/items?itemName=hediet.vscode-drawio)
2. Open .drawio file in VS Code
3. Edit inline with preview

### Exporting Diagrams

**To PNG/JPG:**
1. Open in draw.io
2. File → Export as → PNG (or JPG)
3. Choose resolution (1x, 2x, 4x for higher quality)
4. Save

**To PDF:**
1. Open in draw.io
2. File → Export as → PDF
3. Choose page size and quality
4. Save

**To SVG (Vector):**
1. Open in draw.io
2. File → Export as → SVG
3. Save (best for scalable graphics)

---

## 🔄 Diagram Maintenance

### When to Update Diagrams

**Update required when:**
- Architecture changes (new services, removed components)
- New platforms added (e.g., TikTok crawler)
- Infrastructure modifications (new databases, caching layers)
- Workflow changes (new agent types, different collaboration patterns)
- Deployment strategy updates

### How to Update

1. **Open diagram** in draw.io (web or desktop)
2. **Make changes** using the visual editor
3. **Save file** (File → Save or Ctrl+S)
4. **Commit to git** with clear commit message describing changes
5. **Update this README** if new diagrams added or major structural changes

### Version Control

All diagrams are version-controlled in git. To see history:
```bash
# View diagram change history
git log --follow architecture/01_SYSTEM_ARCHITECTURE.drawio

# View specific version
git show <commit-hash>:architecture/01_SYSTEM_ARCHITECTURE.drawio
```

---

## 📋 Diagram Usage by Audience

### For Executives & Stakeholders
**Start with:**
1. `01_SYSTEM_ARCHITECTURE.drawio` - Big picture overview
2. `05_DEPLOYMENT_ARCHITECTURE.drawio` - Infrastructure costs and reliability

### For Product Managers
**Start with:**
1. `02_MULTI_AGENT_WORKFLOW.drawio` - How queries are processed
2. `04_DATA_FLOW_PIPELINE.drawio` - Data journey and metrics

### For Developers
**Start with:**
1. `03_CRAWLER_ARCHITECTURE.drawio` - Crawler implementation details
2. `04_DATA_FLOW_PIPELINE.drawio` - Data transformations
3. `01_SYSTEM_ARCHITECTURE.drawio` - Component interactions

### For DevOps Engineers
**Start with:**
1. `05_DEPLOYMENT_ARCHITECTURE.drawio` - Infrastructure setup
2. `01_SYSTEM_ARCHITECTURE.drawio` - Service dependencies

### For Data Scientists
**Start with:**
1. `04_DATA_FLOW_PIPELINE.drawio` - ML pipeline integration
2. `02_MULTI_AGENT_WORKFLOW.drawio` - Agent analysis process

---

## 🛠️ Customization Guide

### Editing Diagrams

**Common tasks:**

**Add a new service:**
1. Open relevant diagram
2. Use left sidebar to drag shapes
3. Connect with arrows
4. Match color scheme (see legend)
5. Update text and labels

**Change colors:**
- Select shape → Right panel → Style → Fill color
- Use consistent colors per component type (see legends in diagrams)

**Add documentation:**
- Click shape → Edit text (Enter key)
- Use markdown-style formatting where supported

**Export for presentation:**
1. File → Export as → PNG
2. Resolution: 2x or 4x
3. Transparent background: Yes (optional)
4. Save

---

## 🎯 Diagram Design Principles

All diagrams follow these principles:

1. **Clarity First:** Simple, uncluttered layouts
2. **Consistent Colors:** Same component types use same colors across diagrams
3. **Proper Labels:** All components clearly labeled
4. **Directional Flow:** Arrows show data/control flow direction
5. **Legends Included:** Each diagram has legend explaining symbols
6. **Scalable:** Works at different zoom levels
7. **Print-Friendly:** Readable when printed or exported

### Color Scheme

| Color | Component Type | Hex Code |
|-------|---------------|----------|
| Yellow (`#fff2cc`) | Web/API servers, orchestration | #fff2cc |
| Blue (`#dae8fc`) | Databases, data storage | #dae8fc |
| Green (`#d5e8d4`) | AI agents, processing | #d5e8d4 |
| Purple (`#e1d5e7`) | ML models, analytics | #e1d5e7 |
| Pink (`#f8cecc`) | Critical components, security | #f8cecc |
| Orange (`#ffe6cc`) | External services, APIs | #ffe6cc |

---

## 📖 Additional Resources

### Related Documentation
- [USA Implementation Plan](../USA_IMPLEMENTATION_PLAN.md) - Full project roadmap
- [Executive Summary](../EXECUTIVE_SUMMARY.md) - One-page overview
- [Team Quick Start Guide](../TEAM_QUICK_START_GUIDE.md) - Developer onboarding
- [Adaptation Guide](../ADAPTATION_GUIDE_USA_PLATFORMS.md) - Platform adaptation details

### External Tools
- [draw.io Documentation](https://www.diagrams.net/doc/)
- [Architecture Diagram Best Practices](https://www.lucidchart.com/blog/how-to-create-architecture-diagrams)
- [C4 Model for Architecture](https://c4model.com/) - Optional architecture framework

---

## 🤝 Contributing

When creating or updating diagrams:

1. **Follow naming convention:** `##_DESCRIPTIVE_NAME.drawio`
2. **Add to this README:** Document purpose and contents
3. **Include legend:** Every diagram should have a legend
4. **Test export:** Ensure PNG/PDF export looks good
5. **Commit with message:** Describe what changed and why

**Example commit message:**
```
Add crawler architecture diagram

- Shows Twitter, Reddit, YouTube crawler details
- Includes rate limiting and error handling
- Documents API costs per platform
```

---

## 📞 Questions?

If you have questions about the architecture:
- **System design:** Ask Tech Lead
- **Deployment:** Ask DevOps Engineer
- **Data flow:** Ask Backend Developer
- **Agent workflow:** Ask ML Engineer

For draw.io usage questions: [draw.io Help Center](https://www.diagrams.net/doc/)

---

**Last Updated:** 2025-11-09
**Diagram Version:** 1.0
**Total Diagrams:** 5
