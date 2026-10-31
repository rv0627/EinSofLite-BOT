# Ein Sof Lite

> Modular Multi-bot investment intelligence system (FastAPI + Celery + TimescaleDB)

## Overview

Ein Sof Lite is a modular data-engine and API that pulls End-Of-Day (EOD) market data, stores raw payloads, and exposes a simple HTTP API to trigger background tasks. It uses FastAPI for the web API, Celery + Redis for background tasks, and TimescaleDB/Postgres for persistent storage. Alembic is used for database migrations.

## Features
- FastAPI HTTP endpoints ([src/main.py](src/main.py))
- Asynchronous background tasks using Celery ([src/workers/tasks.py](src/workers/tasks.py))
- Timescale/Postgres storage and Alembic migrations (see `alembic/`)
- Docker Compose for local multi-service development

## Requirements
- Python 3.10+ (or a compatible 3.x)
- Docker & Docker Compose (for containerized quick-start)
- Local Postgres/TimescaleDB and Redis (or use Docker Compose)

## Environment variables
- `DATABASE_URL` — SQLAlchemy database URL (example: `postgresql://postgres:password@localhost:5432/einsoflite`)
- `REDIS_URL` — Redis URL used by Celery (example: `redis://localhost:6379/0`)
- `TWELVE_DATA_API_KEY` — API key for the Twelve Data adapter

Example `.env` (copy to repository root as `.env`):

```
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=einsoflite
DATABASE_URL=postgresql://postgres:password@localhost:5432/einsoflite
REDIS_URL=redis://localhost:6379/0
TWELVE_DATA_API_KEY=your_api_key_here
```

## Quick start (Docker Compose)
This repository includes `docker-compose.yml` with services for the database, Redis, FastAPI webserver, and Celery worker/beat.

1. Build and start services:

```
docker-compose up --build -d
```

2. Apply database migrations (inside the `web` container or locally):

```
docker-compose exec web alembic upgrade head
```

3. Open the API at `http://localhost:8001` (mapped in compose)

## Local development (without Docker)

1. Create and activate a virtualenv:

Windows (PowerShell):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. Install dependencies:

```
pip install -r requirements.txt
```

3. Run Alembic migrations:

```
alembic upgrade head
```

4. Run the FastAPI app:

```
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

5. Run Celery worker and beat (in separate terminals):

```
celery -A src.workers.tasks.celery_app worker --loglevel=info
celery -A src.workers.tasks.celery_app beat --loglevel=info
```

## API
- Health check: `GET /` — implemented in [src/main.py](src/main.py)
- Trigger Bot1 EOD: `POST /trigger/bot1/eod` — triggers the `pull_eod_data` Celery task

## Database migrations
- Migrations live in the `alembic/` folder. Use Alembic commands to create and apply revisions.

## Project structure

- `src/` — application source
  - `main.py` — FastAPI app entrypoint
  - `adapters/` — external service adapters (e.g., Twelve Data)
  - `api/`, `core/`, `domain/`, `repositories/`, `services/` — modular structure
  - `workers/` — Celery tasks and worker setup

## Contributing
- Open issues and pull requests. Keep changes focused and add tests where applicable.

## License
This repository does not specify a license. Add a `LICENSE` file to clarify terms.
