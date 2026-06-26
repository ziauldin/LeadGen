# LeadsGen API

FastAPI backend for the LeadsGen lead-intelligence and outreach system.

## Setup

From the repo root, copy `.env.example` to `.env` and configure credentials.

```powershell
cd services\api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
```

## Run

```powershell
uvicorn app.main:app --reload --port 8000
celery -A app.core.celery_app worker -l info
```

See the root [README.md](../../README.md) for full instructions.
