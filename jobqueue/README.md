# Async Job Queue

A minimal PostgreSQL-backed job queue with:

- A FastAPI producer for enqueueing and inspecting jobs.
- One or more workers that claim and execute jobs.
- PostgreSQL row locking with `FOR UPDATE SKIP LOCKED` so workers do not process the same job.
- Retry handling for failed jobs.

## Requirements

- Python 3.10+
- PostgreSQL

## Setup

From this directory:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

Create the queue table in PostgreSQL:

```sql
CREATE TABLE jobs (
    id BIGSERIAL PRIMARY KEY,
    job_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    locked_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT jobs_status_check CHECK (status IN ('pending', 'processing', 'completed', 'failed'))
);

CREATE INDEX jobs_pending_run_at_idx
    ON jobs (run_at)
    WHERE status = 'pending';
```

Update `DB_DSN` in both `api.py` and `run_worker.py` with your PostgreSQL connection string. For example:

```python
DB_DSN = "postgresql://user:password@localhost:5432/yourdb"
```

## Run the API

```bash
source venv/bin/activate
uvicorn api:app --reload
```

The API is available at `http://127.0.0.1:8000`. Interactive documentation is available at `/docs`.

## Run a worker

In another terminal:

```bash
source venv/bin/activate
python run_worker.py
```

Multiple worker processes can run at the same time. Each worker polls every five seconds and claims an available pending job.

## API usage

Enqueue a job:

```bash
curl -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"job_type":"generate_weekly_report","payload":{"manager_id":42,"format":"pdf"}}'
```

Run a job later by supplying an ISO 8601 `run_at` value:

```json
{
  "job_type": "generate_weekly_report",
  "payload": {"manager_id": 42},
  "run_at": "2026-09-09T09:00:00Z"
}
```

Inspect a job:

```bash
curl http://127.0.0.1:8000/jobs/1
```

## Adding handlers

Register a function in `handlers.py` using the job type that producers will submit:

```python
@register("send_invoice")
def send_invoice(payload: dict):
    invoice_id = payload["invoice_id"]
    # Perform the work here.
```

An unknown job type is marked `failed` immediately. Handler exceptions are retried until `max_attempts` is reached; retries are delayed by 60 minutes in `run_worker.py`.

## Project files

| File | Purpose |
| --- | --- |
| `api.py` | FastAPI endpoints for creating and reading jobs |
| `worker.py` | Atomic job claiming logic |
| `run_worker.py` | Worker polling loop and retry handling |
| `handlers.py` | Job handler registry and example handler |
| `requirements.txt` | Python dependencies |

