"""
Integration test suite for Async Job Queue
Tests:
1. Job insertion via API logic
2. Job retrieval via API logic
3. Worker claim logic (FOR UPDATE SKIP LOCKED)
4. Successful job execution by handler
5. Permanent failure for unregistered job type
6. Retry handling on exception
"""

import sys
import psycopg
from psycopg.rows import dict_row

from config import DB_DSN
from worker import claim_next_job
from run_worker import run_one_job
from handlers import register


def setup_clean_table():
    with psycopg.connect(DB_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM jobs;")
        conn.commit()


def test_enqueue_and_get():
    print("[TEST 1] Enqueueing job via API logic...")
    from api import enqueue_job, get_job, JobCreate

    req = JobCreate(job_type="generate_weekly_report", payload={"manager_id": 42, "format": "pdf"})
    result = enqueue_job(req)
    job_id = result["id"]
    assert result["status"] == "pending", f"Expected status 'pending', got {result['status']}"
    print(f"  Enqueued job id: {job_id}")

    job_data = get_job(job_id)
    assert job_data["id"] == job_id
    assert job_data["job_type"] == "generate_weekly_report"
    assert job_data["payload"] == {"manager_id": 42, "format": "pdf"}
    assert job_data["status"] == "pending"
    print("  Job retrieved successfully with matching payload!")
    return job_id


def test_claim_and_execute(job_id):
    print("[TEST 2] Claiming and executing job...")
    with psycopg.connect(DB_DSN, row_factory=dict_row) as conn:
        job = claim_next_job(conn)
        conn.commit()

        assert job is not None, "Failed to claim eligible pending job"
        assert job["id"] == job_id
        print(f"  Claimed job {job['id']}, status set to 'processing'")

        run_one_job(conn, job)

    from api import get_job
    updated_job = get_job(job_id)
    assert updated_job["status"] == "completed", f"Expected 'completed', got {updated_job['status']}"
    print("  Job marked as 'completed' successfully!")


def test_unknown_handler():
    print("[TEST 3] Testing unrecoverable failure for unknown job type...")
    from api import enqueue_job, get_job, JobCreate

    req = JobCreate(job_type="unknown_action_type", payload={"foo": "bar"})
    job_info = enqueue_job(req)
    job_id = job_info["id"]

    with psycopg.connect(DB_DSN, row_factory=dict_row) as conn:
        job = claim_next_job(conn)
        conn.commit()
        assert job is not None
        run_one_job(conn, job)

    failed_job = get_job(job_id)
    assert failed_job["status"] == "failed"
    assert "No handler registered" in failed_job["last_error"]
    print("  Unregistered job immediately marked permanently 'failed' as expected!")


def test_retry_on_exception():
    print("[TEST 4] Testing retry mechanism on handler failure...")
    
    @register("flaky_job")
    def flaky_handler(payload):
        raise ValueError("Simulated network outage")

    from api import enqueue_job, get_job, JobCreate

    req = JobCreate(job_type="flaky_job", payload={"test": True})
    job_info = enqueue_job(req)
    job_id = job_info["id"]

    with psycopg.connect(DB_DSN, row_factory=dict_row) as conn:
        job = claim_next_job(conn)
        conn.commit()
        run_one_job(conn, job)

    retrying_job = get_job(job_id)
    assert retrying_job["status"] == "pending", f"Expected status 'pending' for retry, got {retrying_job['status']}"
    assert retrying_job["attempts"] == 1
    assert "Simulated network outage" in retrying_job["last_error"]
    print(f"  Job correctly scheduled for retry (attempts={retrying_job['attempts']}, status='{retrying_job['status']}')!")


if __name__ == "__main__":
    setup_clean_table()
    job_id = test_enqueue_and_get()
    test_claim_and_execute(job_id)
    test_unknown_handler()
    test_retry_on_exception()
    print("\nALL TESTS PASSED SUCCESSFULLY! \u2705")
