"""
The worker's main loop: claim a job, run its handler, record the outcome.

Run this as its own process: `python run_worker.py`
You can run MULTIPLE copies of this process at once — that's the whole
point of FOR UPDATE SKIP LOCKED, they won't collide.
"""

import time
import traceback

import psycopg
from psycopg.rows import dict_row

from handlers import HANDLERS
from worker import claim_next_job

DB_DSN = "postgresql://user:password@localhost:5432/yourdb"  # replace with real config
POLL_INTERVAL_SECONDS = 5
RETRY_DELAY_MINUTES = 60  # matches the "retry after 1 hour" decision


def mark_completed(conn: psycopg.Connection, job_id: int):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE jobs SET status = 'completed' WHERE id = %s",
            (job_id,),
        )
    conn.commit()


def mark_permanently_failed(conn: psycopg.Connection, job: dict, error: str):
    """
    For failures that retrying can NEVER fix (e.g. no handler registered
    for this job_type — a typo isn't going to un-typo itself in an hour).
    Skips the attempts/max_attempts math entirely and fails immediately.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE jobs
            SET status = 'failed', attempts = attempts + 1, last_error = %s
            WHERE id = %s
            """,
            (error, job["id"]),
        )
    conn.commit()
    # TODO: this is where you'd trigger an alert (email/Slack/etc)
    print(f"Job {job['id']} permanently failed (unrecoverable): {error}")


def mark_failed_or_retry(conn: psycopg.Connection, job: dict, error: str):
    """
    If attempts is still under max_attempts, bump attempts and push
    run_at into the future so it gets picked up again later.
    Otherwise mark it permanently 'failed'.
    """
    new_attempts = job["attempts"] + 1

    with conn.cursor() as cur:
        if new_attempts >= job["max_attempts"]:
            cur.execute(
                """
                UPDATE jobs
                SET status = 'failed', attempts = %s, last_error = %s
                WHERE id = %s
                """,
                (new_attempts, error, job["id"]),
            )
            # TODO: this is where you'd trigger an alert (email/Slack/etc)
            print(f"Job {job['id']} permanently failed after {new_attempts} attempts")
        else:
            cur.execute(
                """
                UPDATE jobs
                SET status = 'pending',
                    attempts = %s,
                    last_error = %s,
                    run_at = NOW() + (%s || ' minutes')::interval
                WHERE id = %s
                """,
                (new_attempts, error, RETRY_DELAY_MINUTES, job["id"]),
            )
    conn.commit()


def run_one_job(conn: psycopg.Connection, job: dict):
    handler = HANDLERS.get(job["job_type"])

    if handler is None:
        # Unrecoverable — no amount of retrying makes a handler appear.
        mark_permanently_failed(conn, job, f"No handler registered for '{job['job_type']}'")
        return

    try:
        handler(job["payload"])
    except Exception:
        mark_failed_or_retry(conn, job, traceback.format_exc())
    else:
        mark_completed(conn, job["id"])


def worker_loop():
    print("Worker started, polling for jobs...")
    while True:
        with psycopg.connect(DB_DSN, row_factory=dict_row) as conn:
            job = claim_next_job(conn)
            conn.commit()  # releases the FOR UPDATE lock, confirms the claim

            if job is None:
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            print(f"Claimed job {job['id']} ({job['job_type']})")
            run_one_job(conn, job)


if __name__ == "__main__":
    worker_loop()