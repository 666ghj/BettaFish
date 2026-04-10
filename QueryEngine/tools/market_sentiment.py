"""
Optional structured market sentiment research tools powered by Adanos.

The QueryEngine consumes external tools through a news-like result interface.
This module adapts Adanos stock and market sentiment data into that shape so the
existing summary/report nodes can reuse it without special handling.
"""

from __future__ import annotations

import os
import re
import sys
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional

import requests

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
utils_dir = os.path.join(root_dir, "utils")
if utils_dir not in sys.path:
    sys.path.append(utils_dir)

from retry_helper import SEARCH_API_RETRY_CONFIG, with_graceful_retry

from .search import SearchResult, TavilyResponse


class AdanosSentimentAgency:
    """Optional adapter around the Adanos Market Sentiment API."""

    _BASE_URL = "https://api.adanos.org"
    _DOCS_URL = "https://api.adanos.org/docs"
    _SOURCES = ("news", "reddit", "x", "polymarket")

    def __init__(self, api_key: Optional[str] = None):
        api_key = api_key or os.getenv("ADANOS_API_KEY")
        if not api_key:
            raise ValueError("Adanos API Key未找到！请设置ADANOS_API_KEY环境变量或在初始化时提供")

        self._api_key = api_key
        self._session = requests.Session()

    def search_market_sentiment(self, query: str, days: int = 7) -> TavilyResponse:
        """
        Return stock-specific or market-wide sentiment as SearchResult-like items.

        If the query contains explicit tickers (AAPL, $TSLA, BRK.A), the tool returns
        a cross-source stock snapshot and source-level breakdown. Otherwise it returns
        service-level market sentiment across the supported sources.
        """
        tickers = self._extract_tickers(query)
        if tickers:
            return self._search_stock_sentiment(query=query, tickers=tickers[:3], days=days)
        return self._search_market_overview(query=query, days=days)

    @with_graceful_retry(SEARCH_API_RETRY_CONFIG, default_return=None)
    def _request_json(self, path: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        response = self._session.get(
            f"{self._BASE_URL}{path}",
            params=params,
            headers={"X-API-Key": self._api_key},
            timeout=20,
        )

        if response.status_code == 404:
            return None

        response.raise_for_status()
        return response.json()

    def _search_stock_sentiment(self, query: str, tickers: List[str], days: int) -> TavilyResponse:
        results: List[SearchResult] = []

        for ticker in tickers:
            snapshots: Dict[str, Dict[str, Any]] = {}
            for source in self._SOURCES:
                payload = self._request_json(f"/{source}/stocks/v1/stock/{ticker}", {"days": days})
                if payload and payload.get("found"):
                    snapshots[source] = payload

            if not snapshots:
                continue

            results.append(self._build_stock_overview_result(ticker, snapshots, days))
            for source, payload in snapshots.items():
                results.append(self._build_stock_source_result(ticker, source, payload, days))

        answer = (
            f"Found structured Adanos sentiment coverage for {', '.join(tickers)}."
            if results
            else "No Adanos sentiment data found for the requested ticker(s)."
        )
        return TavilyResponse(query=query, answer=answer, results=results)

    def _search_market_overview(self, query: str, days: int) -> TavilyResponse:
        snapshots: Dict[str, Dict[str, Any]] = {}
        for source in self._SOURCES:
            payload = self._request_json(f"/{source}/stocks/v1/market-sentiment", {"days": days})
            if payload:
                snapshots[source] = payload

        if not snapshots:
            return TavilyResponse(
                query=query,
                answer="No Adanos market-wide sentiment sources were available.",
                results=[],
            )

        results = [self._build_market_overview_result(snapshots, days)]
        results.extend(
            self._build_market_source_result(source=source, payload=payload, days=days)
            for source, payload in snapshots.items()
        )

        return TavilyResponse(
            query=query,
            answer="Structured cross-source market sentiment snapshot retrieved from Adanos.",
            results=results,
        )

    def _build_stock_overview_result(
        self, ticker: str, snapshots: Dict[str, Dict[str, Any]], days: int
    ) -> SearchResult:
        buzz_values = [payload.get("buzz_score") for payload in snapshots.values() if payload.get("buzz_score") is not None]
        bullish_values = [
            payload.get("bullish_pct") for payload in snapshots.values() if payload.get("bullish_pct") is not None
        ]
        sentiment_values = [
            payload.get("sentiment_score") for payload in snapshots.values() if payload.get("sentiment_score") is not None
        ]

        lines = [
            f"Ticker: {ticker}",
            f"Lookback window: {days} days",
            f"Sources with signal: {', '.join(source.upper() for source in snapshots.keys())}",
            f"Average buzz score: {mean(buzz_values):.1f}" if buzz_values else "Average buzz score: unavailable",
            (
                f"Average bullish percentage: {mean(bullish_values):.1f}%"
                if bullish_values
                else "Average bullish percentage: unavailable"
            ),
            self._format_alignment(sentiment_values),
            "Source snapshots:",
        ]
        for source, payload in snapshots.items():
            lines.append(
                f"- {source.upper()}: buzz {self._format_number(payload.get('buzz_score'))}, "
                f"bullish {self._format_percent(payload.get('bullish_pct'))}, "
                f"sentiment {self._format_number(payload.get('sentiment_score'))}, "
                f"activity {self._format_activity(payload)}"
            )

        return SearchResult(
            title=f"{ticker} cross-source market sentiment snapshot",
            url=self._DOCS_URL,
            content="\n".join(lines),
            score=float(mean(buzz_values)) if buzz_values else None,
        )

    def _build_stock_source_result(
        self, ticker: str, source: str, payload: Dict[str, Any], days: int
    ) -> SearchResult:
        lines = [
            f"Ticker: {ticker}",
            f"Source: {source.upper()}",
            f"Lookback window: {days} days",
            f"Buzz score: {self._format_number(payload.get('buzz_score'))}",
            f"Sentiment score: {self._format_number(payload.get('sentiment_score'))}",
            f"Bullish percentage: {self._format_percent(payload.get('bullish_pct'))}",
            f"Trend: {payload.get('trend') or 'unknown'}",
            f"Activity: {self._format_activity(payload)}",
        ]

        return SearchResult(
            title=f"{ticker} {source.upper()} sentiment details",
            url=f"{self._BASE_URL}/{source}/stocks/v1/stock/{ticker}?days={days}",
            content="\n".join(lines),
            score=payload.get("buzz_score"),
        )

    def _build_market_overview_result(
        self, snapshots: Dict[str, Dict[str, Any]], days: int
    ) -> SearchResult:
        buzz_values = [payload.get("buzz_score") for payload in snapshots.values() if payload.get("buzz_score") is not None]
        bullish_values = [
            payload.get("bullish_pct") for payload in snapshots.values() if payload.get("bullish_pct") is not None
        ]
        sentiment_values = [
            payload.get("sentiment_score") for payload in snapshots.values() if payload.get("sentiment_score") is not None
        ]

        lines = [
            f"Lookback window: {days} days",
            f"Covered sources: {', '.join(source.upper() for source in snapshots.keys())}",
            f"Average market buzz score: {mean(buzz_values):.1f}" if buzz_values else "Average market buzz score: unavailable",
            (
                f"Average bullish percentage: {mean(bullish_values):.1f}%"
                if bullish_values
                else "Average bullish percentage: unavailable"
            ),
            self._format_alignment(sentiment_values),
            "Top drivers by source:",
        ]

        for source, payload in snapshots.items():
            drivers = payload.get("drivers") or []
            if drivers:
                top_driver = drivers[0]
                driver_text = (
                    f"{top_driver.get('ticker')} (buzz {self._format_number(top_driver.get('buzz_score'))}, "
                    f"sentiment {self._format_number(top_driver.get('sentiment_score'))})"
                )
            else:
                driver_text = "no driver data"
            lines.append(f"- {source.upper()}: {driver_text}")

        return SearchResult(
            title="Cross-source US market sentiment overview",
            url=self._DOCS_URL,
            content="\n".join(lines),
            score=float(mean(buzz_values)) if buzz_values else None,
        )

    def _build_market_source_result(self, source: str, payload: Dict[str, Any], days: int) -> SearchResult:
        lines = [
            f"Source: {source.upper()}",
            f"Lookback window: {days} days",
            f"Buzz score: {self._format_number(payload.get('buzz_score'))}",
            f"Sentiment score: {self._format_number(payload.get('sentiment_score'))}",
            f"Bullish percentage: {self._format_percent(payload.get('bullish_pct'))}",
            f"Trend: {payload.get('trend') or 'unknown'}",
            f"Activity breadth: {self._format_market_activity(payload)}",
        ]
        drivers = payload.get("drivers") or []
        if drivers:
            lines.append("Top drivers:")
            for driver in drivers[:3]:
                lines.append(
                    f"- {driver.get('ticker')}: buzz {self._format_number(driver.get('buzz_score'))}, "
                    f"sentiment {self._format_number(driver.get('sentiment_score'))}"
                )

        return SearchResult(
            title=f"{source.upper()} market sentiment overview",
            url=f"{self._BASE_URL}/{source}/stocks/v1/market-sentiment?days={days}",
            content="\n".join(lines),
            score=payload.get("buzz_score"),
        )

    @staticmethod
    def _extract_tickers(query: str) -> List[str]:
        candidates = re.findall(r"\$?[A-Za-z]{1,5}(?:\.[A-Za-z])?\b", query)
        seen = set()
        tickers = []
        for raw_candidate in candidates:
            candidate = raw_candidate.lstrip("$")
            if "$" not in raw_candidate and candidate.upper() != raw_candidate:
                continue
            candidate = candidate.upper()
            if candidate in {"A", "AN", "AND", "FOR", "WITH", "THE", "USA", "NEWS", "STOCK"}:
                continue
            if candidate not in seen:
                seen.add(candidate)
                tickers.append(candidate)
        return tickers

    @staticmethod
    def _format_alignment(sentiment_values: Iterable[Optional[float]]) -> str:
        numeric_values = [float(value) for value in sentiment_values if value is not None]
        if len(numeric_values) < 2:
            return "Cross-source alignment: insufficient signal"
        spread = max(numeric_values) - min(numeric_values)
        if spread < 0.15:
            label = "strongly aligned"
        elif spread < 0.35:
            label = "moderately aligned"
        else:
            label = "divergent"
        return f"Cross-source alignment: {label}"

    @staticmethod
    def _format_market_activity(payload: Dict[str, Any]) -> str:
        if "mentions" in payload:
            return f"{payload.get('mentions', 0)} mentions across {payload.get('active_tickers', 0)} active tickers"
        if "trade_count" in payload:
            return f"{payload.get('trade_count', 0)} trades across {payload.get('active_tickers', 0)} active tickers"
        return "activity unavailable"

    @staticmethod
    def _format_activity(payload: Dict[str, Any]) -> str:
        if payload.get("mentions") is not None:
            return f"{int(payload.get('mentions', 0))} mentions"
        if payload.get("trade_count") is not None:
            return f"{int(payload.get('trade_count', 0))} trades"
        if payload.get("unique_tweets") is not None:
            return f"{int(payload.get('unique_tweets', 0))} tweets"
        return "unavailable"

    @staticmethod
    def _format_number(value: Any) -> str:
        if value is None:
            return "unavailable"
        return f"{float(value):.2f}"

    @staticmethod
    def _format_percent(value: Any) -> str:
        if value is None:
            return "unavailable"
        return f"{float(value):.0f}%"
