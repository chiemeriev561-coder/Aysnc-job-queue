-- job queue schema
-- Run with: psql -U youruser -d yourdb -f schema.sql

CREATE TABLE IF NOT EXISTS jobs (
    id BIGSERIAL PRIMARY KEY,

    -- Identity & routing
    job_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- State & retry control
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,

    -- Timing & safety (use TIMESTAMPTZ for timezone consistency)
    run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    locked_at TIMESTAMPTZ NULL,

    -- Failure tracking
    last_error TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT jobs_status_check CHECK (status IN ('pending', 'processing', 'completed', 'failed'))
);

-- Speeds up the worker's "find me eligible pending job" query
-- Only indexes pending rows, not the full history of completed/failed jobs.
CREATE INDEX IF NOT EXISTS idx_jobs_status_run_at ON jobs (run_at) WHERE status = 'pending';