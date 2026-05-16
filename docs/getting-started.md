# Getting Started with BettaFish

> **BettaFish** is a multi-agent sentiment analysis platform powered by LLMs. This guide will walk you through installation, dependency management, database setup, API key configuration, and troubleshooting — based on the most common issues reported by our users.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Dependency Management](#dependency-management)
- [Database Setup](#database-setup)
- [API Key Configuration](#api-key-configuration)
- [Running the Application](#running-the-application)
- [Windows-Specific Troubleshooting](#windows-specific-troubleshooting)
- [Docker Deployment](#docker-deployment)
- [Common Errors & Solutions](#common-errors--solutions)
- [Getting Help](#getting-help)

---

## Prerequisites

| Requirement | Minimum Version | Notes |
|---|---|---|
| Python | 3.8+ | 3.9+ recommended for full compatibility |
| pip | Latest | Package manager for Python |
| PostgreSQL | 15+ | Primary recommended database |
| MySQL | 8.0+ | Alternative database (also supported) |
| Git | Latest | For cloning the repository |
| Conda (optional) | Latest | Recommended for Windows users to manage environments |

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/666ghj/BettaFish.git
cd BettaFish
```

### 2. Create a Virtual Environment

**Using Conda (recommended, especially on Windows):**

```bash
conda create -n bettafish python=3.9
conda activate bettafish
```

**Using venv:**

```bash
# Linux / macOS
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

> **⚠️ If you encounter errors during installation**, see [Dependency Management](#dependency-management) and [Windows-Specific Troubleshooting](#windows-specific-troubleshooting) below.

### 4. Configure Environment Variables

Copy the example environment file and edit it with your settings:

```bash
cp .env.example .env
```

Then open `.env` in your preferred editor and fill in the required values. See [API Key Configuration](#api-key-configuration) and [Database Setup](#database-setup) for detailed guidance.

---

## Dependency Management

### Common Dependency Issues

#### Missing Module: `humps`

**Error:** `ModuleNotFoundError: No module named 'humps'`

**Fix:** Install the missing package manually:

```bash
pip install pyhumps
```

> **Note:** The import name is `humps`, but the pip package name is `pyhumps`.

#### PyTorch Installation

The default `requirements.txt` installs the CPU version of PyTorch. If you need GPU support:

```bash
# Uninstall CPU version first
pip uninstall torch torchvision

# Install GPU version (adjust CUDA version as needed)
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu126
```

#### WeasyPrint Installation (PDF Export)

WeasyPrint requires system-level dependencies. On Linux:

```bash
# Ubuntu/Debian
sudo apt-get install build-essential python3-dev python3-pip python3-setuptools python3-wheel python3-cffi libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info

# Fedora
sudo dnf install redhat-rpm-config python3-devel cairo-gobject-devel pango-devel gdk-pixbuf2-devel libffi-devel
```

On Windows, WeasyPrint may require GTK runtime. See the [WeasyPrint Windows installation guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows) for details.

#### Playwright Installation (Web Crawling)

After installing the Python package, you must also install the browser binaries:

```bash
playwright install
```

### Verifying Your Installation

Run a quick check to ensure all critical packages are installed:

```bash
python -c "import flask, streamlit, openai, asyncpg, pandas, torch; print('All critical dependencies installed successfully!')"
```

---

## Database Setup

BettaFish supports both **PostgreSQL** (recommended) and **MySQL**. PostgreSQL is the default and strongly recommended.

### Option A: PostgreSQL (Recommended)

#### 1. Install PostgreSQL

```bash
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# macOS (Homebrew)
brew install postgresql@15

# Windows: Download from https://www.postgresql.org/download/windows/
```

#### 2. Create a Database

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create database and user
CREATE USER bettafish WITH PASSWORD 'your_secure_password';
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
DB_PASSWORD=your_secure_password
DB_NAME=bettafish
DB_CHARSET=utf8mb4
```

> **⚠️ Common Mistake:** Many users accidentally set `DB_PORT=3306` (the MySQL default) when using PostgreSQL. The default PostgreSQL port is **5432**. Using the wrong port will cause connection failures.

#### 4. Initialize the Database Schema

BettaFish will automatically create the required tables on first run. However, if you encounter errors about missing tables (e.g., `daily_news`, `daily_topics`), you may need to manually initialize:

```bash
python -m utils.db_init
```

### Option B: MySQL

#### 1. Install MySQL

```bash
# Ubuntu/Debian
sudo apt-get install mysql-server

# macOS (Homebrew)
brew install mysql

# Windows: Download from https://dev.mysql.com/downloads/installer/
```

#### 2. Create a Database

```bash
mysql -u root -p

CREATE DATABASE bettafish CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'bettafish'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON bettafish.* TO 'bettafish'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

#### 3. Configure `.env`

```env
DB_DIALECT=mysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=bettafish
DB_PASSWORD=your_secure_password
DB_NAME=bettafish
DB_CHARSET=utf8mb4
```

### Database Connection Troubleshooting

| Error | Cause | Solution |
|---|---|---|
| `Connection refused` | Database not running or wrong port | Verify the DB service is running and `DB_PORT` matches the actual port |
| `Password authentication failed` | Wrong credentials | Double-check `DB_USER` and `DB_PASSWORD` in `.env` |
| `connect() got unexpected keyword argument 'sslmode'` | Using `asyncpg` with MySQL | Set `DB_DIALECT=postgresql` when using asyncpg, or switch to `aiomysql` for MySQL |
| `database "bettafish" does not exist` | Database not created | Create the database first (see steps above) |
| `FATAL: role "bettafish" does not exist` | User not created | Create the database user first |

> **⚠️ SSL Mode Note:** The `sslmode` parameter is specific to PostgreSQL. If you are using MySQL, do not use `asyncpg` (which expects PostgreSQL). Use `aiomysql` instead by setting `DB_DIALECT=mysql`.

---

## API Key Configuration

BettaFish uses multiple LLM agents, each with its own API configuration. **Any OpenAI-compatible API provider will work** — you just need to set the `API_KEY`, `BASE_URL`, and `MODEL_NAME` correctly for each agent.

### Understanding the Agent Architecture

| Agent | Purpose | Recommended Model | Provider |
|---|---|---|---|
| **Insight Agent** | Core insight analysis | `kimi-k2-0711-preview` | [Moonshot](https://platform.moonshot.cn/) |
| **Media Agent** | Media content analysis | `gemini-2.5-pro` | [AIHubMix](https://aihubmix.com/) (relay) |
| **Query Agent** | Query processing | `deepseek-chat` | [DeepSeek](https://platform.deepseek.com/) |
| **Report Agent** | Report generation (needs strong model) | `gemini-2.5-pro` | [AIHubMix](https://aihubmix.com/) (relay) |
| **MindSpider Agent** | Web crawling & extraction | `deepseek-chat` | [DeepSeek](https://platform.deepseek.com/) |
| **Forum Host** | Forum moderation | `qwen-plus` | [Alibaba Cloud](https://www.aliyun.com/product/bailian) |
| **Keyword Optimizer** | SQL keyword optimization | `qwen-plus` | [Alibaba Cloud](https://www.aliyun.com/product/bailian) |

### Minimal Configuration (to get started quickly)

You don't need separate API keys for every agent. You can use a single provider for all agents initially:

```env
# Example: Using a single OpenAI-compatible provider for all agents
INSIGHT_ENGINE_API_KEY=sk-your-api-key
INSIGHT_ENGINE_BASE_URL=https://api.your-provider.com/v1
INSIGHT_ENGINE_MODEL_NAME=gpt-4o

MEDIA_ENGINE_API_KEY=sk-your-api-key
MEDIA_ENGINE_BASE_URL=https://api.your-provider.com/v1
MEDIA_ENGINE_MODEL_NAME=gpt-4o

QUERY_ENGINE_API_KEY=sk-your-api-key
QUERY_ENGINE_BASE_URL=https://api.your-provider.com/v1
QUERY_ENGINE_MODEL_NAME=gpt-4o

REPORT_ENGINE_API_KEY=sk-your-api-key
REPORT_ENGINE_BASE_URL=https://api.your-provider.com/v1
REPORT_ENGINE_MODEL_NAME=gpt-4o

MINDSPIDER_API_KEY=sk-your-api-key
MINDSPIDER_BASE_URL=https://api.your-provider.com/v1
MINDSPIDER_MODEL_NAME=gpt-4o

FORUM_HOST_API_KEY=sk-your-api-key
FORUM_HOST_BASE_URL=https://api.your-provider.com/v1
FORUM_HOST_MODEL_NAME=gpt-4o

KEYWORD_OPTIMIZER_API_KEY=sk-your-api-key
KEYWORD_OPTIMIZER_BASE_URL=https://api.your-provider.com/v1
KEYWORD_OPTIMIZER_MODEL_NAME=gpt-4o
```

> **💡 Tip:** We strongly recommend starting with the recommended models listed above. Get the system running first, then experiment with different providers.

### BASE_URL Configuration — Critical Details

The `BASE_URL` must point to the **root of the OpenAI-compatible API**, NOT the full chat completions endpoint. The application automatically appends `/chat/completions` to your `BASE_URL`.

#### ✅ Correct BASE_URL Examples

```env
INSIGHT_ENGINE_BASE_URL=https://api.moonshot.cn/v1
INSIGHT_ENGINE_BASE_URL=https://api.deepseek.com
INSIGHT_ENGINE_BASE_URL=https://aihubmix.com/v1
```

#### ❌ Incorrect BASE_URL Examples

```env
# WRONG: Double path — the app already appends /chat/completions
INSIGHT_ENGINE_BASE_URL=https://api.moonshot.cn/v1/chat/completions

# WRONG: Missing protocol (http:// or https://)
INSIGHT_ENGINE_BASE_URL=api.moonshot.cn/v1

# WRONG: Trailing slash may cause issues on some providers
INSIGHT_ENGINE_BASE_URL=https://api.moonshot.cn/v1/
```

> **⚠️ Double Path Error:** This is the #1 most common configuration mistake! If you see a `404` error when making LLM requests, check that your `BASE_URL` does not already include `/chat/completions`. The application constructs the full URL as `BASE_URL + /chat/completions`, so if your `BASE_URL` already ends with `/chat/completions`, the final URL will be `/v1/chat/completions/chat/completions`, which returns a 404.

### Search Tool Configuration

BettaFish supports web search through either Tavily, AnspireAPI, or BochaAPI:

```env
# Choose your search tool type
SEARCH_TOOL_TYPE=AnspireAPI    # Options: AnspireAPI or BochaAPI

# Tavily (alternative search)
TAVILY_API_KEY=tvly-your-tavily-key

# Anspire AI Search (recommended)
ANSPIRE_BASE_URL=https://plugin.anspire.cn/api/ntsearch/search
ANSPIRE_API_KEY=your-anspire-key

# Bocha AI Search (alternative)
BOCHA_BASE_URL=https://api.bocha.cn/v1/ai-search
BOCHA_WEB_SEARCH_API_KEY=your-bocha-key
```

> **Note:** `AnspireAPI` is an AI-powered search service. You can obtain an API key at [https://open.anspire.cn/](https://open.anspire.cn/).

### API Error Troubleshooting

| HTTP Error | Cause | Solution |
|---|---|---|
| **401 Unauthorized** | Invalid or expired API key | Verify your API key is correct and active. Check for trailing spaces or newlines in `.env`. |
| **404 Not Found** | Wrong `BASE_URL` or `MODEL_NAME` | Ensure `BASE_URL` does NOT include `/chat/completions`. Verify the model name is correct for your provider. |
| **402/403 Payment Required** | Insufficient API balance/quota | Top up your account at the provider's dashboard. |
| **429 Too Many Requests** | Rate limiting | Reduce request frequency or upgrade your API plan. Add retries with backoff. |
| **400 Bad Request (Content Risk)** | Content filtered by provider | Some providers (e.g., Alibaba Cloud/Qwen) have strict content policies. Try rephrasing your query or switching to a provider with fewer restrictions. |
| **400 Bad Request (Invalid temperature)** | Model doesn't support the temperature value | Some models (e.g., certain Qwen models) only accept `temperature=1`. Check your provider's documentation. |
| **400 Bad Request (Token limit)** | Input tokens exceed model's max sequence length | Reduce the length of your input text or switch to a model with a larger context window. |

---

## Running the Application

### Start the Flask Server

```bash
python app.py
```

The application will be available at `http://localhost:5000` by default.

### Start with Streamlit Reports

The application also provides Streamlit-based report viewers on the following ports:

| Service | Port |
|---|---|
| Main Flask App | 5000 |
| Insight Engine Reports | 8501 |
| Media Engine Reports | 8502 |
| Query Engine Reports | 8503 |

---

## Windows-Specific Troubleshooting

### GBK Encoding Error During Database Initialization

**Error:**

```
UnicodeDecodeError: 'gbk' codec can't decode byte 0x80 in position XXX
```

**Cause:** On Chinese-language Windows systems, the default encoding is GBK. When BettaFish spawns a subprocess to initialize the database, the subprocess inherits the system's GBK encoding, which cannot handle certain UTF-8 characters.

**Solution 1 — Set environment variable before running:**

```cmd
set PYTHONUTF8=1
python app.py
```

**Solution 2 — Set it permanently:**

```cmd
setx PYTHONUTF8 1
```

Then restart your terminal and run the application.

**Solution 3 — Use Conda with UTF-8:**

```cmd
conda activate bettafish
set PYTHONIOENCODING=utf-8
python app.py
```

### Streamlit SSRF Vulnerability with UNC Paths (CVE-2026-33682)

If you encounter SSRF-related warnings or errors involving UNC paths on Windows, make sure you are using the latest version of Streamlit:

```bash
pip install --upgrade streamlit
```

### General Windows Tips

1. **Use Conda** — Conda handles binary dependencies (like `cryptography`, `lxml`) better than pip on Windows.
2. **Use `python` instead of `python3`** — On Windows, the command is typically `python`, not `python3`.
3. **Long path names** — If you encounter path-related errors, move the project to a shorter path like `C:\bf\` instead of `C:\Users\YourName\Very\Long\Path\BettaFish\`.
4. **Visual C++ Build Tools** — Some packages require compilation. Install [Microsoft Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) if you see compilation errors.

---

## Docker Deployment

### Quick Start with Docker Compose

Docker is the easiest way to get BettaFish running, as it includes a PostgreSQL container:

```bash
# 1. Copy and configure .env
cp .env.example .env
# Edit .env with your API keys and database settings

# 2. Start all services
docker-compose up -d
```

This will start:
- **BettaFish** application on ports 5000, 8501, 8502, 8503
- **PostgreSQL** database on port 5444 (internal: 5432)

### Docker Configuration for Database

When using Docker Compose, the PostgreSQL container is automatically configured. Set these in your `.env`:

```env
POSTGRES_USER=bettafish
POSTGRES_PASSWORD=bettafish
POSTGRES_DB=bettafish
POSTGRES_PORT=5444
```

And update the database connection settings:

```env
DB_DIALECT=postgresql
DB_HOST=db           # Use the Docker service name
DB_PORT=5432         # Internal port inside the container
DB_USER=bettafish
DB_PASSWORD=bettafish
DB_NAME=bettafish
```

### Docker Troubleshooting

| Issue | Solution |
|---|---|
| **Image pull failure (DNS resolution)** | Try using a mirror: change `ghcr.io` to `ghcr.nju.edu.cn` in `docker-compose.yml` |
| **Health check failures on Streamlit ports** | Ensure ports 8501, 8502, 8503 are not in use by other services |
| **Config pattern mismatch error** | Ensure your `.env` file has no trailing whitespace or BOM characters |
| **Container exits immediately** | Check logs with `docker-compose logs bettafish` |

---

## Common Errors & Solutions

### `'Settings' object has no attribute 'LOG_FILE'`

**Cause:** Your `.env` file or `config.py` is out of date after an update.

**Fix:** Pull the latest code and compare your `.env` with `.env.example`:

```bash
git pull origin main
diff .env .env.example
```

Add any missing variables to your `.env` file.

### `IndentationError: unexpected indent` in `base_config.py`

**Cause:** The Python configuration file has incorrect indentation, possibly from manual editing.

**Fix:** Do not manually edit Python config files. Use the `.env` file for all configuration. If you must edit Python files, ensure consistent indentation (4 spaces, no tabs).

### Report Generation Issues

| Problem | Solution |
|---|---|
| **Blank charts in report** | The Report Agent needs a strong model. Use `gemini-2.5-pro` or equivalent. |
| **JSON parsing failure** | The LLM returned malformed JSON. Try a different model or retry. |
| **Report generation stuck/hanging** | Check your API key rate limits and network connectivity. |

### API Keys Exposed via `/api/config`

**Security Notice:** The configuration endpoint may expose API keys. In production deployments, ensure this endpoint is protected or disabled. See the project's security advisories for updates.

---

## Getting Help

- **GitHub Issues:** [https://github.com/666ghj/BettaFish/issues](https://github.com/666ghj/BettaFish/issues) — Search existing issues before creating a new one.
- **Discussions:** Check the Discussions tab for community support.
- **Contributing:** See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines.

---

*This guide was created based on analysis of common pain points reported in the project's closed issues. If you encounter an issue not covered here, please open a new issue on GitHub so we can improve this documentation.*
