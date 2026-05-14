# Getting Started with InsightEngine (BettaFish)

Welcome to InsightEngine! This guide will help you get up and running quickly by walking you through installation, dependency management, database setup, API key configuration, and platform-specific troubleshooting. This guide was compiled based on the most common pain points reported by users in our issue tracker.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Dependency Management](#dependency-management)
4. [Database Setup](#database-setup)
5. [API Key Configuration](#api-key-configuration)
6. [Running the Application](#running-the-application)
7. [Docker Deployment](#docker-deployment)
8. [Windows-Specific Troubleshooting](#windows-specific-troubleshooting)
9. [Common Errors and Solutions](#common-errors-and-solutions)
10. [Getting Help](#getting-help)

---

## Prerequisites

Before you begin, make sure you have the following installed:

- **Python 3.10+** (Python 3.11 recommended)
- **Git**
- **PostgreSQL 15+** (or Docker for containerized database)
- A compatible LLM API provider account (OpenAI, Azure OpenAI, or any OpenAI-compatible endpoint)

> **Note for Windows users:** See the [Windows-Specific Troubleshooting](#windows-specific-troubleshooting) section for important setup considerations.

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/666ghj/BettaFish.git
cd BettaFish
```

### 2. Create a Virtual Environment

```bash
# Linux/macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

If you encounter issues with the `humps` module not being found, install it explicitly:

```bash
pip install pyhumps
```

> **Known Issue:** The `humps` module is listed as a dependency but may not install correctly on all systems. See [Dependency Management](#dependency-management) for details.

---

## Dependency Management

### Common Dependency Issues

#### Missing `humps` Module

**Symptom:** `ModuleNotFoundError: No module named 'humps'`

**Solution:**

```bash
pip install pyhumps
```

The package is published as `pyhumps` on PyPI but imported as `humps` in Python code.

#### IndentationError in `base_config.py`

**Symptom:** `IndentationError` when importing configuration modules.

**Solution:** Make sure you have the latest version of the code. If you cloned earlier, pull the latest changes:

```bash
git pull origin main
```

#### Settings Object Missing `LOG_FILE` Attribute

**Symptom:** `AttributeError: 'Settings' object has no attribute 'LOG_FILE'`

**Solution:** Ensure your `.env` file includes the `LOG_FILE` setting, or update to the latest codebase where this attribute has a default value. You can add the following to your `.env` file:

```env
LOG_FILE=logs/insightengine.log
```

### Verifying Your Installation

After installing dependencies, verify everything is working:

```bash
python -c "import humps; print('humps OK')"
python -c "import pydantic; print('pydantic OK')"
python -c "import asyncpg; print('asyncpg OK')"
```

---

## Database Setup

### Configuring PostgreSQL

InsightEngine uses **PostgreSQL** as its primary database. **Do not use MySQL or other databases** — the project uses `asyncpg` which is PostgreSQL-specific.

#### Step 1: Install PostgreSQL

- **Linux (Ubuntu/Debian):** `sudo apt install postgresql postgresql-contrib`
- **macOS (Homebrew):** `brew install postgresql@15`
- **Windows:** Download from [postgresql.org](https://www.postgresql.org/download/windows/)
- **Docker:** See [Docker Deployment](#docker-deployment) below

#### Step 2: Create a Database and User

```bash
sudo -u postgres psql
```

```sql
CREATE USER insightengine WITH PASSWORD 'your_secure_password';
CREATE DATABASE insightengine OWNER insightengine;
GRANT ALL PRIVILEGES ON DATABASE insightengine TO insightengine;
\q
```

#### Step 3: Configure the Database Connection

Add the following to your `.env` file:

```env
DB_HOST=localhost
DB_PORT=5432
DB_USER=insightengine
DB_PASSWORD=your_secure_password
DB_NAME=insightengine
DB_CHARSET=utf8
DB_DIALECT=postgresql
```

> **⚠️ Common Mistake:** Make sure `DB_PORT` is `5432` (PostgreSQL default), **not** `3306` (MySQL default). Using the wrong port will cause connection failures.

> **⚠️ SSL Mode:** If you encounter an error like `SSL mode is not supported by asyncpg`, you may need to adjust the SSL configuration. For local development, set `DB_DIALECT=postgresql` and ensure the asyncpg connection string does not include SSL parameters. For remote databases, check your PostgreSQL server's SSL configuration.

### Database Initialization

After configuring the connection, initialize the database schema:

```bash
python -m app.db.init_db
```

Or follow the project's migration instructions if using Alembic.

> **Known Issue:** If you see errors about missing tables (e.g., `daily_news`, `daily_topics`), make sure the database initialization script has been run successfully. These tables are created during the initialization process.

---

## API Key Configuration

This is the **most common source of setup issues**. InsightEngine uses multiple LLM API endpoints for different engines. Each engine requires its own API key, base URL, and model name.

### Understanding the Engine Architecture

InsightEngine uses several specialized engines, each of which can use a different LLM provider:

| Engine | Purpose |
|--------|---------|
| `INSIGHT_ENGINE` | Main analysis and insight generation |
| `MEDIA_ENGINE` | Media content processing |
| `QUERY_ENGINE` | Query generation and optimization |
| `REPORT_ENGINE` | Report generation |
| `MINDSPIDER` | Web crawling and data extraction |
| `FORUM_HOST` | Forum/discussion analysis |
| `KEYWORD_OPTIMIZER` | Keyword analysis and optimization |

### Configuring API Keys in `.env`

Create a `.env` file in the project root (copy from `.env.example` if available):

```env
# Insight Engine (Main LLM)
INSIGHT_ENGINE_API_KEY=sk-your-api-key-here
INSIGHT_ENGINE_BASE_URL=https://api.openai.com/v1
INSIGHT_ENGINE_MODEL_NAME=gpt-4o

# Media Engine
MEDIA_ENGINE_API_KEY=sk-your-api-key-here
MEDIA_ENGINE_BASE_URL=https://api.openai.com/v1
MEDIA_ENGINE_MODEL_NAME=gpt-4o

# Query Engine
QUERY_ENGINE_API_KEY=sk-your-api-key-here
QUERY_ENGINE_BASE_URL=https://api.openai.com/v1
QUERY_ENGINE_MODEL_NAME=gpt-4o

# Report Engine
REPORT_ENGINE_API_KEY=sk-your-api-key-here
REPORT_ENGINE_BASE_URL=https://api.openai.com/v1
REPORT_ENGINE_MODEL_NAME=gpt-4o

# MindSpider Engine
MINDSPIDER_API_KEY=sk-your-api-key-here
MINDSPIDER_BASE_URL=https://api.openai.com/v1
MINDSPIDER_MODEL_NAME=gpt-4o

# Forum Host Engine
FORUM_HOST_API_KEY=sk-your-api-key-here
FORUM_HOST_BASE_URL=https://api.openai.com/v1
FORUM_HOST_MODEL_NAME=gpt-4o

# Keyword Optimizer Engine
KEYWORD_OPTIMIZER_API_KEY=sk-your-api-key-here
KEYWORD_OPTIMIZER_BASE_URL=https://api.openai.com/v1
KEYWORD_OPTIMIZER_MODEL_NAME=gpt-4o
```

### Using a Single Provider for All Engines

If you are using a single LLM provider (e.g., OpenAI), you can use the same API key and base URL for all engines. However, each engine's environment variable **must** still be set individually.

### Critical BASE_URL Configuration Rules

> **⚠️ This is the #1 cause of 404 errors!**

The `BASE_URL` should point to the **root** of the API endpoint, **NOT** the full chat completions path.

| ✅ Correct | ❌ Incorrect |
|------------|--------------|
| `https://api.openai.com/v1` | `https://api.openai.com/v1/chat/completions` |
| `https://your-provider.com/v1` | `https://your-provider.com/v1/chat/completions` |

InsightEngine automatically appends `/chat/completions` to the base URL internally. If you include it in the `BASE_URL`, the resulting URL will be `/v1/chat/completions/chat/completions`, causing a **404 Not Found** error.

### Protocol Requirement

Always include `https://` (or `http://` for local/self-hosted endpoints) in the `BASE_URL`:

| ✅ Correct | ❌ Incorrect |
|------------|--------------|
| `https://api.openai.com/v1` | `api.openai.com/v1` |
| `http://localhost:8000/v1` | `localhost:8000/v1` |

### Model Name Configuration

Ensure the model name exactly matches what your provider supports:

- **OpenAI:** `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `gpt-3.5-turbo`
- **Azure OpenAI:** Use your deployment name, not the model name
- **Other providers:** Check your provider's documentation for supported model IDs

> **Known Issue:** Using an incorrect model name will result in a "model not found" error (usually 404). Double-check your provider's model catalog.

### Temperature Parameter

Some LLM providers only support `temperature=1`. If you encounter errors related to temperature values, check your provider's documentation for supported parameter ranges.

### Search Tool Configuration

InsightEngine supports multiple search tools. Configure which one to use with:

```env
SEARCH_TOOL_TYPE=AnspireAPI
```

Options:
- `AnspireAPI` — Anspire search API
- `Bocha` — Bocha web search API

Then configure the corresponding keys:

```env
# For AnspireAPI
ANSPIRE_BASE_URL=https://api.anspire.com
ANSPIRE_API_KEY=your-anspire-key

# For Bocha
BOCHA_BASE_URL=https://api.bocha.com
BOCHA_WEB_SEARCH_API_KEY=your-bocha-key
```

### Verifying API Configuration

Test your API key setup before running the full application:

```python
import openai

client = openai.OpenAI(
    api_key="sk-your-key",
    base_url="https://api.openai.com/v1"
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}],
    max_tokens=10
)
print(response.choices[0].message.content)
```

---

## Running the Application

Once all configuration is complete:

```bash
# Activate your virtual environment
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows

# Run the application
python -m app.main
```

Or if using uvicorn:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Docker Deployment

### Using Docker Compose

The project includes a `docker-compose.yml` for easy deployment:

```bash
docker compose up -d
```

### Docker Database Issues

If you encounter "Failed to resolve postgres:15 image" errors:

1. **Check Docker Hub access:** Ensure Docker can pull images from Docker Hub
2. **Use a mirror:** If behind a firewall, configure a Docker registry mirror
3. **Pull the image manually first:**

```bash
docker pull postgres:15
docker compose up -d
```

### Docker Database Hostname

When running both the application and database in Docker Compose, use the **service name** as the hostname:

```env
DB_HOST=postgres
```

Do **NOT** use `localhost` or `127.0.0.1` when the application is running inside Docker. Use `localhost` only when the application runs on the host and the database runs in Docker with a port mapping.

---

## Windows-Specific Troubleshooting

Windows users frequently encounter unique issues. Here are the most common ones and their solutions.

### 1. UnicodeDecodeError: 'gbk' Codec

**Symptom:**

```
UnicodeDecodeError: 'gbk' codec can't decode byte 0x80 in position X
```

This occurs when InsightEngine uses `subprocess` to run commands and tries to decode output using the system default encoding (GBK on Chinese Windows systems).

**Solution A: Set environment variable for UTF-8**

Open PowerShell as Administrator and run:

```powershell
[System.Environment]::SetEnvironmentVariable('PYTHONUTF8', '1', 'User')
```

Then restart your terminal. This forces Python to use UTF-8 for all text I/O.

**Solution B: Set console code page**

Before running the application:

```cmd
chcp 65001
```

**Solution C: Modify the system locale**

1. Go to **Settings → Time & Language → Language and region**
2. Click **Administrative language settings**
3. Click **Change system locale**
4. Check **Beta: Use Unicode UTF-8 for worldwide language support**
5. Restart your computer

### 2. UNC Path Vulnerability (CVE-2026-33682)

**Symptom:** On Windows, UNC paths (e.g., `\\server\share`) can be used in certain inputs to trigger Server-Side Request Forgery (SSRF) attacks.

**Solution:** Always validate and sanitize file paths in your application. Avoid accepting raw UNC paths in user input. If you must process file paths, resolve them to local paths first.

### 3. Path Separator Issues

Windows uses backslashes (`\`) while the codebase may expect forward slashes (`/`). This can cause issues with file paths in configuration.

**Solution:** Use raw strings or forward slashes in your `.env` file:

```env
LOG_FILE=logs/insightengine.log
```

### 4. Python Virtual Environment on Windows

Remember to use the correct activation script:

```cmd
venv\Scripts\activate
```

Not `source venv/bin/activate` (that's for Linux/macOS).

---

## Common Errors and Solutions

### Authentication Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `401 Unauthorized` | Invalid or missing API key | Check that the API key is correct and properly set in `.env` |
| `402 Payment Required` | Insufficient API balance | Top up your API provider account |
| `403 Forbidden` | API key lacks permissions | Check your API key's permissions on the provider dashboard |

### Connection Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `404 Not Found` on `/chat/completions` | Double path in BASE_URL | Remove `/chat/completions` from BASE_URL — see [BASE_URL Configuration](#critical-base_url-configuration-rules) |
| `Connection refused` | Wrong port or host | Verify `DB_HOST` and `DB_PORT` in `.env` |
| `Password authentication failed` | Wrong DB credentials | Double-check `DB_USER` and `DB_PASSWORD` |

### Rate Limiting

| Error | Cause | Solution |
|-------|-------|----------|
| `429 Too Many Requests` | API rate limit exceeded | Reduce request frequency or upgrade your API plan |

**Mitigation strategies:**
- Add retry logic with exponential backoff
- Reduce concurrent request count
- Use a higher-tier API plan
- Distribute requests across multiple API keys

### Content Filtering

| Error | Cause | Solution |
|-------|-------|----------|
| `Content Exists Risk` / Content filter triggered | LLM provider's safety filter blocked the response | Rephrase the input to avoid triggering content filters, or switch to a less restrictive provider/model |

This is especially common with Chinese-language content due to stricter filtering on some providers.

### Token Limit Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Token limit exceeded` / `context_length_exceeded` | Input + output exceeds model's token limit | Reduce input size, use a model with a larger context window, or chunk your input |

### Database Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `relation "daily_news" does not exist` | Database not initialized | Run the database initialization script |
| `SSL mode not supported` | asyncpg SSL configuration mismatch | For local dev, remove SSL params from the connection string |
| `Connection refused` (port 3306) | Using MySQL port instead of PostgreSQL | Change `DB_PORT` to `5432` |

### Security Note

> **⚠️ API Key Exposure:** The `/api/config` endpoint may expose configuration including API keys without authentication. If deploying in a production or shared environment, ensure proper access controls are in place. Consider adding authentication middleware or restricting access to this endpoint.

---

## Getting Help

If you're still having trouble after following this guide:

1. **Check existing issues:** [GitHub Issues](https://github.com/666ghj/BettaFish/issues) — your problem may already be reported and resolved
2. **Search closed issues:** Many common setup problems have been solved in closed issues
3. **Open a new issue:** Include your error message, environment details (OS, Python version), and what you've already tried
4. **Provide your configuration** (with API keys redacted) when reporting issues

---

*This guide was compiled based on analysis of closed issues in the InsightEngine repository to address the most common onboarding pain points. Last updated based on issues through June 2025.*
