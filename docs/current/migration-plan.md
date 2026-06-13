# BettaFish-localized migration plan

## Goal

Create a Korea/global-friendly BettaFish fork that preserves the original report/intelligence concept while replacing China-centric or hard-to-use providers with configurable local/global providers.

## Phase 1 — baseline and audit ✅

- Create `/Users/crimson/Projects/bettafish-localized` from original `/Users/crimson/Research/BettaFish`.
- Preserve upstream code and remote.
- Add localized architecture/search-provider docs.
- Add provider-router scaffold.
- Keep legacy China providers optional.

## Phase 2 — Compose-first default search ✅

- Bundle SearXNG in Docker Compose.
- Make `SEARCH_PROVIDER=searxng` the no-key default.
- Keep app-in-container URL as `http://searxng:8080` and host/dev URL as `http://localhost:8080`.
- Keep external-key providers explicit opt-in.

## Phase 3 — search/source integration in progress

- Route QueryEngine/MediaEngine web search through `localized_search` first.
- Keep Tavily/Bocha/Anspire adapters as compatible provider implementations.
- Add explicit fail-closed behavior for missing keys/provider failures.
- Add sample-data only as a visibly labeled demo mode if needed later.

## Phase 4 — MindSpider source transform ✅ first slice wired

- Keep original China platform crawler logic isolated as legacy opt-in.
- Add source provider layer for Korea/global discovery.
- Wire BroadTopicExtraction daily source collection to localized providers.
- Start with SearXNG default and support Naver/Brave/Tavily/Serper/Jina by config.
- Add RSS provider for public news/community feeds without login scraping.
- Later add GitHub/Hacker News/Reddit/YouTube source adapters as separate global/social modules.

## Phase 5 — Docker runtime verification next

- Validate `docker compose config`.
- Run `docker compose up -d searxng` and query `/search?format=json` when Docker runtime is available.
- Run app + DB + SearXNG smoke once environment secrets for LLMs/DB are set.

## Phase 6 — report and GraphRAG improvements later

- Decide whether Graphiti/Neo4j is useful as a local evidence graph for collected topics/entities.
- If added, it must be fail-closed and session/group separated.
