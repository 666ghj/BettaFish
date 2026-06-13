# Architecture — BettaFish-localized

## Current direction

BettaFish-localized keeps the original BettaFish concept — public-opinion / issue discovery → multi-engine analysis → report generation — but moves source/search dependencies behind localized adapters.

```text
Input / issue seed
→ source/search providers
   → bundled local SearXNG default
   → optional global/Korean search APIs
   → optional legacy China sources
   → local database / uploaded materials
→ analysis engines
→ report engine
→ HTML / Markdown / PDF output
```

## Provider policy

- Default no-key Docker Compose path: `SEARCH_TOOL_TYPE=LocalizedAPI`, `SEARCH_PROVIDER=searxng`, `SEARXNG_BASE_URL=http://searxng:8080`.
- Host/dev SearXNG URL: `SEARXNG_BASE_URL=http://localhost:8080`.
- Korea-first path: `SEARCH_PROVIDER=naver` for Korean news/blog/web coverage; requires Naver credentials.
- Higher-quality global path: `brave`, `tavily`, `serper`, or `jina`; each is explicit opt-in and key/config dependent.
- Legacy China-oriented paths: `anspire`, `bocha`, and MindSpider China platform crawlers remain upstream-compatible but are not localized defaults.

## Fail-closed policy

Search/provider failures must not be silently converted into successful empty analysis.

- Missing API key: explicit BLOCKED/FAILED.
- Provider HTTP failure: explicit BLOCKED/FAILED unless the user enabled a clearly labeled demo/mock mode.
- Legacy China source unavailable: mark source unavailable; do not report it as collected.
- No automatic fallback chain is enabled by default. If a provider chain is added later, record `source_provider` and `fallback_used` per result.

## Implemented slice

A lightweight `localized_search` provider router exists for:

- SearXNG — default bundled no-key provider
- Brave Search API
- Naver Search API
- Tavily
- Serper.dev
- Jina Search

`QueryEngine` and `MediaEngine` can initialize `LocalizedSearchClient`; standalone Streamlit paths now allow `LocalizedAPI` instead of forcing only Tavily/Bocha/Anspire search.

## MindSpider source transformation

The original MindSpider workflow is preserved conceptually:

```text
hot-topic/source discovery
→ topic/keyword extraction
→ source collection
→ DB storage
→ sentiment/insight/report engines
```

Localized shape:

```text
source discovery
→ default: SearXNG
→ Korea: Naver Search / RSS / portal sources later
→ Global: Brave / Tavily / Serper / Jina
→ Developer/market: GitHub / Hacker News / Reddit / YouTube public/RSS
→ Legacy China: Weibo / Zhihu / Bilibili / Douyin / Tieba / XHS opt-in only
→ same DB/analysis/report flow
```

The first scaffold is now wired into `MindSpider/BroadTopicExtraction/get_today_news.py`:

- default `MINDSPIDER_SOURCE_MODE=localized` collects via `MINDSPIDER_SOURCE_PROVIDER=searxng`;
- `--provider naver|brave|tavily|serper|jina` or env config switches provider without changing downstream analysis;
- `--sources rss --rss-feeds <url...>` or `MINDSPIDER_RSS_FEEDS=` adds public RSS sources;
- `--sources hackernews github github-issues reddit reddit-api youtube youtube-data youtube-rss bluesky mastodon x-api` adds global developer/community/media/SNS signals without browser scraping;
- China hot-list IDs such as `weibo`, `zhihu`, `douyin`, `xhs`, `bili`, `tieba` are blocked unless `MINDSPIDER_SOURCE_MODE=legacy_china` is explicitly selected.

The collector still feeds the existing `daily_news → topic extraction → daily_topics → deep sentiment crawling keywords` flow, so the original MindSpider logic is preserved while the source layer is no longer China-fixed by default.
