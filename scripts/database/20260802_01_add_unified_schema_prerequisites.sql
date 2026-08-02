-- Migration 01 of 03.
-- Run against a restored copy of the current Neon production database.
-- Adds the shared Eurobot/Hilfen schema required before changing keys or
-- installing per-field timestamp tracking.

BEGIN;

-- These tables must already exist in the current production schema.
DO $BODY$
BEGIN
    IF to_regclass('public.users_eurobot') IS NULL THEN
        RAISE EXCEPTION 'Migration stopped: public.users_eurobot does not exist';
    END IF;

    IF to_regclass('public.telegram_messages') IS NULL THEN
        RAISE EXCEPTION 'Migration stopped: public.telegram_messages does not exist';
    END IF;
END;
$BODY$;

-- Remove the temporary single-row column-lock experiment from Neon. It must
-- not survive into the unified production database.
DROP TRIGGER IF EXISTS a_freeze_experiment_user_fields
    ON public.users_eurobot;
DROP FUNCTION IF EXISTS public.freeze_experiment_user_fields();

-- The final queue schema used by both worker lanes.
CREATE TABLE IF NOT EXISTS public.job_queue
(
    id serial PRIMARY KEY,
    user_id bigint NOT NULL,
    priority integer NOT NULL DEFAULT 2,
    status text NOT NULL DEFAULT 'pending',
    attempts integer NOT NULL DEFAULT 0,
    max_attempts integer NOT NULL DEFAULT 3,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    source text NOT NULL DEFAULT 'eurobot',
    CONSTRAINT job_queue_priority_check
        CHECK (priority = ANY (ARRAY[1, 2, 3])),
    CONSTRAINT job_queue_status_check
        CHECK (status = ANY (ARRAY['pending', 'processing', 'completed', 'failed']))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_job_queue_active_user_job
    ON public.job_queue (user_id)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_job_queue_fetch
    ON public.job_queue (status ASC, priority DESC, created_at ASC);

-- Add the two staging columns used to join Hilfen channel/group messages back
-- to the main Telegram channel post.
ALTER TABLE public.telegram_messages
    ADD COLUMN IF NOT EXISTS hilfen_message_id integer,
    ADD COLUMN IF NOT EXISTS hilfen_group_message_id integer;

-- Presence columns require a one-time backfill. Only perform that backfill
-- when neither column existed before this migration, so rerunning the script
-- cannot turn later Hilfen-only users into Eurobot users.
DO $BODY$
DECLARE
    existing_presence_columns integer;
BEGIN
    SELECT COUNT(*)
    INTO existing_presence_columns
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'users_eurobot'
      AND column_name IN ('is_in_eurobot', 'is_in_hilfen_bot');

    IF existing_presence_columns = 0 THEN
        ALTER TABLE public.users_eurobot
            ADD COLUMN is_in_eurobot boolean NOT NULL DEFAULT false,
            ADD COLUMN is_in_hilfen_bot boolean NOT NULL DEFAULT false;

        -- Preserve every row's historical updated_at while recording that all
        -- rows from the old Neon database originated in Eurobot.
        ALTER TABLE public.users_eurobot DISABLE TRIGGER USER;
        UPDATE public.users_eurobot
        SET is_in_eurobot = true,
            is_in_hilfen_bot = false;
        ALTER TABLE public.users_eurobot ENABLE TRIGGER USER;
    ELSIF existing_presence_columns = 2 THEN
        RAISE NOTICE 'Presence columns already exist; skipping old-row backfill';
    ELSE
        RAISE EXCEPTION
            'Migration stopped: only one bot-presence column exists';
    END IF;
END;
$BODY$;

-- Hilfen-owned profile and internal message fields.
ALTER TABLE public.users_eurobot
    ADD COLUMN IF NOT EXISTS hilfen_id bigint,
    ADD COLUMN IF NOT EXISTS hilfen_status text,
    ADD COLUMN IF NOT EXISTS hilfen_date_join bigint,
    ADD COLUMN IF NOT EXISTS hilfen_command text,
    ADD COLUMN IF NOT EXISTS hilfen_data text,
    ADD COLUMN IF NOT EXISTS hilfen_id_card_photo text,
    ADD COLUMN IF NOT EXISTS hilfen_all_projects integer DEFAULT 0,
    ADD COLUMN IF NOT EXISTS hilfen_all_projects_done integer DEFAULT 0,
    ADD COLUMN IF NOT EXISTS hilfen_limits_time bigint DEFAULT 0,
    ADD COLUMN IF NOT EXISTS hilfen_message_id bigint,
    ADD COLUMN IF NOT EXISTS hilfen_group_message_id bigint;

COMMIT;
