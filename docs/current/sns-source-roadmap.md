# SNS / global source collection roadmap

## Position

Keep the original MindSpider analysis flow, but treat SNS/community data as explicit source adapters with risk tiers. The default product must not depend on browser/session scraping or China-specific platforms.

## Stage 1 — safe public/no-login sources (implemented)

Use sources that can be collected without user accounts, browser sessions, or anti-bot bypassing.

- `hackernews`: public Algolia HN API.
- `github`: public GitHub repository search; optional `GITHUB_TOKEN` only for rate-limit relief.
- `github-issues`: public GitHub issue search.
- `reddit`: public JSON search only; may fail closed on 403/rate limits.
- `youtube`: provider-backed web search with `site:youtube.com/watch` filter.
- `youtube-rss`: explicit channel IDs via public RSS feeds.
- `rss`: configured public feeds.

Policy: shallow discovery only, source metadata preserved, no login, no comment/thread deep-crawl unless separately approved.

## Stage 2 — official APIs / key-backed connectors (implemented as opt-in adapters)

Use when the user wants stronger or more stable SNS coverage and can provide keys.

- `bluesky`: public AT Protocol appview first; optional `BLUESKY_IDENTIFIER` + `BLUESKY_APP_PASSWORD` app-password session if public search is blocked.
- `mastodon`: public hashtag timeline / instance search; optional `MASTODON_ACCESS_TOKEN` for instances requiring authenticated search.
- `reddit-api`: official Reddit OAuth client-credentials search; requires `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET`.
- `youtube-data`: official YouTube Data API search; requires `YOUTUBE_DATA_API_KEY`.
- `x-api`: official X/Twitter API v2 recent search; requires `X_BEARER_TOKEN`.

Policy: explicit provider selection, API-key validation, quota/rate-limit reporting, fail-closed errors. Do not silently fall back to scraped pages.

## Stage 3 — browser/session crawling (approval-gated, not implemented by default)

Only for platforms where official APIs are unavailable or insufficient.

Required gates before implementation:

1. Scope: exact platforms, public pages vs logged-in pages, target volume, fields needed.
2. Compliance: robots/TOS/legal review by the user; no bypass of paywalls, captchas, or access controls.
3. Credentials: user-managed dedicated account/session only; never type or store secrets in agent memory.
4. Rate limits: slow crawl, retry/backoff, per-platform caps, kill switch.
5. Isolation: separate crawler container/profile, separate logs, clear `blocked` state on anti-bot/captcha.
6. Data hygiene: PII minimization, raw-page retention policy, provenance in every record.

Policy: opt-in module, never default. If blocked by login/captcha/403, report `blocked`; do not fake success with empty data.

## Usage examples

```bash
# Public/no-key social/community sources
python MindSpider/BroadTopicExtraction/main.py --sources mastodon hackernews github --queries "local llm" "ai agent"

# Reddit official API
REDDIT_CLIENT_ID=... REDDIT_CLIENT_SECRET=... python MindSpider/BroadTopicExtraction/main.py --sources reddit-api --queries "local llm"

# YouTube official API
YOUTUBE_DATA_API_KEY=... python MindSpider/BroadTopicExtraction/main.py --sources youtube-data --queries "AI agent demo"

# Bluesky app-password session, only if public appview is blocked
BLUESKY_IDENTIFIER=user.bsky.social BLUESKY_APP_PASSWORD=... python MindSpider/BroadTopicExtraction/main.py --sources bluesky --queries "local llm"

# X/Twitter official API
X_BEARER_TOKEN=... python MindSpider/BroadTopicExtraction/main.py --sources x-api --queries "local llm"
```

## Current verification notes

- Unit coverage verifies normalization and missing-key fail-closed behavior for all Stage 1/2 adapters.
- Real smoke passed for Mastodon public hashtag source.
- Bluesky public appview returned 403 from this environment; adapter now supports official Bluesky app-password sessions.
- Key-backed adapters are wired and tested with mocks; live API verification requires user-provided keys.
