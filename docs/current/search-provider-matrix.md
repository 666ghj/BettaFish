# Search provider matrix — BettaFish-localized

## Recommended order for this project

| Priority | Provider | Best for | Region fit | Key/cost posture | Notes |
|---:|---|---|---|---|---|
| 1 | SearXNG | Default no-key/local web discovery | Global, depends on upstream engines | Free/self-hosted; bundled by Docker Compose | Recommended first boot path. In Compose use `http://searxng:8080`; host/dev uses `http://localhost:8080`. |
| 2 | Naver Search API | Korean news/blog/web/local signals | Korea | Developer key required | Best Korea-first source. Use news/blog/webkr/local endpoints depending on analysis type. |
| 3 | Brave Search API | Higher-quality global web discovery | Global + Korea usable | API key required | Independent index, simple API, good opt-in upgrade from SearXNG. |
| 4 | Tavily | Agent-oriented search summaries | Global | Key required; free/dev tiers vary | Useful for LLM research flows; now routed through localized provider when selected. |
| 5 | Serper.dev | Google-style broad recall | Global | Key required | Useful when Google-like results are needed without building scraping. |
| 6 | Jina Search/Reader | Research snippets + readable pages | Global | Often easy to try; key optional/plan-dependent | Good for source extraction/reader style workflows. |
| 7 | Hacker News / GitHub | Developer and market-tech signals | Global/dev | No key for light public API use; GitHub token optional for rate limit | Safe first global-source adapters; no login scraping. |
| 8 | Reddit public/API | Public community discussion signal | Global/community | Public may 403; official API requires `REDDIT_CLIENT_ID/SECRET` | `reddit` stays no-login; `reddit-api` is stable opt-in. |
| 9 | YouTube via web search / RSS / Data API | Video/community signal | Global/media | Search/RSS no key; Data API requires `YOUTUBE_DATA_API_KEY` | `youtube-data` is official API opt-in. |
| 10 | Bluesky / Mastodon / X API | Open/social streams | Global/social | Mastodon often public; Bluesky app password optional; X requires bearer token | Explicit SNS adapters, no browser scraping. |
| Legacy | Bocha / Anspire | China-oriented AI search / multimodal cards | China | Account/access may be harder | Keep optional for users who can issue keys; not localized default. |
| Legacy | MindSpider China crawlers | Weibo/XHS/Douyin/Bilibili/Zhihu etc. | China | Login/crawler fragility/legal risk | Preserve logic, but isolate from Korea/global default source flow. |

## Source transformation plan

### MindSpider original concept

```text
hot-topic discovery
→ keyword/topic extraction
→ platform crawl
→ store in DB
→ sentiment/insight/report engines query DB
```

### Localized concept

```text
source discovery
→ provider-specific collection
   → default: SearXNG bundled in Compose
   → Korea: Naver news/blog/web, optional local portals/RSS
   → Global: Brave/Tavily/Serper/Jina
   → Developer/market: GitHub, Hacker News, Reddit/RSS, YouTube public/RSS
   → Legacy China: optional Bocha/Anspire/China social crawlers
→ same DB/analysis/report flow
```

## Decision guide

- If user wants no-key local experiments: start with `searxng`.
- If user wants Korea-first public opinion: use `naver` + RSS/manual uploads later.
- If user wants global market/tech intelligence: use `brave` + optional `tavily`/`serper`.
- If user wants readable source extraction: add `jina`.
- If user can issue China provider keys and needs China coverage: keep Bocha/Anspire/MindSpider China crawlers as opt-in, not default.

## Configuration examples

### Default Compose/no-key

```env
SEARCH_TOOL_TYPE=LocalizedAPI
SEARCH_PROVIDER=searxng
SEARXNG_BASE_URL=http://searxng:8080
SEARCH_FAIL_CLOSED=true
```

### Host/dev SearXNG

```env
SEARCH_PROVIDER=searxng
SEARXNG_BASE_URL=http://localhost:8080
```

### External provider opt-in

```env
SEARCH_PROVIDER=brave
BRAVE_SEARCH_API_KEY=

SEARCH_PROVIDER=naver
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=

SEARCH_PROVIDER=tavily
TAVILY_API_KEY=

SEARCH_PROVIDER=serper
SERPER_API_KEY=

SEARCH_PROVIDER=jina
JINA_API_KEY=
```

## Fail-closed rule

Missing keys, HTTP errors, or unavailable providers must be visible BLOCKED/FAILED states. Do not report empty analysis as success. Demo/sample data is allowed only when visibly labeled.


## MindSpider localized collection usage

Default no-key collection:

```bash
python MindSpider/BroadTopicExtraction/main.py --provider searxng --queries "AI" "market" --keywords 50
```

Korea-first collection when Naver keys are configured:

```bash
MINDSPIDER_SOURCE_PROVIDER=naver python MindSpider/BroadTopicExtraction/main.py --queries "한국 AI" "시장 여론"
```

RSS/public source collection:

```bash
python MindSpider/BroadTopicExtraction/main.py --sources rss --rss-feeds https://example.com/feed.xml
```

Global developer/community source collection:

```bash
python MindSpider/BroadTopicExtraction/main.py --sources hackernews github reddit mastodon bluesky --queries "open source ai" "local llm"
```

YouTube no-key baseline:

```bash
# Search YouTube through the configured search provider, e.g. bundled SearXNG.
python MindSpider/BroadTopicExtraction/main.py --sources youtube --queries "AI agent demo"

# Or collect stable channel feeds with explicit channel IDs.
MINDSPIDER_YOUTUBE_CHANNEL_IDS=UCxxxx,UCyyyy \
python MindSpider/BroadTopicExtraction/main.py --sources youtube-rss
```

SNS crawling policy:

```text
Stage 1: public/no-login adapters only — Reddit JSON search, RSS, HN, GitHub, YouTube via provider/RSS.
Stage 2: official APIs where available — `reddit-api`, `youtube-data`, `bluesky`, `mastodon`, `x-api`; explicit keys/quotas where required.
Stage 3: browser/session crawling only as opt-in — separate credentials, rate limits, robots/TOS review, and clear failure states.
```

Legacy China collection is explicit opt-in only:

```bash
MINDSPIDER_SOURCE_MODE=legacy_china python MindSpider/BroadTopicExtraction/main.py --sources weibo zhihu
```
