# Getting Started with InsightEngine

Welcome to InsightEngine, an open-source data analytics tool for deep research and sentiment analysis. This guide will help you set up and run InsightEngine on your local machine.

## Prerequisites

Before you begin, ensure you have the following:

- **Python 3.10 or 3.11** (3.12+ may have compatibility issues)
- **MySQL 8.0** (or higher) with a running instance
- **Git** for cloning the repository
- **pip** and **virtualenv** (recommended)
- **Docker** (optional, for containerized deployment)

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/666ghj/BettaFish.git
cd BettaFish
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

The core dependencies are listed in `requirements.txt`. However, some additional packages may be required depending on your environment.

```bash
pip install -r requirements.txt
```

#### Additional Packages

Some users have reported missing packages. If you encounter import errors, install these manually:

```bash
pip install cryptography asyncmy typer watchdog
```

- `cryptography` is required for MySQL 8.0 authentication.
- `asyncmy` is needed for asynchronous MySQL driver (Python 3.13).
- `typer` is used by the MediaCrawler command-line interface.
- `watchdog` improves file watching performance in Streamlit apps.

### 4. Database Setup

InsightEngine uses MySQL to store crawled data and analysis results.

#### Create a Database

```sql
CREATE DATABASE mindspider CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

#### Configure Database Connection

Copy the example environment file and update the database credentials:

```bash
cp .env.example .env
```

Edit `.env` and set the following variables:

```ini
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=mindspider
```

#### Run Database Initialization

Navigate to the `MindSpider` directory and run the initialization script:

```bash
cd MindSpider
python schema/init_database.py
```

If you encounter foreign key errors, ensure your MySQL user has the necessary privileges and that the tables are created with compatible column types.

### 5. Configure API Keys

InsightEngine uses various LLM providers (OpenAI, DeepSeek, etc.) and search APIs (Tavily). You need to set the corresponding API keys in the environment or configuration files.

Add the following to your `.env` file:

```ini
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=...
TAVILY_API_KEY=...
```

Alternatively, you can set them directly in `config.py` under the respective engine settings.

### 6. Running InsightEngine

InsightEngine is accessible via the SingleEngineApp, a Streamlit-based interface.

#### Start the Streamlit App

```bash
cd SingleEngineApp
streamlit run insight_engine_streamlit_app.py
```

Then open your browser to `http://localhost:8501`.

#### Using Docker (Alternative)

If you prefer Docker, you can start the entire stack with:

```bash
docker-compose up -d
```

This will start MySQL, the crawler, and the Streamlit app. Check the logs for any issues.

## Troubleshooting

### Common Issues

#### Missing Dependencies

If you see errors like `ModuleNotFoundError: No module named 'cryptography'`, install the missing package as described above.

#### Database Connection Errors

- Ensure MySQL is running and accessible.
- Verify the credentials in `.env`.
- Check that the `mindspider` database exists.

#### API Key Errors

If you encounter `Unauthorized: missing or invalid API key`, make sure you have set the correct API key for the provider you are using. The default configuration uses DeepSeek; you may need to switch to a different provider if you don't have a DeepSeek key.

#### Windows-Specific Issues

On Windows, you may encounter DLL errors when loading PyTorch. Ensure you have the latest Microsoft Visual C++ Redistributable installed. Also, consider using WSL2 for a smoother experience.

#### Streamlit CORS/XSRF Warnings

The warning about `server.enableCORS` and `server.enableXsrfProtection` is harmless and can be ignored. If you want to disable it, set `server.enableXsrfProtection=False` in `~/.streamlit/config.toml`.

#### Reports Not Clearing

If you find that the engine continues a previous report after restart, manually delete the report files in the `insight_engine_streamlit_reports` directory.

### Getting Help

If you encounter issues not covered here, please:

1. Search existing [GitHub issues](https://github.com/666ghj/BettaFish/issues).
2. Open a new issue with detailed error logs and your environment information.

## Next Steps

Once you have InsightEngine running, try:

- Running a simple query (e.g., "Analyze sentiment about AI in 2025")
- Exploring the different engines (QueryEngine, MediaEngine, ReportEngine)
- Customizing the configuration for your own data sources

For advanced usage, refer to the [API documentation](https://github.com/666ghj/BettaFish/wiki) (coming soon).

---

*Happy analyzing! The InsightEngine Team*