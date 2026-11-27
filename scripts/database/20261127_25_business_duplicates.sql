-- Additive SNS directory storage only. No user, Telegram or queue changes.
BEGIN;
CREATE TABLE IF NOT EXISTS service_duplicate_archives (
    original_id bigint PRIMARY KEY,
    survivor_id bigint REFERENCES services(id) ON DELETE SET NULL,
    source text,
    external_id text,
    snapshot jsonb NOT NULL,
    merged_by text NOT NULL,
    reason text NOT NULL,
    archived_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source, external_id)
);
CREATE INDEX IF NOT EXISTS service_duplicate_archives_survivor_idx
    ON service_duplicate_archives(survivor_id);
COMMIT;
