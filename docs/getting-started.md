# Getting Started with BettaFish

This guide covers installation, configuration, and common troubleshooting steps to help you get up and running quickly.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Database Setup](#database-setup)
- [API Key Configuration](#api-key-configuration)
- [Common API Mistakes](#common-api-mistakes)
- [Search Tool Configuration](#search-tool-configuration)
- [Windows Troubleshooting](#windows-troubleshooting)
- [Docker Deployment](#docker-deployment)
- [Quick Start Checklist](#quick-start-checklist)

## Prerequisites

- Python 3.9 or higher
- PostgreSQL 12+ or MySQL 8+ (or Docker for containerized setup)
- Valid API keys for the LLM providers you intend to use

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/ospocn/BettaFish.git
   cd BettaFish
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scriptsctivate
   pip install -r requirements.txt
   ```

   > **Tip:** If you encounter dependency conflicts, try installing in a fresh virtual environment. Some users have reported issues with conflicting versions of `aiohttp` and `httpx`.

3. Copy the example environment file and configure it:
   ```bash
   cp .env.example .env
   ```

## Database Setup

### PostgreSQL (Recommended)

1. Install PostgreSQL or use the provided Docker setup:
   ```bash
   docker compose up -d db
   ```

2. Create the database:
   ```sql
   CREATE DATABASE bettafish;
   ```

3. Update your `.env` file:
   ```
   DATABASE_URL=postgresql://user:password@localhost:5432/bettafish
   ```

4. Run migrations:
   ```bash
   python manage.py migrate
   ```

### MySQL

1. Update your `.env` file with the MySQL connection string:
   ```
   DATABASE_URL=mysql://user:password@localhost:3306/bettafish
   ```

2. Run migrations as above.

### Using Docker for the Full Stack

See the [Docker Deployment](#docker-deployment) section below.

## API Key Configuration

BettaFish supports 7 LLM agents. Configure the ones you need in your `.env` file:

| Agent        | Environment Variable       | Where to Get Key                          |
|-------------|---------------------------|-------------------------------------------|
| OpenAI      | `OPENAI_API_KEY`          | https://platform.openai.com/api-keys      |
| Azure OpenAI| `AZURE_OPENAI_API_KEY`    | Azure Portal                              |
| Anthropic   | `ANTHROPIC_API_KEY`       | https://console.anthropic.com/            |
| Google      | `GOOGLE_API_KEY`          | https://aistudio.google.com/apikey        |
| DeepSeek    | `DEEPSEEK_API_KEY`        | https://platform.deepseek.com/            |
| ZhipuAI     | `ZHIPUAI_API_KEY`         | https://open.bigmodel.cn/                 |
| Ollama      | No key needed (local)     | https://ollama.com/                       |

Example `.env` entries:
```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=sk-...
```

> **Note:** You only need to configure the API keys for the providers you plan to use. The application will gracefully skip unconfigured agents.

## Common API Mistakes

### 1. Double Path in API Base URL

**Wrong:**
```
OPENAI_API_BASE=https://api.openai.com/v1/v1/chat/completions
```

**Correct:**
```
OPENAI_API_BASE=https://api.openai.com/v1
```

The application appends the path automatically. Do not include the endpoint path in the base URL.

### 2. Missing Protocol in API Base URL

**Wrong:**
```
OPENAI_API_BASE=api.openai.com/v1
```

**Correct:**
```
OPENAI_API_BASE=https://api.openai.com/v1
```

Always include `https://` (or `http://` for local services like Ollama).

### 3. Ollama Base URL

For local Ollama, use:
```
OLLAMA_API_BASE=http://localhost:11434
```

Do **not** add `/api` or `/v1` to the Ollama base URL.

## Search Tool Configuration

BettaFish can use web search tools to enhance responses. Configure them in your `.env`:

```
SEARCH_ENGINE=bing  # Options: bing, google, duckduckgo
BING_SEARCH_API_KEY=your-key-here
```

> **Note:** If you don't configure a search engine, the application will still work but without web search capabilities.

## Windows Troubleshooting

### GBK Encoding Errors

If you see `UnicodeDecodeError: 'gbk' codec can't decode byte...`, set the encoding:

```bash
set PYTHONUTF8=1
```

Or add this to the top of the main entry script:
```python
import sys
sys.stdout.reconfigure(encoding='utf-8')
```

### WeasyPrint Installation Issues

WeasyPrint requires GTK libraries on Windows. Install it using:

1. Download GTK from https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer
2. Install it, then reinstall WeasyPrint:
   ```bash
   pip install weasyprint --force-reinstall
   ```

Alternatively, if you don't need PDF export, you can skip WeasyPrint by removing it from `requirements.txt`.

## Docker Deployment

For a quick start with all dependencies:

1. Build and start all services:
   ```bash
   docker compose up -d
   ```

2. The application will be available at `http://localhost:8000`.

3. To view logs:
   ```bash
   docker compose logs -f app
   ```

4. To stop all services:
   ```bash
   docker compose down
   ```

> **Tip:** If you modify `.env` after starting containers, restart them with `docker compose up -d` to pick up changes.

## Quick Start Checklist

- [ ] Python 3.9+ installed
- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file configured with database URL
- [ ] Database running and migrations applied
- [ ] At least one LLM API key configured
- [ ] API base URLs are correct (no double paths, include protocol)
- [ ] (Optional) Search engine configured
- [ ] (Windows) UTF-8 encoding set if needed
- [ ] (Windows) WeasyPrint GTK installed if PDF export is needed

---

If you run into issues not covered here, please check the [existing issues](https://github.com/ospocn/BettaFish/issues) or open a new one.
