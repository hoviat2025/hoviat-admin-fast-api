-- MANUAL TEST SCRIPT (not part of the numbered migrations).
-- Opens all privacy settings for the first 3000 users so the SNS frontend
-- has visible data to work against on staging.
--
-- Run manually against the staging database:
--   sudo -u postgres psql -d <staging_db_name> -f manual_open_visibility_first_3000.sql

BEGIN;

CREATE TEMP TABLE tmp_first_3000 AS
SELECT user_id
FROM public.users_eurobot
ORDER BY user_id ASC
LIMIT 3000;

-- 1. Update rows that already exist.
UPDATE public.user_privacy_settings p
SET is_profile_discoverable      = true,
    profile_picture_visibility   = 'public',
    username_visibility          = 'public',
    first_name_visibility        = 'public',
    last_name_visibility         = 'public',
    nickname_visibility          = 'public',
    country_visibility           = 'public',
    phone_number_visibility      = 'public',
    whatsapp_number_visibility   = 'public',
    bio_visibility               = 'public',
    occupation_visibility        = 'public',
    social_links_visibility      = 'public',
    updated_at                   = now()
FROM tmp_first_3000 t
WHERE p.user_id = t.user_id;

-- 2. Insert rows for users who had none at all.
INSERT INTO public.user_privacy_settings (
    user_id,
    is_profile_discoverable,
    profile_picture_visibility,
    username_visibility,
    first_name_visibility,
    last_name_visibility,
    nickname_visibility,
    country_visibility,
    phone_number_visibility,
    whatsapp_number_visibility,
    bio_visibility,
    occupation_visibility,
    social_links_visibility
)
SELECT
    t.user_id,
    true,
    'public'::privacy_scope,
    'public'::privacy_scope,
    'public'::privacy_scope,
    'public'::privacy_scope,
    'public'::privacy_scope,
    'public'::privacy_scope,
    'public'::privacy_scope,
    'public'::privacy_scope,
    'public'::privacy_scope,
    'public'::privacy_scope,
    'public'::privacy_scope
FROM tmp_first_3000 t
WHERE NOT EXISTS (
    SELECT 1 FROM public.user_privacy_settings p WHERE p.user_id = t.user_id
);

COMMIT;

-- Sanity check afterwards:
-- SELECT count(*), count(*) FILTER (WHERE is_profile_discoverable) AS discoverable
-- FROM public.user_privacy_settings
-- WHERE user_id IN (SELECT user_id FROM public.users_eurobot ORDER BY user_id LIMIT 3000);
