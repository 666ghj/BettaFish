from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

app = FastAPI(title="SRIES BettaFish Provider Service", version="0.1.0")


# ---------
# Models (SRIES contract)
# ---------
class ProviderHealth(BaseModel):
    provider: str
    status: Literal["ok", "degraded", "down"]
    checkedAt: str
    details: Optional[Dict[str, Any]] = None


class SyncMetadata(BaseModel):
    provider: str
    lastSyncAt: Optional[str] = None
    lastSuccessAt: Optional[str] = None
    lastFailureAt: Optional[str] = None
    lastError: Optional[str] = None


class NormalizedIntelligenceRecord(BaseModel):
    provider: str
    eventId: str
    title: str
    summary: Optional[str] = None

    severity: Optional[Literal["low", "medium", "high", "critical"]] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    source: Optional[str] = None
    normalizedCategory: Optional[str] = None

    classification: Optional[Literal["internal", "external", "unknown"]] = "unknown"

    affectedEntities: Optional[List[str]] = None
    affectedAssets: Optional[List[str]] = None

    timestamp: Optional[str] = None

    recommendedActions: Optional[List[str]] = None
    complianceControls: Optional[List[str]] = None

    sriesScoreInputs: Optional[Dict[str, Any]] = None
    sriesScoreOutputs: Optional[Dict[str, Any]] = None

    raw: Optional[Dict[str, Any]] = None


class ProviderConfig(BaseModel):
    enabled: Optional[bool] = None
    polling_interval_seconds: Optional[int] = None


# ---------
# Auth
# ---------
def require_api_key(x_sries_api_key: Optional[str]) -> None:
    expected = os.getenv("SRIES_PROVIDER_API_KEY", "")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SRIES_PROVIDER_API_KEY not configured",
        )
    if not x_sries_api_key or x_sries_api_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_api_key")


# ---------
# In-memory state (scaffold)
# ---------
STATE: dict = {
    "config": {"enabled": True, "polling_interval_seconds": 300},
    "sync": {"lastSyncAt": None, "lastSuccessAt": None, "lastFailureAt": None, "lastError": None},
}


@app.get("/health", response_model=ProviderHealth)
def health(x_sries_api_key: Optional[str] = Header(default=None, alias="X-SRIES-API-KEY")) -> ProviderHealth:
    require_api_key(x_sries_api_key)
    now = datetime.now(timezone.utc).isoformat()
    return ProviderHealth(
        provider="bettafish",
        status="ok",
        checkedAt=now,
        details={"service": "sries_provider_service"},
    )


@app.get("/sync", response_model=SyncMetadata)
def sync(x_sries_api_key: Optional[str] = Header(default=None, alias="X-SRIES-API-KEY")) -> SyncMetadata:
    require_api_key(x_sries_api_key)
    return SyncMetadata(provider="bettafish", **STATE.get("sync", {}))


@app.get("/intelligence", response_model=List[NormalizedIntelligenceRecord])
def intelligence(
    x_sries_api_key: Optional[str] = Header(default=None, alias="X-SRIES-API-KEY"),
    limit: int = Query(default=100, ge=1, le=500),
    since: Optional[str] = Query(default=None, description="ISO8601 timestamp"),
) -> List[NormalizedIntelligenceRecord]:
    """
    Placeholder until we connect to BettaFish's actual detection/analysis outputs.
    For now returns [] so SRIES end-to-end wiring is testable.
    """
    require_api_key(x_sries_api_key)
    _ = limit
    _ = since
    return []


@app.post("/config")
def configure(
    cfg: ProviderConfig,
    x_sries_api_key: Optional[str] = Header(default=None, alias="X-SRIES-API-KEY"),
):
    require_api_key(x_sries_api_key)
    current = STATE.get("config", {})
    updates = {k: v for k, v in cfg.model_dump().items() if v is not None}
    STATE["config"] = {**current, **updates}
    return {"status": "ok", "config": STATE["config"]}
