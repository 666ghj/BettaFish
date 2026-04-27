# Getting Started with InsightEngine (BettaFish)

> **Multi-Agent Public Opinion Analysis Assistant** — This guide will help you set up, configure, and run InsightEngine from scratch, addressing the most common issues reported by the community.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Dependency Management](#dependency-management)
4. [Database Setup](#database-setup)
5. [API Key Configuration](#api-key-configuration)
6. [Search Tool Configuration](#search-tool-configuration)
7. [Running the Application](#running-the-application)
8. [Docker Deployment](#docker-deployment)
9. [Windows-Specific Troubleshooting](#windows-specific-troubleshooting)
10. [Common Error Reference](#common-error-reference)
11. [Getting Help](#getting-help)

---

## Prerequisites

| Requirement | Minimum Version | Recommended |
|---|---|---|
| Python | 3.9 | 3.10–3.12 |
| PostgreSQL | 13+ | 15+ |
| MySQL | 8.0+ (optional) | 8.0+ |
| Redis | 6.0+ (optional) | 7.0+ |
| Git | 2.30+ | Latest |
| OS | Linux / macOS / Windows 10+ | Linux (Ubuntu 22.04+) |

> **Windows users:** Please read the [Windows-Specific Troubleshooting](#windows-specific-troubleshooting) section before proceeding.

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/666ghj/BettaFish.git
cd BettaFish
```

### 2. Create a Virtual Environment

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate
```

**Windows (Conda — recommended for Windows users):**
```cmd
conda create -n bettafish python=3.10
conda activate bettafish
```

> ⚠️ **Important:** Always activate your virtual environment before installing dependencies or running the application. If you skip this step, packages will be installed globally and may conflict with your system Python.

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

If you encounter build failures for `weasyprint`, `torch`, or `playwright`, see [Dependency Management](#dependency-management) below.

### 4. Install Playwright Browsers

The MindSpider crawler requires Playwright browser binaries:

```bash
playwright install chromium
```

> On Linux servers without a GUI, use:
> ```bash
> playwright install chromium --with-deps
> ```

---

## Dependency Management

### Common Installation Failures

#### `ModuleNotFoundError: No module named 'humps'`

This means the `humps` package was not installed. Install it manually:

```bash
pip install pyhumps
```

> The package name on PyPI is `pyhumps`, but it's imported as `humps`. If `pip install humps` fails, use `pip install pyhumps` instead.

#### WeasyPrint Installation Failures

WeasyPrint requires system-level libraries. Install them first:

**Ubuntu/Debian:**
```bash
sudo apt-get install build-essential python3-dev python3-pip python3-setuptools python3-wheel python3-cffi libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info
```

**macOS:**
```bash
brew install cairo pango gdk-pixbuf libffi
```

**Windows:** WeasyPrint on Windows is challenging. Use Docker instead, or install GTK3 runtime from [gtk-win64](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer).

#### PyTorch Installation

If the default `pip install torch` is too slow or fails, install a CPU-only version:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

Or install with CUDA support (adjust for your GPU):
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

#### IndentationError in Config Files

If you see an `IndentationError` after editing `.env` or Python config files, ensure:
- No mixed tabs and spaces (use spaces only)
- No trailing whitespace on continuation lines
- The `.env` file uses simple `KEY=VALUE` format (no indentation needed)

---

## Database Setup

InsightEngine supports **PostgreSQL** (recommended) and **MySQL**. The default dialect is PostgreSQL.

### Option A: PostgreSQL (Recommended)

#### 1. Install and Start PostgreSQL

**Ubuntu/Debian:**
```bash
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**macOS (Homebrew):**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Windows:** Download the installer from [postgresql.org](https://www.postgresql.org/download/windows/).

#### 2. Create Database and User

```bash
sudo -u postgres psql
```

```sql
CREATE USER bettafish WITH PASSWORD 'bettafish';
CREATE DATABASE bettafish OWNER bettafish;
GRANT ALL PRIVILEGES ON DATABASE bettafish TO bettafish;
\q
```

#### 3. Configure `.env`

```env
DB_DIALECT=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_USER=bettafish
DB_PASSWORD=bettafish
DB_NAME=bettafish
DB_CHARSET=utf8mb4
```

> ⚠️ **Do NOT put SSL parameters in the `DB_NAME` field.** The application uses `asyncpg` for PostgreSQL, which does **not** support `sslmode` as a query parameter in the database URL. If you need SSL, configure it at the PostgreSQL server level or use a connection pooler like PgBouncer.

#### 4. Initialize Tables

Start the application once — it will auto-create the required tables (`daily_news`, `daily_topics`, etc.) on first run:

```bash
python app.py
```

If tables are not created automatically, check:
- The database user has `CREATE TABLE` permissions
- The `DB_HOST` and `DB_PORT` are correct (the app defaults to port 3306 if not set; for PostgreSQL, explicitly set `DB_PORT=5432`)
- The database name exists and the user can access it

### Option B: MySQL

```env
DB_DIALECT=mysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=bettafish
DB_CHARSET=utf8mb4
```

### Option C: Using Docker for the Database (Easiest)

If you don't want to install PostgreSQL locally, use the Docker Compose setup (see [Docker Deployment](#docker-deployment)), which includes a pre-configured PostgreSQL service.

The default Docker Compose database settings are:
- Host: `db` (service name in Docker network) or `localhost` (from host)
- Port: `5444` (mapped from container's 5432)
- User: `bettafish`
- Password: `bettafish`
- Database: `bettafish`

### Database Troubleshooting

| Problem | Cause | Solution |
|---|---|---|
| `Connection refused` | DB not running or wrong host/port | Verify DB is running: `pg_isready -h localhost -p 5432` |
| `Password authentication failed` | Wrong credentials | Check `DB_USER` and `DB_PASSWORD` in `.env` |
| `FATAL: database "bettafish" does not exist` | Database not created | Create it: `createdb -U postgres bettafish` |
| `no pg_hba.conf entry` | PostgreSQL not allowing connections | Add `host all all 0.0.0.0/0 md5` to `pg_hba.conf` |
| `SSL not supported` | `sslmode` parameter used with asyncpg | Remove SSL params from DB connection; configure at server level |
| Docker container can't reach DB | Wrong hostname | Use service name `db` instead of `localhost` in Docker |

---

## API Key Configuration

This is the **most common source of errors**. InsightEngine uses multiple LLM agents, each requiring its own API key, base URL, and model name.

### Understanding the Agent Architecture

InsightEngine has **7 LLM-powered agents**, each configured independently:

| Agent | Purpose | Recommended Model | Recommended Provider |
|---|---|---|---|
| Insight Engine | Core insight analysis | `kimi-k2` | Moonshot (api.moonshot.cn) |
| Media Engine | Media content analysis | `gemini-2.5-pro` | AIHubMix (aihubmix.com) |
| Query Engine | Query processing | `deepseek-chat` | DeepSeek (platform.deepseek.com) |
| Report Engine | Report generation | `gemini-2.5-pro` | AIHubMix (aihubmix.com) |
| MindSpider | Web crawling & extraction | `deepseek-chat` | DeepSeek (platform.deepseek.com) |
| Forum Host | Multi-agent discussion | `qwen-plus` | Alibaba Bailian |
| Keyword Optimizer | Search keyword refinement | `qwen-plus` | Alibaba Bailian |

### Configuring `.env` for API Keys

Copy the example file and edit it:

```bash
cp .env.example .env
```

Each agent needs three variables:

```env
# Insight Engine
INSIGHT_ENGINE_API_KEY=sk-your-insight-key-here
INSIGHT_ENGINE_BASE_URL=https://api.moonshot.cn/v1
INSIGHT_ENGINE_MODEL_NAME=kimi-k2

# Media Engine
MEDIA_ENGINE_API_KEY=sk-your-media-key-here
MEDIA_ENGINE_BASE_URL=https://aihubmix.com/v1
MEDIA_ENGINE_MODEL_NAME=gemini-2.5-pro

# Query Engine
QUERY_ENGINE_API_KEY=sk-your-query-key-here
QUERY_ENGINE_BASE_URL=https://api.deepseek.com
QUERY_ENGINE_MODEL_NAME=deepseek-chat

# Report Engine
REPORT_ENGINE_API_KEY=sk-your-report-key-here
REPORT_ENGINE_BASE_URL=https://aihubmix.com/v1
REPORT_ENGINE_MODEL_NAME=gemini-2.5-pro

# MindSpider
MINDSPIDER_API_KEY=sk-your-mindspider-key-here
MINDSPIDER_BASE_URL=https://api.deepseek.com
MINDSPIDER_MODEL_NAME=deepseek-chat

# Forum Host
FORUM_HOST_API_KEY=sk-your-forum-key-here
FORUM_HOST_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
FORUM_HOST_MODEL_NAME=qwen-plus

# Keyword Optimizer
KEYWORD_OPTIMIZER_API_KEY=sk-your-keyword-key-here
KEYWORD_OPTIMIZER_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
KEYWORD_OPTIMIZER_MODEL_NAME=qwen-plus
```

> 💡 **Tip:** You can use the same API key and base URL for multiple agents if your provider supports the models you need. For example, you can use a single OpenAI-compatible endpoint for all agents.

### Critical BASE_URL Rules

The `BASE_URL` is the **most frequently misconfigured** setting. Follow these rules:

1. **Always include the protocol** (`http://` or `https://`):
   - ✅ `https://api.moonshot.cn/v1`
   - ❌ `api.moonshot.cn/v1` (missing protocol)

2. **Do NOT include `/chat/completions` at the end** — the application appends this automatically:
   - ✅ `https://api.moonshot.cn/v1`
   - ❌ `https://api.moonshot.cn/v1/chat/completions` (doubled path → 404 error)

3. **Do NOT include a trailing slash**:
   - ✅ `https://api.deepseek.com`
   - ❌ `https://api.deepseek.com/`

4. **Use the correct endpoint for your provider**:
   - Alibaba Bailian (Qwen models): `https://dashscope.aliyuncs.com/compatible-mode/v1`
   - Moonshot: `https://api.moonshot.cn/v1`
   - DeepSeek: `https://api.deepseek.com`
   - AIHubMix: `https://aihubmix.com/v1`

### API Error Reference

| HTTP Status | Meaning | Common Cause | Solution |
|---|---|---|---|
| 401 | Unauthorized | Invalid or missing API key | Check `API_KEY` spelling and value in `.env` |
| 402 / 403 | Payment required / Forbidden | Insufficient balance or quota | Top up your API account; check usage limits |
| 404 | Not Found | Wrong `BASE_URL` (doubled path) or model unavailable | Remove `/chat/completions` from `BASE_URL`; verify model name |
| 429 | Too Many Requests | Rate limiting | Wait and retry; reduce concurrent requests; upgrade API plan |
| 400 | Bad Request | Invalid model, temperature, or content filter | See content filter section below |

### Content Filter Issues ("Content Exists Risk" / "Inappropriate Content")

When using Alibaba Cloud (Qwen/Bailian) models, you may encounter content filter errors:

- `"Content Exists Risk"` — The provider's safety filter flagged the input or output
- `"Input/Output data may contain inappropriate content"` — Same issue, different wording

**Workaround:** Add the following header to bypass the Alibaba Cloud green network filter:

```
X-DashScope-DataInspection: disable
```

In the `.env` file or code configuration, you may need to set this as a custom header. See [Issue #549](https://github.com/666ghj/BettaFish/issues/549) for details.

**Alternative:** Switch to a model from a different provider (e.g., DeepSeek or Moonshot) for agents that frequently trigger content filters.

### Temperature Parameter

Some models (especially certain Qwen models) only support `temperature=1`. If you encounter temperature-related errors, set the temperature to 1 in the code or configuration for that specific agent.

### Security Warning ⚠️

**The `/api/config` endpoint may expose your API keys** if the application is accessible publicly. To mitigate this:

1. Do not expose the application directly to the internet without authentication
2. Use a reverse proxy (e.g., Nginx) with basic auth or OAuth
3. Restrict network access to trusted IPs only

---

## Search Tool Configuration

InsightEngine uses a web search tool to gather information. There are **three options**:

### Option 1: AnspireAPI (Default)

```env
SEARCH_TOOL_TYPE=AnspireAPI
ANSPIRE_BASE_URL=https://open.anspire.cn
ANSPIRE_API_KEY=your-anspire-api-key
```

Register at [open.anspire.cn](https://open.anspire.cn/) to get an API key.

### Option 2: BochaAPI

```env
SEARCH_TOOL_TYPE=BochaAPI
BOCHA_BASE_URL=https://api.bocha.cn/v1/ai-search
BOCHA_WEB_SEARCH_API_KEY=your-bocha-api-key
```

Register at [open.bochaai.com](https://open.bochaai.com/) to get an API key.

### Option 3: Tavily

```env
TAVILY_API_KEY=your-tavily-api-key
```

Register at [tavily.com](https://tavily.com/) to get an API key.

> ⚠️ **Note:** The code primarily uses Tavily for search, but the `.env.example` configures Anspire/Bocha. If you set `SEARCH_TOOL_TYPE` but don't configure the corresponding API key, search will fail. Make sure your search tool configuration is consistent.

---

## Running the Application

### Full Application (All Agents)

```bash
python app.py
```

The web interface will be available at `http://localhost:5000`.

### Report Engine Only

If you only need to generate reports and don't need the full multi-agent pipeline:

```bash
python report_engine_only.py
```

> ⚠️ **Note:** If you see `AttributeError: 'Settings' object has no attribute 'LOG_FILE'`, make sure your `.env` file includes all required variables from `.env.example`, especially the `LOG_FILE` setting if present. Copy the full `.env.example` to `.env` and customize from there.

### MindSpider (Web Crawler)

MindSpider must be **run manually** — it is not automatically scheduled:

```bash
# From the project root
cd MindSpider
python -m MindSpider.main
```

> **Note:** Some platform crawler modules may have empty directories (code not yet committed). See [Issue #589](https://github.com/666ghj/BettaFish/issues/589) for updates.

---

## Docker Deployment

### Quick Start with Docker Compose

```bash
# Copy and edit the configuration
cp .env.example .env
# Edit .env with your API keys and database settings

# Start all services
docker compose up -d
```

This starts:
- The InsightEngine application (port 5000)
- Streamlit report viewers (ports 8501, 8502, 8503)
- PostgreSQL database (port 5444)

### Docker Images

The official images are available at:
- **Primary:** `ghcr.io/666ghj/bettafish:latest`
- **China Mirror:** `ghcr.nju.edu.cn/666ghj/bettafish:latest`

> If `docker compose pull` fails, try the China mirror by editing `docker-compose.yml`.

### Windows Docker Note

If you see `no matching manifest for windows/amd64` when pulling the image, the pre-built image may not support Windows containers. **Switch to Linux containers** in Docker Desktop settings (right-click the Docker icon in the system tray → "Switch to Linux containers").

---

## Windows-Specific Troubleshooting

Windows users encounter several unique issues. This section addresses the most common ones.

### 1. GBK Encoding Errors

**Problem:**
```
UnicodeDecodeError: 'gbk' codec can't decode byte 0xXX in position XX
```

This occurs during database initialization or file operations because Windows defaults to the GBK encoding instead of UTF-8.

**Solutions:**

**Option A: Set environment variable (Recommended)**
```cmd
set PYTHONUTF8=1
python app.py
```

Or set it permanently:
1. Search "Environment Variables" in Windows Start menu
2. Add a new user variable: `PYTHONUTF8` = `1`
3. Restart your terminal

**Option B: Use Conda with UTF-8 locale**
```cmd
conda activate bettafish
set PYTHONIOENCODING=utf-8
python app.py
```

**Option C: Modify the Python command**
```cmd
python -X utf8 app.py
```

### 2. Path Issues with Backslashes

Windows uses backslashes (`\`) in paths, which can cause issues in some Python libraries. If you encounter path-related errors:

- Use raw strings or forward slashes in any custom paths
- Ensure your project is in a path **without spaces or special characters** (avoid `C:\Program Files\` or `C:\Users\User Name\`)
- Recommended project location: `C:\Projects\BettaFish` or `D:\BettaFish`

### 3. Docker on Windows

- Ensure Docker Desktop is running in **Linux container mode** (not Windows containers)
- If `docker compose up` fails with manifest errors, see [Docker Deployment](#docker-deployment)
- Allocate at least **4 GB RAM** to Docker Desktop (Settings → Resources → Memory)

### 4. WeasyPrint on Windows

WeasyPrint requires GTK3 libraries which are not available by default on Windows. Options:

1. **Install GTK3 Runtime:** Download from [GTK for Windows](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer)
2. **Use Docker:** The Docker image includes all system dependencies
3. **Skip PDF generation:** If you only need HTML/Markdown reports, you can skip WeasyPrint

### 5. Playwright on Windows

If `playwright install chromium` fails:
```cmd
# Run as Administrator
playwright install --with-deps chromium
```

### 6. Conda Environment Setup (Recommended for Windows)

```cmd
# Create environment
conda create -n bettafish python=3.10 -y
conda activate bettafish

# Set UTF-8 encoding
set PYTHONUTF8=1

# Install dependencies
pip install -r requirements.txt

# Install Playwright
playwright install chromium

# Copy and edit configuration
copy .env.example .env
# Edit .env with your settings

# Run the application
python app.py
```

---

## Common Error Reference

### Quick Diagnosis Table

| Error Message | Section to Read |
|---|---|
| `401 Unauthorized` | [API Key Configuration](#api-key-configuration) |
| `404 Not Found` (doubled path) | [Critical BASE_URL Rules](#critical-base_url-rules) |
| `429 Too Many Requests` | [API Error Reference](#api-error-reference) |
| `402 / 403 Insufficient balance` | [API Error Reference](#api-error-reference) |
| `Content Exists Risk` | [Content Filter Issues](#content-filter-issues-content-exists-risk--inappropriate-content) |
| `Connection refused` (database) | [Database Setup](#database-setup) |
| `Password authentication failed` | [Database Setup](#database-setup) |
| `no pg_hba.conf entry` | [Database Troubleshooting](#database-troubleshooting) |
| `sslmode not supported` | [Database Setup — PostgreSQL](#option-a-postgresql-recommended) |
| `UnicodeDecodeError: 'gbk'` | [Windows-Specific Troubleshooting](#windows-specific-troubleshooting) |
| `no matching manifest for windows/amd64` | [Docker Deployment](#docker-deployment) |
| `ModuleNotFoundError: No module named 'humps'` | [Dependency Management](#dependency-management) |
| `AttributeError: 'Settings' object has no attribute 'LOG_FILE'` | [Running the Application](#running-the-application) |
| `IndentationError` in config | [Dependency Management](#dependency-management) |
| JSON parsing failures in reports | [Running the Application](#running-the-application) |
| `no matching manifest` (Docker) | [Docker Deployment](#docker-deployment) |

### Report Generation Issues

If reports fail to generate or contain JSON parsing errors:
1. Ensure the Report Engine model returns well-formed JSON (some models are better at this than others)
2. Try using `gemini-2.5-pro` or `deepseek-chat` which tend to produce more structured output
3. Check the logs in the `logs/` directory for detailed error messages

---

## Getting Help

- **Issues:** [GitHub Issues](https://github.com/666ghj/BettaFish/issues) — Search existing issues before creating a new one
- **Discussions:** [GitHub Discussions](https://github.com/666ghj/BettaFish/discussions) — For questions and general discussion
- **Contributing:** See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines

---

*This guide was created by analyzing over 100 closed issues to identify the most common setup and configuration pain points. If you encounter an issue not covered here, please [open a new issue](https://github.com/666ghj/BettaFish/issues/new) so we can improve this guide.*
