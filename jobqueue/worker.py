"""
Minimal Postgres-backed job queue worker.

Core idea: `claim_next_job` does the SELECT + lock + UPDATE as ONE
transaction, so two workers running this at the same time can never
grab the same row. That's the FOR UPDATE SKIP LOCKED pattern we
walked through.
"""

import psycopg
from psycopg.rows import dict_row

STALE_JOB_TIMEOUT_MINUTES = 15


def claim_next_job(conn: psycopg.Connection) -> dict | None:
    """
    Atomically find one eligible job, lock it, and mark it 'processing'.
    Returns the job row as a dict, or None if nothing is eligible.

    Must be called inside a transaction that you COMMIT after —
    the lock from FOR UPDATE is only held until commit/rollback.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            WITH expired_job AS (
                SELECT id
                FROM jobs
                WHERE status = 'processing'
                  AND locked_at <= NOW() - (%s * INTERVAL '1 minute')
                ORDER BY locked_at
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            UPDATE jobs
            SET status = CASE
                    WHEN jobs.attempts + 1 >= jobs.max_attempts THEN 'failed'
                    ELSE 'pending'
                END,
                attempts = jobs.attempts + 1,
                locked_at = NULL,
                last_error = %s,
                run_at = NOW()
            FROM expired_job
            WHERE jobs.id = expired_job.id
            """,
            (
                STALE_JOB_TIMEOUT_MINUTES,
                f"Worker lease expired after {STALE_JOB_TIMEOUT_MINUTES} minutes",
            ),
        )
        cur.execute(
            """
            SELECT id, job_type, payload, attempts, max_attempts
            FROM jobs
            WHERE status = 'pending' AND run_at <= NOW()
            ORDER BY run_at
            LIMIT 1
            FOR UPDATE SKIP LOCKED
            """
        )
        job = cur.fetchone()

        if job is None:
            return None  # nothing to do right now

        # Still inside the SAME transaction as the SELECT above —
        # this is what makes "claiming" atomic. No other worker
        # can see this row as 'pending' anymore once we commit.
        cur.execute(
            """
            UPDATE jobs
            SET status = 'processing', locked_at = NOW()
            WHERE id = %s
            """,
            (job["id"],),
        )

    return job