-- Migration 08.
-- Records whether the current profile picture is Telegram-derived or
-- explicitly managed by the user through the SNS panel.

BEGIN;

DO $BODY$
BEGIN
    IF to_regclass('public.users_eurobot') IS NULL THEN
        RAISE EXCEPTION 'Migration stopped: public.users_eurobot does not exist';
    END IF;
END;
$BODY$;

ALTER TABLE public.users_eurobot
    ADD COLUMN IF NOT EXISTS profile_source text;

-- Existing profile_path values were produced by the Telegram bot flow.
UPDATE public.users_eurobot
SET profile_source = 'telegram'
WHERE profile_path IS NOT NULL
  AND profile_source IS NULL;

COMMENT ON COLUMN public.users_eurobot.profile_source IS
    'Profile picture provenance: telegram or user';

COMMIT;
