# NyayaSaar — FastAPI Backend

## Local development

```bash
# From apps/api/
# Python 3.13 is required for the pinned LangGraph/langsmith stack.
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-dev.txt

uvicorn app.main:app --reload --port 8000
```

API is now available at:
- **Health:** http://localhost:8000/api/v1/health
- **Readiness:** http://localhost:8000/api/v1/ready
- **Docs:** http://localhost:8000/docs
- **OpenAPI:** http://localhost:8000/openapi.json

## Stage 5 analysis endpoints

All require `Authorization: Bearer <token>` and case ownership.

```
POST /api/v1/cases/{case_id}/analysis                    → 202 queued workflow
GET  /api/v1/cases/{case_id}/analysis                    → recent runs
GET  /api/v1/cases/{case_id}/analysis/{workflow_id}      → status/result
POST /api/v1/cases/{case_id}/analysis/{workflow_id}/retry
GET  /api/v1/ai/status                                   → provider/model (no key)
```

Configure the provider with `AI_PROVIDER`, `AI_MODEL`, `AI_API_KEY`, and
`AI_BASE_URL`. With no key outside production, the API uses a clearly-labelled
deterministic fixture; it never claims that a model was called.

## Running tests

```bash
# From apps/api/ with venv active:
python -m pytest
```

## Environment variables

See `../../.env.example` for all available variables.
Copy it to `apps/api/.env` (the API resolves this path relative to the package,
so it works even if you start uvicorn from the repository root).

`.env` changes require an API restart: `uvicorn --reload` watches Python files,
not `.env`.

## Render deployment

- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health check path:** `/api/v1/health`
- **Root dir:** `apps/api`
- **Environment:** Set variables from `.env.example` in the Render dashboard

See `../../docs/deployment.md` for full Render setup instructions.

