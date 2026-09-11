"""
Producer side: a small FastAPI app that lets other code enqueue jobs.

This is intentionally dumb — it doesn't know what a "generate_weekly_report"
job does, it just inserts a row. That logic lives in the handler registry,
which the WORKER owns, not the API.
"""

from datetime import datetime, timezone
from typing import Any, Optional

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config import DB_DSN

app = FastAPI()


class JobCreate(BaseModel):
    job_type: str
    payload: dict[str, Any] = {}
    run_at: Optional[datetime] = None  # defaults to "now" if not given


@app.post("/jobs", status_code=201)
def enqueue_job(job: JobCreate):
    run_at = job.run_at or datetime.now(timezone.utc)

    with psycopg.connect(DB_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (job_type, payload, run_at)
                VALUES (%s, %s, %s)
                RETURNING id, status, run_at
                """,
                (job.job_type, psycopg.types.json.Json(job.payload), run_at),
            )
            row = cur.fetchone()
        conn.commit()

    if row is None:
        raise HTTPException(status_code=500, detail="Failed to enqueue job")

    return {"id": row[0], "status": row[1], "run_at": row[2]}


@app.get("/jobs/{job_id}")
def get_job(job_id: int):
    with psycopg.connect(DB_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, job_type, payload, status, attempts, max_attempts,
                       run_at, last_error, created_at
                FROM jobs
                WHERE id = %s
                """,
                (job_id,),
            )
            row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")

    columns = ["id", "job_type", "payload", "status", "attempts", "max_attempts",
               "run_at", "last_error", "created_at"]
    return dict(zip(columns, row))