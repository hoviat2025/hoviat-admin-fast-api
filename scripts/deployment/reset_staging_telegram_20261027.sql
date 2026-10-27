-- Staging clone only. Stop the staging backend/queue workers and take a backup
-- before running with psql -X -v ON_ERROR_STOP=1 against the local 18/main socket.
-- Connect as hoviat_sns_stage, or postgres with role=hoviat_sns_stage.
-- This script never contacts Telegram. Output contains aggregate counts only.
\set ON_ERROR_STOP on

BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '120s';
SET LOCAL search_path = pg_catalog, public;

DO $guard$
BEGIN
    IF current_database() <> 'hoviat_sns_stage_20261021'
       OR current_user <> 'hoviat_sns_stage'
       OR session_user NOT IN ('postgres', 'hoviat_sns_stage')
       OR inet_server_addr() IS NOT NULL
       OR current_setting('port') <> '5432'
       OR current_setting('server_version_num')::integer / 10000 <> 18 THEN
        RAISE EXCEPTION 'STOP: expected PostgreSQL 18 staging clone, staging role, local socket port 5432';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_database d JOIN pg_roles r ON r.oid = d.datdba
        WHERE d.datname = current_database() AND r.rolname = 'hoviat_sns_stage'
    ) THEN
        RAISE EXCEPTION 'STOP: staging database owner does not match';
    END IF;
END;
$guard$;

LOCK TABLE public.users_eurobot, public.telegram_messages, public.job_queue
    IN EXCLUSIVE MODE;

-- Existing system-managed timestamp triggers remain active.
WITH reset_users AS (
    UPDATE public.users_eurobot
    SET telegram_message_id = NULL,
        group_message_id = NULL,
        public_message_id = NULL,
        public_group_message_id = NULL,
        hilfen_message_id = NULL,
        hilfen_group_message_id = NULL,
        channel_updated_at = NULL
    WHERE telegram_message_id IS NOT NULL
       OR group_message_id IS NOT NULL
       OR public_message_id IS NOT NULL
       OR public_group_message_id IS NOT NULL
       OR hilfen_message_id IS NOT NULL
       OR hilfen_group_message_id IS NOT NULL
       OR channel_updated_at IS NOT NULL
    RETURNING 1
), deleted_mappings AS (
    DELETE FROM public.telegram_messages RETURNING 1
), deleted_active_jobs AS (
    DELETE FROM public.job_queue
    WHERE status IN ('pending', 'processing')
    RETURNING 1
)
SELECT (SELECT count(*) FROM reset_users) AS users_reset,
       (SELECT count(*) FROM deleted_mappings) AS mappings_deleted,
       (SELECT count(*) FROM deleted_active_jobs) AS active_jobs_deleted;

-- A failed postcondition aborts everything.
DO $verify$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.users_eurobot
        WHERE telegram_message_id IS NOT NULL OR group_message_id IS NOT NULL
           OR public_message_id IS NOT NULL OR public_group_message_id IS NOT NULL
           OR hilfen_message_id IS NOT NULL OR hilfen_group_message_id IS NOT NULL
           OR channel_updated_at IS NOT NULL
    ) OR EXISTS (SELECT 1 FROM public.telegram_messages)
      OR EXISTS (SELECT 1 FROM public.job_queue WHERE status IN ('pending', 'processing')) THEN
        RAISE EXCEPTION 'STOP: staging Telegram reset postconditions failed';
    END IF;
END;
$verify$;

SELECT count(*) FILTER (WHERE status = 'completed') AS completed_jobs_preserved,
       count(*) FILTER (WHERE status = 'failed') AS failed_jobs_preserved
FROM public.job_queue;

COMMIT;
