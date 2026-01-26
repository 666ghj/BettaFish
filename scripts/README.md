# LiteLLM Gateway Client

A Python client for connecting to LiteLLM proxy gateways to access multiple LLM providers through a unified API.

## Setup

### 1. Configure Environment Variables

Add the following to your `.env` file:

```bash
LITELLM_BASE_URL=https://llm.art-ai.me
LITELLM_API_KEY=your_api_key_here
```

### 2. Install Dependencies

```bash
pip install httpx loguru
```

## Usage

### Basic Usage

```python
import asyncio
from scripts.litellm_client import LiteLLMClient

async def main():
    client = LiteLLMClient()

    # Get available models
    models = await client.get_models()
    print(f"Available models: {[m['id'] for m in models]}")

    # Chat completion
    response = await client.chat_completion(
        messages=[{"role": "user", "content": "Hello!"}],
        model="gpt-5-mini",
    )
    print(response["choices"][0]["message"]["content"])

asyncio.run(main())
```

### News Analysis

```python
async def analyze():
    client = LiteLLMClient()

    news_text = "Breaking news content here..."
    analysis = await client.analyze_news(news_text, model="gpt-5.2")
    print(analysis)

asyncio.run(analyze())
```

### Available Models

The LiteLLM gateway provides access to multiple models:

- `gpt-5`, `gpt-5-mini`, `gpt-5-nano`
- `gpt-5.2`, `gpt-5.2-chat`
- `gpt-5.1-code`
- `anthropic-sonnet-4-5`
- `o3-mini`
- And more (28+ models total)

### Test Connection

```bash
python scripts/litellm_client.py
```

## API Reference

### LiteLLMClient

#### `__init__(base_url, api_key)`
Initialize the client with optional custom base URL and API key.

#### `get_models() -> List[Dict]`
Get list of available models from the gateway.

#### `chat_completion(messages, model, temperature, max_tokens, stream) -> Dict`
Create a chat completion.

Parameters:
- `messages`: List of message dictionaries `[{"role": "user", "content": "..."}]`
- `model`: Model ID (default: "gpt-4o-mini")
- `temperature`: Sampling temperature (default: 0.7)
- `max_tokens`: Maximum tokens (default: 2000)
- `stream`: Whether to stream (default: False)

#### `analyze_news(news_content, model) -> str`
Analyze news content for sentiment, topics, and key points.

## Public Opinion Research Workflow

This client was designed for researching US political news and public opinions across platforms.

### Workflow Steps

1. **Gather News**: Use WebSearch or news APIs to collect recent political news
2. **Collect Western Opinions**: Query HackerNews (Algolia API), Reddit (public JSON API)
3. **Collect Chinese Opinions**: Search for discussions on 微博, 小红书, 抖音
4. **Process Data**: Use LiteLLM to analyze and summarize collected data

### Example: Multi-Platform Opinion Analysis

```python
import asyncio
import httpx
from scripts.litellm_client import LiteLLMClient

async def research_opinions():
    client = LiteLLMClient()

    # 1. Get HackerNews stories
    async with httpx.AsyncClient() as http:
        hn_response = await http.get(
            "https://hn.algolia.com/api/v1/search",
            params={"query": "trump tariffs", "tags": "story", "hitsPerPage": 10}
        )
        hn_stories = hn_response.json().get("hits", [])

    # 2. Get Reddit posts
    async with httpx.AsyncClient() as http:
        reddit_response = await http.get(
            "https://www.reddit.com/r/politics/search.json",
            params={"q": "trump", "sort": "hot", "limit": 10},
            headers={"User-Agent": "ResearchBot/1.0"}
        )
        reddit_posts = reddit_response.json().get("data", {}).get("children", [])

    # 3. Compile and analyze
    data = f"""
    HackerNews: {[s['title'] for s in hn_stories[:5]]}
    Reddit: {[p['data']['title'] for p in reddit_posts[:5]]}
    """

    analysis = await client.chat_completion(
        messages=[
            {"role": "system", "content": "Summarize public opinion sentiment."},
            {"role": "user", "content": data}
        ],
        model="gpt-5.2"
    )

    return analysis["choices"][0]["message"]["content"]

asyncio.run(research_opinions())
```

## Troubleshooting

### "Invalid model name" Error
The gateway may not have all models. Use `get_models()` to list available models first.

### Empty Response
Some models may return empty content. Try a different model like `gpt-5.2` instead of `gpt-5-mini`.

### Connection Timeout
Increase timeout in httpx.AsyncClient: `httpx.AsyncClient(timeout=120.0)`
