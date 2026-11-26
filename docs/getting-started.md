# Getting Started with BettaFish (InsightEngine)

Welcome to **BettaFish** — a multi-agent public opinion analysis system powered by LLMs. This guide will walk you through every step of setup and configuration, addressing the most common pain points reported by our community.

> **New to BettaFish?** Start here! If you run into issues not covered in this guide, please [open an issue](https://github.com/666ghj/BettaFish/issues).

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Installation Methods](#2-installation-methods)
   - [Option A: Docker Deployment (Recommended)](#option-a-docker-deployment-recommended)
   - [Option B: Local / Conda Deployment](#option-b-local--conda-deployment)
3. [Database Setup](#3-database-setup)
4. [API Key Configuration](#4-api-key-configuration)
5. [Search Tool Configuration](#5-search-tool-configuration)
6. [Dependency Management](#6-dependency-management)
7. [Windows-Specific Troubleshooting](#7-windows-specific-troubleshooting)
8. [Verifying Your Setup](#8-verifying-your-setup)
9. [Common Issues & FAQ](#9-common-issues--faq)
10. [Next Steps](#10-next-steps)

---

## 1. Prerequisites

Before you begin, ensure you have the following:

| Requirement | Docker Deployment | Local Deployment |
|---|---|---|
| **Docker** + **Docker Compose** | ✅ Required | ❌ Not needed |
| **Python 3.11** | ❌ Not needed | ✅ Required |
| **Conda** (recommended) | ❌ Not needed | ✅ Recommended |
| **PostgreSQL 15+** | ✅ Included via Docker | ✅ Must install separately |
| **Git** | ✅ Required | ✅ Required |
| **8 GB+ RAM** | ✅ Recommended | ✅ Recommended |
| **10 GB+ disk space** | ✅ Recommended | ✅ Recommended |

### LLM API Keys You'll Need

BettaFish uses **multiple LLM agents**, each of which can use a different model provider. You need at minimum **one API key** to get started, but for full functionality you'll need several. See [Section 4](#4-api-key-configuration) for details.

---

## 2. Installation Methods

### Option A: Docker Deployment (Recommended)

Docker is the easiest way to get BettaFish running — all system dependencies (including PDF generation libraries and Playwright browsers) are pre-installed in the image.

#### Step 1: Clone the Repository

```bash
git clone https://github.com/666ghj/BettaFish.git
cd BettaFish
```

#### Step 2: Create Your `.env` File

```bash
cp .env.example .env
```

Edit `.env` and fill in your configuration. At minimum, set:
- Database credentials (`DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`)
- At least one set of LLM API keys (see [Section 4](#4-api-key-configuration))

> ⚠️ **Important:** The `.env` file is mounted into the Docker container at `/app/.env`. Make sure your database credentials in `.env` match the PostgreSQL container's configuration (see [Section 3](#3-database-setup)).

#### Step 3: Pull and Start Containers

```bash
docker compose up -d
```

This starts two containers:
- **bettafish** — the main application (Flask + Streamlit on ports 5000, 8501, 8502, 8503)
- **bettafish-db** — PostgreSQL 15 database

#### Step 4: Access the Application

| Service | URL |
|---|---|
| Main Dashboard (Flask) | http://localhost:5000 |
| Insight Engine | http://localhost:8501 |
| Media Engine | http://localhost:8502 |
| Query Engine | http://localhost:8503 |

#### 🐛 Docker Troubleshooting

**Problem: `unable to fetch descriptor which reports content size of zero`**

This is a Docker image layer corruption issue. Fix it by:

```bash
# Clear Docker cache and re-pull
docker system prune -a
docker compose pull
docker compose up -d
```

If the issue persists, try using the mirror image (for users in China):

```yaml
# In docker-compose.yml, uncomment the mirror line:
image: ghcr.nju.edu.cn/666ghj/bettafish:latest
```

**Problem: PostgreSQL image pull fails (`failed to resolve reference`)**

- Ensure you have a stable internet connection
- Try pulling the PostgreSQL image separately: `docker pull postgres:15`
- For users in China, consider configuring a Docker registry mirror

**Problem: Can BettaFish run on Windows with Docker?**

Yes! Docker Desktop for Windows works fine. Make sure:
1. Docker Desktop is running with WSL 2 backend (recommended)
2. Your project path doesn't contain non-ASCII characters (avoid paths like `E:\智能舆情监控\...`)
3. The `version` attribute in `docker-compose.yml` is obsolete and can be safely removed if you see the warning

---

### Option B: Local / Conda Deployment

#### Step 1: Clone the Repository

```bash
git clone https://github.com/666ghj/BettaFish.git
cd BettaFish
```

#### Step 2: Create a Conda Environment

```bash
conda create -n bettafish python=3.11
conda activate bettafish
```

#### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

> ⚠️ **Large dependencies:** The `requirements.txt` includes PyTorch (~2 GB), Playwright (~200 MB), and machine learning libraries. Installation may take 10-30 minutes depending on your network speed.

**For GPU support (optional):**

```bash
# Install PyTorch with CUDA instead
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu126
pip install -r requirements.txt --no-deps torch
```

#### Step 4: Install Playwright Browser

```bash
python -m playwright install chromium
```

#### Step 5: Install PDF Generation Dependencies (WeasyPrint)

WeasyPrint requires several system-level libraries. On Docker deployments these are pre-installed. For local deployment:

**Ubuntu/Debian:**
```bash
sudo apt-get install -y libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
    libgdk-pixbuf2.0-0 libcairo2 libffi-dev
```

**macOS:**
```bash
brew install pango gdk-pixbuf cairo
```

**Windows:** See [Section 7](#7-windows-specific-troubleshooting) for Windows-specific WeasyPrint setup.

#### Step 6: Create Your `.env` File

```bash
cp .env.example .env
```

Edit `.env` with your configuration (see [Section 4](#4-api-key-configuration) for API keys and [Section 3](#3-database-setup) for database).

#### Step 7: Start the Application

```bash
python app.py
```

---

## 3. Database Setup

BettaFish requires **PostgreSQL** (recommended) or **MySQL** as its database. The database stores crawled data, sentiment analysis results, and forum content.

### Docker Deployment (PostgreSQL included)

When using `docker compose up`, a PostgreSQL 15 container (`bettafish-db`) starts automatically. The credentials are mapped from your `.env` file:

```env
# In your .env file:
DB_DIALECT=postgresql
DB_HOST=db            # Use "db" as the hostname when using Docker Compose
DB_PORT=5432
DB_USER=bettafish     # Must match POSTGRES_USER
DB_PASSWORD=bettafish # Must match POSTGRES_PASSWORD
DB_NAME=bettafish     # Must match POSTGRES_DB
```

> ⚠️ **Critical:** The `DB_HOST` must be set to `db` (the Docker service name) when using Docker Compose, NOT `localhost` or `127.0.0.1`. The Docker Compose file maps your `DB_USER`, `DB_PASSWORD`, and `DB_NAME` to the PostgreSQL container's `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` environment variables. **All three must match.**

### Local Deployment (PostgreSQL)

1. **Install PostgreSQL 15+** on your system
2. **Create a database and user:**

```sql
-- Connect to PostgreSQL as superuser
sudo -u postgres psql

-- Create user and database
CREATE USER bettafish WITH PASSWORD 'bettafish';
CREATE DATABASE bettafish OWNER bettafish;
```

3. **Configure your `.env`:**

```env
DB_DIALECT=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_USER=bettafish
DB_PASSWORD=bettafish
DB_NAME=bettafish
DB_CHARSET=utf8mb4
```

### Local Deployment (MySQL alternative)

```env
DB_DIALECT=mysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=bettafish
DB_PASSWORD=bettafish
DB_NAME=bettafish
DB_CHARSET=utf8mb4
```

> **Note:** MySQL requires the `aiomysql` driver (already in `requirements.txt`).

### 🐛 Database Troubleshooting

**Problem: `password authentication failed for user "postgres"`** (Issue #561, #642)

This means the credentials in your `.env` file don't match the actual PostgreSQL credentials. Fix:

1. Verify `DB_USER` and `DB_PASSWORD` in `.env` match the PostgreSQL user
2. For Docker: ensure `DB_USER`, `DB_PASSWORD`, and `DB_NAME` match the `POSTGRES_*` variables
3. If the database was already initialized with different credentials, you may need to reset:

```bash
# Stop containers and remove database volume
docker compose down -v
# Restart with correct .env
docker compose up -d
```

**Problem: `UnicodeDecodeError` on Windows** (Issue #641)

On Windows, database initialization may fail due to encoding issues. Fix:

1. Set `chcp 65001` before running the application
2. Set `PYTHONIOENCODING=utf-8` in your environment
3. Ensure your project path contains only ASCII characters

**Problem: Database initialization fails after changing credentials**

If you change database credentials after the first run, you need to reinitialize:

```bash
# For Docker: remove the database volume
docker compose down -v
docker compose up -d

# For local: drop and recreate the database
sudo -u postgres psql -c "DROP DATABASE bettafish;"
sudo -u postgres psql -c "CREATE DATABASE bettafish OWNER bettafish;"
```

---

## 4. API Key Configuration

BettaFish uses **7 different LLM agent slots**, each configurable with its own API key, base URL, and model name. All LLM configurations follow the **OpenAI-compatible API format**, so any provider that supports this format will work.

### Required vs. Optional API Keys

| Agent | Environment Variable Prefix | Recommended Model | Required? |
|---|---|---|---|
| **Insight Engine** | `INSIGHT_ENGINE_` | `kimi-k2-0711-preview` (Moonshot) | ✅ Yes |
| **Media Engine** | `MEDIA_ENGINE_` | `gemini-2.5-pro` (via relay) | ✅ Yes |
| **Query Engine** | `QUERY_ENGINE_` | `deepseek-chat` (DeepSeek) | ✅ Yes |
| **Report Engine** | `REPORT_ENGINE_` | `gemini-2.5-pro` (via relay) | ✅ Yes |
| **MindSpider** | `MINDSPIDER_` | `deepseek-chat` (DeepSeek) | ⚠️ Optional* |
| **Forum Host** | `FORUM_HOST_` | `qwen-plus` (Alibaba Cloud) | ⚠️ Optional* |
| **Keyword Optimizer** | `KEYWORD_OPTIMIZER_` | `qwen-plus` (Alibaba Cloud) | ⚠️ Optional* |

> *MindSpider is for web crawling. Forum Host and Keyword Optimizer are supplementary. You can start without them, but full analysis features may be limited.

### Configuration Format

For each agent, you need to set **three** environment variables:

```env
<AGENT>_API_KEY=sk-your-api-key-here
<AGENT>_BASE_URL=https://api.provider.com/v1
<AGENT>_MODEL_NAME=model-name
```

### Example: Full Configuration

```env
# Insight Engine - Moonshot Kimi
INSIGHT_ENGINE_API_KEY=sk-your-moonshot-key
INSIGHT_ENGINE_BASE_URL=https://api.moonshot.cn/v1
INSIGHT_ENGINE_MODEL_NAME=kimi-k2-0711-preview

# Media Engine - Gemini via relay provider
MEDIA_ENGINE_API_KEY=sk-your-relay-key
MEDIA_ENGINE_BASE_URL=https://inferera.com/v1
MEDIA_ENGINE_MODEL_NAME=gemini-2.5-pro

# Query Engine - DeepSeek
QUERY_ENGINE_API_KEY=sk-your-deepseek-key
QUERY_ENGINE_BASE_URL=https://api.deepseek.com
QUERY_ENGINE_MODEL_NAME=deepseek-chat

# Report Engine - Gemini via relay provider
REPORT_ENGINE_API_KEY=sk-your-relay-key
REPORT_ENGINE_BASE_URL=https://inferera.com/v1
REPORT_ENGINE_MODEL_NAME=gemini-2.5-pro

# MindSpider - DeepSeek
MINDSPIDER_API_KEY=sk-your-deepseek-key
MINDSPIDER_BASE_URL=https://api.deepseek.com
MINDSPIDER_MODEL_NAME=deepseek-chat

# Forum Host - Qwen via Alibaba Cloud
FORUM_HOST_API_KEY=sk-your-aliyun-key
FORUM_HOST_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
FORUM_HOST_MODEL_NAME=qwen-plus

# Keyword Optimizer - Qwen via Alibaba Cloud
KEYWORD_OPTIMIZER_API_KEY=sk-your-aliyun-key
KEYWORD_OPTIMIZER_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
KEYWORD_OPTIMIZER_MODEL_NAME=qwen-plus
```

### Using a Single Provider for All Agents

If you have one API key (e.g., from a relay provider), you can use the same credentials for all agents:

```env
# Using a single relay provider for all agents
INSIGHT_ENGINE_API_KEY=sk-your-key
INSIGHT_ENGINE_BASE_URL=https://your-relay.com/v1
INSIGHT_ENGINE_MODEL_NAME=gemini-2.5-pro

MEDIA_ENGINE_API_KEY=sk-your-key
MEDIA_ENGINE_BASE_URL=https://your-relay.com/v1
MEDIA_ENGINE_MODEL_NAME=gemini-2.5-pro

QUERY_ENGINE_API_KEY=sk-your-key
QUERY_ENGINE_BASE_URL=https://your-relay.com/v1
QUERY_ENGINE_MODEL_NAME=gemini-2.5-pro

REPORT_ENGINE_API_KEY=sk-your-key
REPORT_ENGINE_BASE_URL=https://your-relay.com/v1
REPORT_ENGINE_MODEL_NAME=gemini-2.5-pro

MINDSPIDER_API_KEY=sk-your-key
MINDSPIDER_BASE_URL=https://your-relay.com/v1
MINDSPIDER_MODEL_NAME=deepseek-chat

FORUM_HOST_API_KEY=sk-your-key
FORUM_HOST_BASE_URL=https://your-relay.com/v1
FORUM_HOST_MODEL_NAME=qwen-plus

KEYWORD_OPTIMIZER_API_KEY=sk-your-key
KEYWORD_OPTIMIZER_BASE_URL=https://your-relay.com/v1
KEYWORD_OPTIMIZER_MODEL_NAME=qwen-plus
```

### Using Locally Deployed Models (Issue #538)

You can use locally deployed models (e.g., Ollama, vLLM, LocalAI) as long as they expose an OpenAI-compatible API:

```env
INSIGHT_ENGINE_API_KEY=not-needed
INSIGHT_ENGINE_BASE_URL=http://localhost:11434/v1
INSIGHT_ENGINE_MODEL_NAME=your-local-model
```

> **Tip:** For best results, use models with strong instruction-following capabilities. Weaker models may produce malformed JSON, especially in the Report Engine (Issue #681).

### 🐛 API Key Troubleshooting

**Problem: `Error code: 401 - Invalid token`** (Issue #505)

Your API key is invalid or expired. Fix:
1. Verify the key is correct and has not expired
2. Check for extra whitespace or newlines in the `.env` file
3. Ensure the key matches the provider specified in `BASE_URL`

**Problem: `Error code: 404 - Model not exist`** (Issue #695)

The model name doesn't exist at the specified provider. Fix:
1. Verify `MODEL_NAME` is correct for your provider
2. Check the provider's documentation for available model names
3. Some relay providers may have different model naming conventions

**Problem: `Error code: 503 - Service unavailable`** (Issue #696)

The model provider's service is temporarily unavailable or rate-limited. Fix:
1. Wait and retry later
2. Switch to a different provider or model
3. Check your provider's status page

**Problem: `Error code: 429 - Rate limit exceeded`** (Issue #524, #535)

You've hit the provider's rate limit. Fix:
1. Reduce concurrent requests
2. Upgrade your API plan for higher rate limits
3. Use a different provider for some agents to distribute load

**Problem: `The api_key client option must be set`** (Issue #501)

An API key is missing for one of the agents. Fix:
1. Check that all required `*_API_KEY` variables are set in `.env`
2. Ensure the `.env` file is in the project root directory
3. For Docker: verify the `.env` file is mounted correctly (`- ./.env:/app/.env` in `docker-compose.yml`)

---

## 5. Search Tool Configuration

BettaFish supports web search through two services: **AnspireAPI** (default) and **BochaAPI**. A **Tavily** API key is also used by some components.

### Search Tool Options

```env
# Choose your search tool: "AnspireAPI" (default) or "BochaAPI"
SEARCH_TOOL_TYPE=AnspireAPI

# Anspire AI Search (default, recommended)
ANSPIRE_BASE_URL=https://plugin.anspire.cn/api/ntsearch/search
ANSPIRE_API_KEY=your-anspire-key

# OR Bocha AI Search (alternative)
BOCHA_BASE_URL=https://api.bocha.cn/v1/ai-search
BOCHA_WEB_SEARCH_API_KEY=your-bocha-key

# Tavily (used by MindSpider for some search features)
TAVILY_API_KEY=your-tavily-key
```

> ⚠️ **Important clarification (Issue #532):** Different engines may use different search tools:
> - **Insight Engine** uses the configured `SEARCH_TOOL_TYPE` (Anspire or Bocha)
> - **Query Engine** uses Tavily directly
> - **MindSpider** uses Tavily for extraction commands
>
> If you don't configure Tavily, Query Engine and MindSpider search features may not work. Configure **both** a search API (Anspire/Bocha) **and** Tavily for full functionality.

### How to Get Search API Keys

| Service | Sign-up URL | Notes |
|---|---|---|
| Anspire | https://open.anspire.cn/ | Cost-effective, recommended |
| Bocha | https://open.bochaai.com/ | Full-featured AI search |
| Tavily | https://www.tavily.com/ | Used by Query Engine & MindSpider |

---

## 6. Dependency Management

### Python Dependencies

All dependencies are listed in `requirements.txt`. Key dependency groups:

| Category | Key Packages | Purpose |
|---|---|---|
| Web Framework | `flask`, `flask-socketio`, `streamlit` | Application server |
| LLM Interface | `openai` | API calls to LLM providers |
| Database | `SQLAlchemy`, `asyncpg`, `pymysql` | PostgreSQL/MySQL access |
| Crawler | `playwright`, `beautifulsoup4` | Web scraping |
| ML/NLP | `torch`, `transformers`, `scikit-learn` | Sentiment analysis |
| PDF | `weasyprint` | Report PDF generation |
| Visualization | `plotly`, `matplotlib`, `wordcloud` | Charts and graphs |

### Common Installation Issues

**Problem: `torch` installation fails or takes too long**

PyTorch is a large package (~2 GB). For faster installation:

```bash
# CPU-only version (sufficient for BettaFish)
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

**Problem: `playwright install chromium` fails**

Playwright requires system dependencies for headless browser operation:

```bash
# Install system dependencies first
python -m playwright install-deps
python -m playwright install chromium
```

**Problem: `weasyprint` installation fails on Linux**

WeasyPrint requires system libraries (see [Option B, Step 5](#step-5-install-pdf-generation-dependencies-weasyprint)).

**Problem: Dependency version conflicts**

Use a clean virtual environment:

```bash
conda create -n bettafish python=3.11
conda activate bettafish
pip install -r requirements.txt
```

> **Warning:** Do **not** mix Conda and pip installations for the same packages. Use one package manager consistently.

---

## 7. Windows-Specific Troubleshooting

Windows users face several unique challenges. Here are the most common issues and their solutions.

### 7.1 Path Encoding Issues (Issue #641)

**Problem:** `UnicodeDecodeError` during database initialization or file operations.

**Solution:**
1. Avoid non-ASCII characters in your project path. Use `C:\Projects\BettaFish` instead of `C:\智能舆情监控\BettaFish`
2. Set console encoding to UTF-8:
   ```cmd
   chcp 65001
   set PYTHONIOENCODING=utf-8
   ```
3. Add to your system environment variables:
   - `PYTHONIOENCODING=utf-8`
   - `PYTHONUTF8=1`

### 7.2 Docker Desktop on Windows

**Problem:** Docker Compose fails or containers can't connect.

**Solution:**
1. Use **WSL 2 backend** for Docker Desktop (Settings → General → "Use the WSL 2 based engine")
2. If containers fail to start, try running from within WSL 2:
   ```bash
   wsl
   cd /mnt/c/Projects/BettaFish
   docker compose up -d
   ```
3. Ensure sufficient memory allocation in Docker Desktop (Settings → Resources → Memory: 8 GB+)

### 7.3 WeasyPrint on Windows

**Problem:** `weasyprint` fails to install or import on Windows.

WeasyPrint requires GTK/Pango libraries which aren't natively available on Windows. Solutions:

**Option 1: Use Docker (Recommended)**
The Docker image includes all WeasyPrint dependencies pre-installed. This is the easiest solution.

**Option 2: MSYS2 GTK Installation**
```bash
# Install MSYS2 from https://www.msys2.org/
# Then in MSYS2 terminal:
pacman -S mingw-w64-x86_64-pango mingw-w64-x86_64-gdk-pixbuf2 mingw-w64-x86_64-cairo

# Add MSYS2 mingw64 bin to your PATH
set PATH=C:\msys64\mingw64\bin;%PATH%
pip install weasyprint
```

**Option 3: Skip PDF Generation**
If you only need HTML/Markdown reports, you can skip WeasyPrint installation. The application will still generate HTML and Markdown reports; PDF export will simply be unavailable.

### 7.4 Playwright on Windows

**Problem:** `playwright install chromium` fails on Windows.

**Solution:**
```bash
# Run as Administrator if needed
python -m playwright install chromium
python -m playwright install-deps
```

If the installation still fails, try:
```bash
# Set Playwright browsers path
set PLAYWRIGHT_BROWSERS_PATH=C:\Playwright\browsers
python -m playwright install chromium
```

### 7.5 Conda Environment on Windows

**Problem:** Conda environment activation doesn't persist.

**Solution:**
Create a batch file (`start_bettafish.bat`) to simplify startup:

```batch
@echo off
chcp 65001
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
call conda activate bettafish
python app.py
pause
```

### 7.6 Windows Firewall and Network

**Problem:** Agents can't connect to LLM APIs.

**Solution:**
1. Ensure Windows Firewall allows Python/Docker through
2. If behind a corporate proxy, set:
   ```env
   HTTP_PROXY=http://proxy:port
   HTTPS_PROXY=http://proxy:port
   ```
3. For Docker: configure proxy in Docker Desktop settings

---

## 8. Verifying Your Setup

After completing setup, verify everything works:

### Step 1: Check Container/Process Status

**Docker:**
```bash
docker compose ps
# Both "bettafish" and "bettafish-db" should show "Up"
```

**Local:**
```bash
# Check that app.py started without errors
# You should see log output like:
# [INFO] MindSpider AI爬虫项目
# [INFO] 数据库初始化成功
# [INFO] Flask server started on 0.0.0.0:5000
```

### Step 2: Check Health Endpoints

```bash
# Insight Engine
curl http://localhost:8501/_stcore/health

# Media Engine
curl http://localhost:8502/_stcore/health

# Query Engine
curl http://localhost:8503/_stcore/health
```

All should return HTTP 200.

### Step 3: Check Database Connection

```bash
# Docker
docker exec -it bettafish-db psql -U bettafish -d bettafish -c "SELECT 1;"

# Local
psql -U bettafish -d bettafish -c "SELECT 1;"
```

### Step 4: Test a Simple Query

1. Open http://localhost:5000 in your browser
2. Enter a search query
3. You should see the agents begin processing

> If agents show no response, check [Section 9](#9-common-issues--faq) for troubleshooting.

---

## 9. Common Issues & FAQ

### Q: All agents are configured but none respond when I send a message (Issue #672)

**A:** This is usually an API key or network connectivity issue:
1. Check that all required `*_API_KEY` values are set in `.env`
2. Verify your `.env` file is properly mounted (Docker) or in the project root (local)
3. Test API connectivity: `curl -H "Authorization: Bearer YOUR_KEY" YOUR_BASE_URL/models`
4. Check application logs for error messages:
   ```bash
   # Docker
   docker compose logs bettafish --tail 100
   
   # Local
   # Check logs/ directory for log files
   ```

### Q: Report generation fails or is very slow (Issue #525, #728)

**A:** Report generation requires a capable LLM model:
1. **Use a strong model** for Report Engine (`gemini-2.5-pro` recommended). Weaker models may produce invalid JSON or incomplete reports (Issue #681)
2. **PDF export failure** (`NoneType object has no attribute 'get'`): This is a known issue with complex reports. Try generating HTML first, then convert to PDF
3. **Slow progress**: Report generation involves multiple LLM calls. This is normal; wait patiently

### Q: Database initialization fails repeatedly (Issue #561, #641, #642)

**A:** See [Section 3 - Database Troubleshooting](#-database-troubleshooting). The most common cause is credential mismatch between `.env` and the actual database.

### Q: I don't have Tavily API key — will search work? (Issue #532)

**A:** Partially. The Insight Engine uses Anspire/Bocha (configured via `SEARCH_TOOL_TYPE`), but the Query Engine requires Tavily. For full functionality, configure **both** a general search API and Tavily.

### Q: Can I use locally deployed models? (Issue #538)

**A:** Yes! Any model server that provides an OpenAI-compatible API will work. Set the `BASE_URL` to your local server and `MODEL_NAME` to your model name. Examples:
- **Ollama:** `BASE_URL=http://localhost:11434/v1`
- **vLLM:** `BASE_URL=http://localhost:8000/v1`
- **LocalAI:** `BASE_URL=http://localhost:8080/v1`

> **Note:** Locally deployed models may produce lower-quality results compared to cloud LLMs, especially for the Report Engine which requires strong instruction-following capabilities.

### Q: Docker image pull fails in China

**A:** Use the mirror image:
```yaml
# In docker-compose.yml, replace:
image: ghcr.io/666ghj/bettafish:latest
# With:
image: ghcr.nju.edu.cn/666ghj/bettafish:latest
```

### Q: How to view application logs?

**A:**
```bash
# Docker
docker compose logs -f bettafish

# Check log files
ls -la logs/
```

### Q: "No space left on device" error (Issue #644)

**A:** Docker images and logs can consume significant disk space:
```bash
# Clean up Docker
docker system prune -a
# Check disk usage
df -h
# Clear old logs
rm -rf logs/*.log
```

---

## 10. Next Steps

Once you have BettaFish running:

1. **Explore the Dashboard** — Visit http://localhost:5000 to access the main interface
2. **Try a Sample Query** — Search for a trending topic to see all agents in action
3. **Customize Your Configuration** — Adjust search limits, timeout values, and model settings in `.env`
4. **Read the Architecture Guide** — Understand how InsightEngine, MediaEngine, QueryEngine, and ReportEngine work together
5. **Contribute** — See [CONTRIBUTING-EN.md](../CONTRIBUTING-EN.md) for contribution guidelines

---

## Getting Help

- **GitHub Issues:** https://github.com/666ghj/BettaFish/issues
- **Documentation:** See the main [README-EN.md](../README-EN.md) for project overview

---

*This guide was created based on analysis of common issues reported by the BettaFish community. If you encounter a problem not covered here, please open a new issue so we can improve this documentation.*
