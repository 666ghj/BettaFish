# Getting Started with InsightEngine (BettaFish)

Welcome to InsightEngine! This guide will help you get up and running quickly, addressing the most common setup and configuration issues reported by our community.

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
10. [Common Issues and Solutions](#common-issues-and-solutions)

---

## Prerequisites

- **Python 3.9-3.13** (Python 3.10+ recommended)
- **Conda** (recommended for managing environments, especially on Windows)
- **PostgreSQL 15+** (recommended) or **MySQL 8.0+**
- **Git**
- **Docker & Docker Compose** (optional, for containerized deployment)
- At least one OpenAI-compatible LLM API key (see [API Key Configuration](#api-key-configuration))

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/666ghj/BettaFish.git
cd BettaFish
```

### 2. Create a Conda Environment (Recommended)

Using Conda is strongly recommended, especially on Windows, to avoid encoding and dependency conflicts:

```bash
conda create -n bettafish python=3.10
conda activate bettafish
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

> **Note for GPU users:** If you have a CUDA-capable GPU and want to use GPU acceleration for the sentiment analysis model, install the GPU version of PyTorch:
>
> ```bash
> pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu126
> ```
>
> Install this **before** running `pip install -r requirements.txt` to avoid overwriting the GPU version with the CPU version.

> **Note:** If you encounter a `ModuleNotFoundError: No module named 'humps'`, install it manually:
>
> ```bash
> pip install pyhumps
> ```

### 4. Install Playwright Browsers

The MindSpider crawler uses Playwright for web scraping:

```bash
playwright install
```

---

## Dependency Management

The project relies on several key dependency groups:

| Category | Key Packages | Notes |
|---|---|---|
| **Web Framework** | Flask 2.3.3, Flask-SocketIO 5.3.6, FastAPI 0.110.2 | Core web services |
| **LLM Integration** | openai>=1.3.0 | OpenAI-compatible API client |
| **Database** | SQLAlchemy 2.0.35, asyncpg 0.29.0, psycopg[binary]>=3.1.0, pymysql 1.1.0, aiomysql 0.2.0 | PostgreSQL and MySQL support |
| **Data Science** | pandas>=2.0.0, numpy>=1.24.0, jieba 0.42.1 | Data processing and Chinese text segmentation |
| **ML/AI** | torch>=2.0.0, transformers>=4.30.0, sentence-transformers>=2.2.2 | Sentiment analysis model |
| **PDF Generation** | weasyprint>=60.0 | Report PDF export (Python 3.9-3.13 only) |
| **Web Scraping** | playwright 1.45.0, beautifulsoup4>=4.12.0 | MindSpider crawler |
| **Configuration** | pydantic 2.5.2, pydantic-settings 2.2.1, python-dotenv>=1.0.0 | Settings and env management |

### Troubleshooting Dependency Issues

- **`ModuleNotFoundError: No module named 'humps'`**: The package is named `pyhumps` on PyPI, not `humps`. Run `pip install pyhumps`.
- **`Settings object has no attribute 'LOG_FILE'`**: Make sure your `.env` file includes all required variables (copy from `.env.example`). This error occurs when the config loader cannot find expected settings.
- **WeasyPrint installation fails on Windows**: WeasyPrint requires GTK libraries. See the [Windows-Specific Troubleshooting](#windows-specific-troubleshooting) section below.

---

## Database Setup

InsightEngine supports **PostgreSQL** (recommended) and **MySQL**. PostgreSQL is the recommended choice.

### Option A: PostgreSQL (Recommended)

#### 1. Install PostgreSQL

- **Linux:** `sudo apt install postgresql postgresql-contrib`
- **macOS:** `brew install postgresql@15`
- **Windows:** Download from [postgresql.org](https://www.postgresql.org/download/windows/)

#### 2. Create Database and User

```sql
-- Connect to PostgreSQL as superuser
sudo -u postgres psql

-- Create user and database
CREATE USER bettafish WITH PASSWORD 'bettafish';
CREATE DATABASE bettafish OWNER bettafish;
GRANT ALL PRIVILEGES ON DATABASE bettafish TO bettafish;
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

> **Common Mistake:** Make sure `DB_PORT` is `5432` for PostgreSQL, not `3306` (which is MySQL's default port). Using the wrong port is a very common source of connection failures.

#### 4. Initialize the Database

The application will automatically create the required tables on first startup. If you encounter issues:

```bash
# Manually initialize if needed
python -c "from app import create_app; app = create_app(); app.app_context().push()"
```

> **SSL Mode Issue with asyncpg:** If you see an error like `sslmode value "prefer" is not supported`, add `?ssl=disable` to your database URL or set the `PGSSLROOTCERT` environment variable to an empty string. Some versions of asyncpg do not support certain SSL modes. You can also set `PGSSLROOTCERT=""` as an environment variable.

### Option B: MySQL

```env
DB_DIALECT=mysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=bettafish
DB_PASSWORD=bettafish
DB_NAME=bettafish
DB_CHARSET=utf8mb4
```

> **Important:** When using MySQL, make sure the `DB_CHARSET` is set to `utf8mb4` (not `utf8`) to properly support emoji and special characters.

### Option C: Using Docker for the Database

If you prefer not to install PostgreSQL locally, you can run it in Docker:

```bash
docker run -d \
  --name bettafish-postgres \
  -e POSTGRES_USER=bettafish \
  -e POSTGRES_PASSWORD=bettafish \
  -e POSTGRES_DB=bettafish \
  -p 5432:5432 \
  -v bettafish_pgdata:/var/lib/postgresql/data \
  postgres:15
```

---

## API Key Configuration

InsightEngine uses **7 different LLM agents**, each with its own API key, base URL, and model name. This is the most common source of setup issues.

### Understanding the Agent System

| Agent | Purpose | Recommended Model | Recommended Provider |
|---|---|---|---|
| **Insight Agent** | Core insight analysis | `kimi-k2` | Moonshot (platform.moonshot.cn) |
| **Media Agent** | Media content analysis | `gemini-2.5-pro` | Google |
| **Query Agent** | Query processing | `deepseek-chat` | DeepSeek (platform.deepseek.com) |
| **Report Agent** | Report generation (needs strong model!) | `gemini-2.5-pro` | Google |
| **MindSpider Agent** | Web crawling and extraction | `deepseek-chat` | DeepSeek |
| **Forum Host** | Forum discussion management | `qwen-plus` | Alibaba (Aliyun Bailian) |
| **Keyword Optimizer** | Search keyword optimization | `qwen-plus` | Alibaba (Aliyun Bailian) |

> **Important:** Any OpenAI-compatible API can be used. The key requirement is that each agent's `API_KEY`, `BASE_URL`, and `MODEL_NAME` are set correctly and consistently.

### Step 1: Copy the Environment Template

```bash
cp .env.example .env
```

### Step 2: Configure Your API Keys

Edit `.env` and fill in the credentials for each agent:

```env
# Insight Agent
INSIGHT_ENGINE_API_KEY=sk-your-insight-api-key
INSIGHT_ENGINE_BASE_URL=https://api.moonshot.cn/v1
INSIGHT_ENGINE_MODEL_NAME=kimi-k2

# Media Agent
MEDIA_ENGINE_API_KEY=your-media-api-key
MEDIA_ENGINE_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
MEDIA_ENGINE_MODEL_NAME=gemini-2.5-pro

# Query Agent
QUERY_ENGINE_API_KEY=sk-your-deepseek-api-key
QUERY_ENGINE_BASE_URL=https://api.deepseek.com
QUERY_ENGINE_MODEL_NAME=deepseek-chat

# Report Agent
REPORT_ENGINE_API_KEY=your-report-api-key
REPORT_ENGINE_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
REPORT_ENGINE_MODEL_NAME=gemini-2.5-pro

# MindSpider Agent
MINDSPIDER_API_KEY=sk-your-deepseek-api-key
MINDSPIDER_BASE_URL=https://api.deepseek.com
MINDSPIDER_MODEL_NAME=deepseek-chat

# Forum Host
FORUM_HOST_API_KEY=sk-your-aliyun-api-key
FORUM_HOST_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
FORUM_HOST_MODEL_NAME=qwen-plus

# Keyword Optimizer
KEYWORD_OPTIMIZER_API_KEY=sk-your-aliyun-api-key
KEYWORD_OPTIMIZER_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
KEYWORD_OPTIMIZER_MODEL_NAME=qwen-plus
```

### Common API Configuration Mistakes

#### 1. Double Path in BASE_URL (Most Common Error!)

The application automatically appends `/chat/completions` to the `BASE_URL`. **Do NOT include `/chat/completions` in your BASE_URL.**

| Wrong | Correct |
|---|---|
| `https://api.deepseek.com/v1/chat/completions` | `https://api.deepseek.com/v1` |
| `https://api.openai.com/v1/chat/completions` | `https://api.openai.com/v1` |
| `https://api.moonshot.cn/v1/chat/completions` | `https://api.moonshot.cn/v1` |

This mistake causes a **404 error** because the application sends requests to `/v1/chat/completions/chat/completions` (doubled path).

#### 2. Missing `http://` or `https://` Protocol Prefix

Always include the protocol in `BASE_URL`:

| Wrong | Correct |
|---|---|
| `api.deepseek.com/v1` | `https://api.deepseek.com/v1` |

#### 3. Invalid API Key (401 Error)

Double-check your API key:
- Ensure there are no leading/trailing spaces or newlines
- Verify the key is active and has not been revoked
- Confirm the key has sufficient permissions for the model you are using

#### 4. Incorrect Model Name

Model names must match exactly what the provider supports:
- Check the provider's documentation for available model IDs
- Model names are case-sensitive
- Common mistake: using `gpt-4` when your key only has access to `gpt-3.5-turbo`

#### 5. Temperature Parameter Errors

Some models (especially newer ones like certain Gemini models) only accept `temperature=1`. If you see an error about invalid temperature values, check the model's documentation for supported parameter ranges.

#### 6. Rate Limiting (429 Error)

If you encounter 429 errors:
- Reduce the frequency of API calls
- Upgrade your API plan for higher rate limits
- Use different API keys/providers for different agents to distribute the load
- Add retry logic or increase timeouts in the configuration

#### 7. Insufficient Balance/Quota (402/403 Error)

- Check your API account balance
- Some providers require pre-paid credits
- Ensure your account is not in arrears

#### 8. Content Filtering (400 Error - "Content Exists Risk")

Some LLM providers (especially Chinese providers like Moonshot/Aliyun) have content safety filters that may reject requests:
- This is a provider-side restriction, not a bug in InsightEngine
- Try rephrasing your query
- Switch to a provider with less restrictive content filtering
- Use providers like DeepSeek or OpenAI for sensitive topics

---

## Search Tool Configuration

InsightEngine supports multiple web search tools for gathering real-time information.

### Available Search Tools

| Tool | SEARCH_TOOL_TYPE Value | Required Config |
|---|---|---|
| **Anspire** | `AnspireAPI` | `ANSPIRE_BASE_URL`, `ANSPIRE_API_KEY` |
| **Bocha** | `BochaAPI` | `BOCHA_BASE_URL`, `BOCHA_WEB_SEARCH_API_KEY` |
| **Tavily** | (set `TAVILY_API_KEY`) | `TAVILY_API_KEY` |

### Configuration Example

```env
# Choose one search tool
SEARCH_TOOL_TYPE=AnspireAPI

# Anspire configuration
ANSPIRE_BASE_URL=https://plugin.anspire.cn/api/ntsearch/search
ANSPIRE_API_KEY=your-anspire-api-key

# Or use Bocha
# SEARCH_TOOL_TYPE=BochaAPI
# BOCHA_BASE_URL=https://api.bocha.cn/v1/ai-search
# BOCHA_WEB_SEARCH_API_KEY=your-bocha-api-key

# Or use Tavily
# TAVILY_API_KEY=your-tavily-api-key
```

> **Tip:** If the search tool is not working, verify that `SEARCH_TOOL_TYPE` matches the tool you have configured. Mixing up tool types and credentials is a common mistake.

---

## Running the Application

### Local Development

```bash
# Make sure your Conda environment is activated
conda activate bettafish

# Start the application
python app.py
```

The application will be available at:
- **Web UI:** http://localhost:5000
- **API:** http://localhost:5000/api

### Verifying Your Setup

1. Open http://localhost:5000 in your browser
2. Submit a test query to verify the Insight Agent is working
3. Check the logs in the `logs/` directory for any errors

---

## Docker Deployment

### Quick Start with Docker Compose

```bash
# Copy and edit the environment file
cp .env.example .env
# Edit .env with your API keys and database settings

# Start all services
docker-compose up -d
```

### Docker Configuration Notes

1. **Database Host:** When using Docker Compose, the PostgreSQL service is named `db`. Set `DB_HOST=db` (not `localhost`) in your `.env` file so the application container can reach the database container.

   | Scenario | DB_HOST Value |
   |---|---|
   | Running locally (not Docker) | `localhost` |
   | Running with Docker Compose | `db` |

2. **Docker Image Mirrors:** If you are in China and have trouble pulling images, the project provides a mirror:
   - Original: `ghcr.io/666ghj/bettafish:latest`
   - Mirror: `ghcr.nju.edu.cn/666ghj/bettafish:latest`

3. **PostgreSQL Image:** If `postgres:15` fails to pull, try using a mirror registry or pre-pull the image manually.

4. **Database Port:** The Docker Compose configuration maps PostgreSQL's internal port 5432 to host port 5444 to avoid conflicts with any locally installed PostgreSQL. Adjust as needed.

### Docker Compose Database Defaults

The default PostgreSQL configuration in `docker-compose.yml`:

```env
POSTGRES_USER=bettafish
POSTGRES_PASSWORD=bettafish
POSTGRES_DB=bettafish
```

Make sure your `.env` file's database settings match these values when using Docker Compose.

---

## Windows-Specific Troubleshooting

Windows users encounter several unique issues. Here are the solutions:

### 1. GBK Encoding Error During Database Initialization

**Problem:** When initializing the database on Windows, you may see:
```
UnicodeDecodeError: 'gbk' codec can't decode byte 0x80 in position XXX
```

**Root Cause:** Windows defaults to the GBK encoding for the system locale. When the application reads SQL or data files containing UTF-8 characters (especially emoji), Python's default file reading uses GBK, causing decoding failures.

**Solution:**

**Option A - Set Python's default encoding (Recommended):**
```bash
# In your Conda environment
conda activate bettafish
set PYTHONUTF8=1
python app.py
```

Or set it permanently in your system environment variables:
1. Open **System Properties** > **Environment Variables**
2. Add a new user variable: `PYTHONUTF8` = `1`

**Option B - Use Conda with UTF-8 forced:**
```bash
conda activate bettafish
conda env config vars set PYTHONUTF8=1
conda deactivate
conda activate bettafish
```

**Option C - Set console code page:**
```bash
chcp 65001
python app.py
```

### 2. WeasyPrint Installation on Windows

WeasyPrint requires GTK runtime libraries on Windows:

1. Download and install MSYS2 from [msys2.org](https://www.msys2.org/)
2. Open MSYS2 terminal and run:
   ```bash
   pacman -S mingw-w64-x86_64-gtk3 mingw-w64-x86_64-pango
   ```
3. Add `C:\msys64\mingw64\bin` to your system PATH
4. Reinstall WeasyPrint: `pip install weasyprint`

### 3. Docker Mirror Resolution on Chinese Networks

If Docker cannot pull images due to network restrictions:

1. Configure Docker daemon with a mirror registry
2. Edit `C:\Users\<YourUser>\.docker\daemon.json`:
   ```json
   {
     "registry-mirrors": [
       "https://mirror.ccs.tencentyun.com",
       "https://registry.docker-cn.com"
     ]
   }
   ```
3. Restart Docker Desktop
4. Use the NJU mirror for the application image: `ghcr.nju.edu.cn/666ghj/bettafish:latest`

### 4. Path Issues on Windows

- Always use forward slashes (`/`) or escaped backslashes (`\\`) in configuration files
- Ensure Git is configured to not convert line endings: `git config --global core.autocrlf input`

---

## Common Issues and Solutions

### Database Issues

| Issue | Cause | Solution |
|---|---|---|
| Connection refused | DB not running or wrong port | Verify DB is running; check `DB_PORT` (5432 for PostgreSQL, 3306 for MySQL) |
| Password authentication failed | Wrong credentials | Verify `DB_USER` and `DB_PASSWORD` match your database |
| SSL mode not supported | asyncpg SSL incompatibility | Set `PGSSLROOTCERT=""` or add `?ssl=disable` to DB URL |
| Tables not found | DB not initialized | Restart the app; it auto-creates tables on startup |
| `daily_news` or `daily_topics` table missing | Incomplete initialization | Check logs for init errors; manually create if needed |
| Docker DB host resolution failed | Using `localhost` instead of `db` | Set `DB_HOST=db` in Docker deployments |

### API/LLM Issues

| Issue | Cause | Solution |
|---|---|---|
| 401 Unauthorized | Invalid API key | Check key is correct, no extra whitespace, and is active |
| 404 Not Found | Double path in BASE_URL | Remove `/chat/completions` from BASE_URL |
| 400 Bad Request (temperature) | Model doesn't support given temperature | Check model docs; some models only accept `temperature=1` |
| 429 Too Many Requests | Rate limiting | Reduce call frequency or upgrade API plan |
| 402/403 Payment Required | Insufficient balance | Top up your API account |
| 400 "Content Exists Risk" | Provider content filter triggered | Rephrase query or switch to a less restrictive provider |
| Report generation fails/incomplete | Weak model or token limit | Use a strong model (e.g., `gemini-2.5-pro`) for the Report Agent |
| JSON parsing errors in reports | Model output format issues | Try a different model or adjust the prompt |

### MindSpider/Crawler Issues

| Issue | Cause | Solution |
|---|---|---|
| `ModuleNotFoundError: No module named 'humps'` | Missing `pyhumps` package | `pip install pyhumps` |
| Playwright browser not found | Browsers not installed | `playwright install` |
| Crawler returns no results | Website blocking or timeout | Check network connectivity; some sites block automated access |
| MindSpider not auto-scheduled | Scheduler not configured | Check the MindSpider configuration in your `.env` file |

### Configuration Issues

| Issue | Cause | Solution |
|---|---|---|
| `Settings object has no attribute 'LOG_FILE'` | Incomplete `.env` file | Copy from `.env.example` and fill in all required fields |
| Config pattern mismatch in Docker | `.env` not mounted properly | Ensure `.env` is in the Docker volume mounts |
| API keys visible at `/api/config` | Security concern | Restrict access to this endpoint in production |

---

## Quick Start Checklist

- [ ] Python 3.9+ installed with Conda environment created
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] Playwright browsers installed (`playwright install`)
- [ ] PostgreSQL or MySQL running and accessible
- [ ] `.env` file created from `.env.example` with all fields filled
- [ ] `DB_DIALECT`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` configured correctly
- [ ] All 7 agent API keys (`API_KEY`, `BASE_URL`, `MODEL_NAME`) configured
- [ ] `BASE_URL` does **not** include `/chat/completions`
- [ ] All `BASE_URL` values include `https://` protocol prefix
- [ ] `SEARCH_TOOL_TYPE` matches your chosen search tool
- [ ] Search tool API key configured
- [ ] (Windows) `PYTHONUTF8=1` environment variable set
- [ ] (Docker) `DB_HOST=db` instead of `localhost`

---

## Getting Help

If you encounter issues not covered in this guide:

1. Check the [existing issues](https://github.com/666ghj/BettaFish/issues) for similar problems
2. Search the [discussions](https://github.com/666ghj/BettaFish/discussions) for community solutions
3. Open a new issue with:
   - Your OS and Python version
   - The exact error message
   - Your `.env` configuration (with sensitive values redacted)
   - Steps to reproduce the issue

---

*This guide was created based on analysis of closed issues in the BettaFish repository. If you find inaccuracies or have suggestions for improvement, please open an issue or submit a pull request.*
