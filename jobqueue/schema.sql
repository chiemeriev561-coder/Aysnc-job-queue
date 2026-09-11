--job queue schema
-- Run with: psql -U youruser -d yourdb -f schema.sql

CREATE TABLE jobs (
    id BIGSERIAL PRIMARY KEY,

    -- Identity & routing 
    job_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    

    --State & retry control 
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,
    

    --Timing  & saftey
    run_at TIMESTAMP NOT NULL DEFAULT NOW(),
    locked_at TIMESTAMP NULL,

    --Failure tracking 
    last_error TEXT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Speeds up the worker's "find me eligible pending job" query
--Only indexes pending rows, not the full history of completed/failed jobs.
CREATE INDEX idx_jobs_status_run_at ON jobs (run_at) WHERE status = 'pending';