# NyayaSaar — FastAPI Backend

## Local development

```bash
# From apps/api/
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

## Running tests

```bash
# From apps/api/ with venv active:
python -m pytest
```

## Environment variables

See `../../.env.example` for all available variables.
Copy it to `../../.env` and fill in values.

## Render deployment

- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health check path:** `/api/v1/health`
- **Root dir:** `apps/api`
- **Environment:** Set variables from `.env.example` in the Render dashboard

See `../../docs/deployment.md` for full Render setup instructions.

