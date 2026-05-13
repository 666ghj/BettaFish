# InsightEngine (微舆/BettaFish) — Getting Started Guide

Welcome to **InsightEngine** (微舆), a multi-agent public opinion analysis assistant. This guide walks you through every step of setting up the project, based on the most common issues reported by our community.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Dependency Management](#dependency-management)
4. [Database Setup](#database-setup)
5. [API Key Configuration](#api-key-configuration)
6. [Running the Application](#running-the-application)
7. [Windows-Specific Troubleshooting](#windows-specific-troubleshooting)
8. [Docker Deployment](#docker-deployment)
9. [Common Errors & Solutions](#common-errors--solutions)
10. [FAQ](#faq)

---

## Prerequisites

| Requirement | Minimum Version | Notes |
|---|---|---|
| Python | 3.10+ | Required for async features and type hints |
| PostgreSQL | 15+ | Primary database; **not** MySQL |
| Git | 2.30+ | For cloning the repository |
| Docker (optional) | 20.10+ | For containerized deployment |
| LLM API Access | — | OpenAI-compatible API endpoint with a valid key |

> **⚠️ Important:** InsightEngine uses **PostgreSQL**, not MySQL. Many connection errors stem from using the wrong database engine or port (see [Database Setup](#database-setup)).

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/666ghj/BettaFish.git
cd BettaFish
```

### 2. Create a Virtual Environment

```bash
python -m venv venv

# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

If you encounter `ModuleNotFoundError` for specific packages (e.g., `humps`), install them individually:

```bash
pip install humps
```

Then re-run:

```bash
pip install -r requirements.txt
```

> **Tip:** If `pip install` fails due to dependency conflicts, try:
> ```bash
> pip install --upgrade pip
> pip install -r requirements.txt --no-cache-dir
> ```

---

## Dependency Management

### Common Missing Modules

If you see errors like `ModuleNotFoundError: No module named 'humps'` or similar, ensure all dependencies are installed:

```bash
pip install -r requirements.txt
```

If `requirements.txt` is missing entries, the commonly overlooked packages include:

- `humps` — for camelCase/snake_case conversion
- `asyncpg` — async PostgreSQL driver
- `streamlit` — for the web UI
- `sqlalchemy[asyncio]` — async ORM support

Install them manually if needed:

```bash
pip install humps asyncpg streamlit "sqlalchemy[asyncio]"
```

### Configuration File Syntax Errors

If you see `IndentationError` in `base_config.py` or other config files:

1. **Do not edit config files with tabs** — use spaces (4 spaces per indent level).
2. Verify that `.env` files follow the `KEY=VALUE` format with no extra whitespace around `=`.
3. Ensure there are no trailing spaces or missing quotes in values containing special characters.

---

## Database Setup

InsightEngine requires **PostgreSQL 15+**. This is one of the most common sources of setup errors.

### 1. Install PostgreSQL

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install postgresql-15
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**macOS (Homebrew):**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Windows:**
Download the installer from [postgresql.org](https://www.postgresql.org/download/windows/) and run it. Ensure the PostgreSQL bin directory is added to your system PATH.

### 2. Create the Database

```bash
sudo -u postgres psql
```

```sql
CREATE USER bettafish WITH PASSWORD 'your_secure_password';
CREATE DATABASE bettafish OWNER bettafish;
GRANT ALL PRIVILEGES ON DATABASE bettafish TO bettafish;
\q
```

### 3. Configure Database Connection

Edit your `.env` file with the correct PostgreSQL settings:

```env
DB_DIALECT=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_USER=bettafish
DB_PASSWORD=your_secure_password
DB_NAME=bettafish
DB_CHARSET=utf8
```

> **⚠️ Common Mistake:** Do **not** use MySQL settings (port `3306`, dialect `mysql`). InsightEngine uses PostgreSQL exclusively (port `5432`, dialect `postgresql`).

### 4. Initialize the Database Schema

```bash
python init_db.py
```

> **⚠️ SSL Mode Error:** If you see `ssslmode not supported by asyncpg`, set `DB_HOST` to `localhost` (not `127.0.0.1`) or remove any `sslmode` parameter from the connection string. When connecting locally, `asyncpg` does not support SSL mode.

### 5. Verify the Database

After initialization, verify that the following tables exist:

```bash
psql -U bettafish -d bettafish -c "\dt"
```

Expected tables include `daily_news`, `daily_topics`, and others. If tables are missing, re-run the initialization script.

### 6. Docker Database (Alternative)

If running PostgreSQL in Docker:

```bash
docker run -d \
  --name bettafish-db \
  -e POSTGRES_USER=bettafish \
  -e POSTGRES_PASSWORD=your_secure_password \
  -e POSTGRES_DB=bettafish \
  -p 5432:5432 \
  postgres:15
```

> **Note:** If the `postgres:15` image fails to pull (common in certain regions), try using a mirror registry or pull with a specific digest:
> ```bash
> docker pull postgres:15@sha256:<digest_hash>
> ```

---

## API Key Configuration

API key misconfiguration is the **#1 source of issues** for new users. InsightEngine uses multiple LLM endpoints, each requiring its own API key, base URL, and model name.

### Understanding the Engine Architecture

InsightEngine uses several independent LLM "engines" for different tasks:

| Engine | Purpose | Required? |
|---|---|---|
| `INSIGHT_ENGINE` | Core analysis engine | ✅ Yes |
| `MEDIA_ENGINE` | Media/content processing | ✅ Yes |
| `QUERY_ENGINE` | Query processing | ✅ Yes |
| `REPORT_ENGINE` | Report generation | ✅ Yes |
| `MINDSPIDER` | Web crawling & scraping | ✅ Yes |
| `FORUM_HOST` | Forum data processing | ⬜ Optional |
| `KEYWORD_OPTIMIZER` | Keyword optimization | ⬜ Optional |

### Configuration Template

Create or edit your `.env` file:

```env
# ─── Core Analysis Engine ───
INSIGHT_ENGINE_API_KEY=sk-xxxxxxxxxxxxxxxx
INSIGHT_ENGINE_BASE_URL=https://api.openai.com/v1
INSIGHT_ENGINE_MODEL_NAME=gpt-4o

# ─── Media Engine ───
MEDIA_ENGINE_API_KEY=sk-xxxxxxxxxxxxxxxx
MEDIA_ENGINE_BASE_URL=https://api.openai.com/v1
MEDIA_ENGINE_MODEL_NAME=gpt-4o

# ─── Query Engine ───
QUERY_ENGINE_API_KEY=sk-xxxxxxxxxxxxxxxx
QUERY_ENGINE_BASE_URL=https://api.openai.com/v1
QUERY_ENGINE_MODEL_NAME=gpt-4o

# ─── Report Engine ───
REPORT_ENGINE_API_KEY=sk-xxxxxxxxxxxxxxxx
REPORT_ENGINE_BASE_URL=https://api.openai.com/v1
REPORT_ENGINE_MODEL_NAME=gpt-4o

# ─── MindSpider (Crawler) ───
MINDSPIDER_API_KEY=sk-xxxxxxxxxxxxxxxx
MINDSPIDER_BASE_URL=https://api.openai.com/v1
MINDSPIDER_MODEL_NAME=gpt-4o

# ─── Forum Host (Optional) ───
FORUM_HOST_API_KEY=sk-xxxxxxxxxxxxxxxx
FORUM_HOST_BASE_URL=https://api.openai.com/v1
FORUM_HOST_MODEL_NAME=gpt-4o

# ─── Keyword Optimizer (Optional) ───
KEYWORD_OPTIMIZER_API_KEY=sk-xxxxxxxxxxxxxxxx
KEYWORD_OPTIMIZER_BASE_URL=https://api.openai.com/v1
KEYWORD_OPTIMIZER_MODEL_NAME=gpt-4o

# ─── Search Tool ───
SEARCH_TOOL_TYPE=AnspireAPI
ANSPIRE_BASE_URL=https://api.anspire.ai/v1
ANSPIRE_API_KEY=sk-xxxxxxxxxxxxxxxx

# Alternative search tool (use SEARCH_TOOL_TYPE=Bocha instead):
# SEARCH_TOOL_TYPE=Bocha
# BOCHA_BASE_URL=https://api.bocha.io/v1
# BOCHA_WEB_SEARCH_API_KEY=sk-xxxxxxxxxxxxxxxx
```

### BASE_URL Configuration — Common Pitfalls

The `BASE_URL` must point to an **OpenAI-compatible API endpoint**. Here are the most common mistakes:

#### ❌ Wrong: Double `/chat/completions` Path

```env
# WRONG — the SDK appends /chat/completions automatically
INSIGHT_ENGINE_BASE_URL=https://api.openai.com/v1/chat/completions
```

#### ✅ Correct: Base URL Only

```env
# CORRECT — just the base API path
INSIGHT_ENGINE_BASE_URL=https://api.openai.com/v1
```

#### ❌ Wrong: Missing `https://` Protocol

```env
# WRONG
INSIGHT_ENGINE_BASE_URL=api.openai.com/v1
```

#### ✅ Correct: Include Protocol

```env
# CORRECT
INSIGHT_ENGINE_BASE_URL=https://api.openai.com/v1
```

#### ❌ Wrong: Trailing Slash Issues

```env
# MAY CAUSE 404s on some providers
INSIGHT_ENGINE_BASE_URL=https://api.openai.com/v1/
```

#### ✅ Correct: No Trailing Slash

```env
INSIGHT_ENGINE_BASE_URL=https://api.openai.com/v1
```

### Using Third-Party LLM Providers

InsightEngine works with any OpenAI-compatible API. Common providers:

| Provider | BASE_URL | Notes |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | Default |
| Azure OpenAI | `https://<resource>.openai.azure.com/openai/deployments/<deployment>` | Use deployment name as model |
| Alibaba Cloud (通义千问) | `https://dashscope.aliyuncs.com/compatible-mode/v1` | May trigger content filtering |
| DeepSeek | `https://api.deepseek.com/v1` | Set `temperature=1` for some models |
| Ollama (local) | `http://localhost:11434/v1` | Use local model names |
| OpenRouter | `https://openrouter.ai/api/v1` | Supports many models |

### Model Name Configuration

Ensure the `MODEL_NAME` exactly matches a model you have access to:

```env
# ✅ Correct — exact model ID from your provider
INSIGHT_ENGINE_MODEL_NAME=gpt-4o

# ❌ Wrong — model doesn't exist or you don't have access
INSIGHT_ENGINE_MODEL_NAME=gpt-4-32k
```

### Temperature Settings

Some models (especially DeepSeek) only accept `temperature=1`. If you encounter errors like:

```
Invalid temperature value. This model only supports temperature=1
```

Update your configuration to set the temperature to 1 for the affected engine.

### Content Filtering (Alibaba Cloud / 通义千问)

If you use Alibaba Cloud's DashScope API, you may encounter `400` errors with messages like "Content Exists Risk". This is the platform's content safety filter blocking requests.

**Workarounds:**
1. Switch to a different LLM provider (OpenAI, DeepSeek, etc.)
2. Modify the input text to avoid triggering the content filter
3. If running your own model, disable content filtering on the server side
4. Use `temperature=1` if the error occurs during retry loops

---

## Running the Application

### Start the Backend

```bash
python main.py
```

### Start the Streamlit Frontend

```bash
streamlit run streamlit_app.py
```

The application will be available at `http://localhost:8501` by default.

### Verify Your Setup

1. Check that the database connection works by looking for successful startup messages
2. Verify API connectivity by submitting a simple query
3. Check the logs for any `401`, `404`, or `402` errors indicating API key or URL problems

---

## Windows-Specific Troubleshooting

Windows users face several unique issues. Here are the most common ones and their solutions.

### 1. GBK Encoding Error During Database Initialization

**Error:**
```
UnicodeDecodeError: 'gbk' codec can't decode byte 0x80 in position X
```

**Cause:** Windows defaults to GBK encoding for file operations, but the project uses UTF-8 encoded files.

**Solution A — Set Environment Variable (Recommended):**

Open Command Prompt as Administrator and run:

```cmd
setx PYTHONUTF8 1
```

Then restart your terminal and re-run the application.

**Solution B — Set in Python Script:**

Add this at the top of your entry script (before any other imports):

```python
import sys
import os
os.environ["PYTHONUTF8"] = "1"
```

**Solution C — Use chcp in Command Prompt:**

```cmd
chcp 65001
python main.py
```

**Solution D — PowerShell:**

```powershell
$env:PYTHONUTF8 = "1"
python main.py
```

### 2. Path Separator Issues

Windows uses `\` as the path separator, while the project may expect `/`. If you encounter path-related errors:

```python
import os
# Use os.path.join for cross-platform paths
config_path = os.path.join("config", "base_config.py")
```

### 3. UNC Path / SSRF Vulnerability

**⚠️ Security Notice:** On Windows, be aware of potential SSRF attacks via UNC paths (CVE-2026-33682). If your application processes URLs or file paths:

- Validate all user-provided paths
- Block UNC paths (`\\server\share\...`)
- Use allowlisting for file system access

### 4. Long Path Names

Windows has a 260-character path limit by default. If you encounter path-too-long errors:

1. Enable long paths in the Windows Registry:
   ```
   HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\FileSystem\LongPathsEnabled = 1
   ```
2. Or clone the repository to a shorter path (e.g., `C:\bf` instead of `C:\Users\username\Documents\projects\BettaFish`)

---

## Docker Deployment

### Quick Start with Docker Compose

```bash
docker compose up -d
```

### Common Docker Issues

#### Image Pull Failures

If `postgres:15` or `ghcr.io/666ghj/bettafish:latest` fails to pull:

1. **Check network connectivity** — some regions may have limited access to Docker Hub or GHCR
2. **Use a mirror** — configure Docker to use a registry mirror in `/etc/docker/daemon.json`:
   ```json
   {
     "registry-mirrors": ["https://mirror.gcr.io"]
   }
   ```
3. **Pull with specific digest:**
   ```bash
   docker pull postgres:15@sha256:<digest>
   ```

#### Database Hostname in Docker

When running with Docker Compose, the database hostname should be `db` (the service name), not `localhost`:

```env
# In docker-compose environment
DB_HOST=db
DB_PORT=5432
```

#### Health Check Timeouts

If Streamlit containers fail health checks on ports 8501/8502/8503:

1. Increase the health check timeout in `docker-compose.yml`
2. Ensure the Streamlit apps have sufficient time to start up
3. Check container logs: `docker compose logs <service_name>`

---

## Common Errors & Solutions

### HTTP 401 — Invalid API Key

```
Error: 401 Unauthorized
```

**Causes & Solutions:**
- **Wrong API key:** Double-check your key in `.env`. Ensure no extra spaces or quotes.
- **Key doesn't have model access:** Verify your key has permission to use the specified model.
- **Key expired or revoked:** Generate a new key from your provider's dashboard.

### HTTP 404 — Not Found

```
Error: 404 Not Found
```

**Causes & Solutions:**
- **Wrong BASE_URL:** The most common cause. Ensure your BASE_URL doesn't include `/chat/completions` (the SDK adds this automatically).
- **Missing `https://`:** Always include the protocol prefix.
- **Nginx reverse proxy misconfiguration:** If behind a proxy, verify the upstream URL is correct.

### HTTP 402 / 403 / 429 — Quota/Rate Limit

```
Error: 402 Payment Required
Error: 403 Forbidden
Error: 429 Too Many Requests
```

**Causes & Solutions:**
- **Insufficient balance:** Top up your API account.
- **Free tier exhausted:** Upgrade to a paid plan.
- **Rate limit exceeded:** Wait and retry, or reduce concurrent requests.
- **Model not available on free tier:** Switch to an available model or upgrade.

### AttributeError: 'Settings' object has no attribute 'LOG_FILE'

**Solution:** Ensure your `.env` file includes the `LOG_FILE` setting, or update to the latest version of the codebase where this attribute has a default value:

```env
LOG_FILE=logs/app.log
```

### Reports Not Generating or Incomplete

**Possible causes:**
1. **Token limit exceeded:** The report engine's model may have hit its maximum token limit. Try using a model with a larger context window.
2. **API timeout:** Increase the timeout setting for the report engine.
3. **Content filtering:** If using Alibaba Cloud, the content filter may be blocking the report content (see [Content Filtering](#content-filtering-alibaba-cloud--通义千问)).
4. **JSON parsing failure:** Check the logs for malformed JSON responses from the LLM.

### MindSpider Not Running

1. **Empty crawler folders:** Ensure `MINDSPIDER_API_KEY` and `MINDSPIDER_BASE_URL` are correctly configured.
2. **Not auto-scheduled:** MindSpider may need to be triggered manually or scheduled via cron/Task Scheduler.
3. **Crawled data not used:** Ensure the crawled data is stored in the correct database tables and the analysis pipeline picks it up.

---

## FAQ

### Q: Can I use the same API key for all engines?

**A:** Yes, if you're using the same provider for all engines. You can set the same `API_KEY`, `BASE_URL`, and `MODEL_NAME` for every engine. However, you can also mix and match providers (e.g., use OpenAI for the core engine and DeepSeek for the crawler).

### Q: Which search tool should I use — Anspire or Bocha?

**A:** Both work. Set `SEARCH_TOOL_TYPE=AnspireAPI` for Anspire or `SEARCH_TOOL_TYPE=Bocha` for Bocha. Make sure to configure the corresponding API key and base URL for your chosen tool.

### Q: Can I use MySQL instead of PostgreSQL?

**A:** No. InsightEngine uses PostgreSQL-specific features and the `asyncpg` driver. MySQL is not supported.

### Q: How do I check if my API key is valid?

**A:** Test your key with a simple curl command:

```bash
curl -X POST https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

Replace `YOUR_API_KEY`, the URL, and model name with your actual values. A successful response confirms your key and configuration are correct.

### Q: How do I reset my database?

```bash
psql -U bettafish -d bettafish -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
python init_db.py
```

### Q: Where can I get help?

- **GitHub Issues:** [https://github.com/666ghj/BettaFish/issues](https://github.com/666ghj/BettaFish/issues)
- **Search existing issues** before opening a new one — most common problems have already been solved!

---

*This guide was created based on analysis of closed issues in the InsightEngine repository. If you encounter an issue not covered here, please open a new issue with detailed error messages and your configuration (redact sensitive information like API keys).*
