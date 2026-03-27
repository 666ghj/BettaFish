# SRIES BettaFish Provider Service

Minimal FastAPI wrapper exposing SRIES provider endpoints:

- `GET /health`
- `GET /sync`
- `GET /intelligence`
- `POST /config`

All endpoints require:
- Header: `X-SRIES-API-KEY: <key>`
- Env var: `SRIES_PROVIDER_API_KEY=<key>`

## Run (port 5000)
```bash
cd sries_provider_service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export SRIES_PROVIDER_API_KEY="change-me"
uvicorn main:app --reload --host 0.0.0.0 --port 5000
```

## Test
```bash
curl -s http://localhost:5000/health -H "X-SRIES-API-KEY: change-me"
curl -s http://localhost:5000/sync -H "X-SRIES-API-KEY: change-me"
curl -s "http://localhost:5000/intelligence?limit=50" -H "X-SRIES-API-KEY: change-me"
curl -s -X POST http://localhost:5000/config \
  -H "content-type: application/json" \
  -H "X-SRIES-API-KEY: change-me" \
  -d '{"enabled": true, "polling_interval_seconds": 300}'
```

## SRIES backend env
In SRIES backend `.env`:

- `BETTAFISH_BASE_URL=http://localhost:5000`
- `BETTAFISH_API_KEY=change-me`

SRIES backend will send:
- `X-SRIES-API-KEY: ${BETTAFISH_API_KEY}`
