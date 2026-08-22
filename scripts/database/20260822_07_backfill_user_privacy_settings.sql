-- Migration 07.
-- Backfill user_privacy_settings for existing users so they appear in the SNS
-- catalogue with a minimal profile: only the nickname is public by default.
-- Also tightens the column defaults so newly created rows (e.g. on first SNS
-- login) start minimal too.

BEGIN;

-- 1. Create a privacy row for every user that does not have one yet.
--    Only nickname is public; every other field is private so sensitive data
--    (phone, country, names, ...) is never exposed without opt-in.
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
    social_links_visibility
)
SELECT
    u.user_id,
    true,
    'private',
    'private',
    'private',
    'private',
    'public',
    'private',
    'private',
    'private',
    'private',
    'private'
FROM public.users_eurobot u
WHERE NOT EXISTS (
    SELECT 1
    FROM public.user_privacy_settings p
    WHERE p.user_id = u.user_id
);

-- 2. Align the column defaults with the minimal profile above, so future rows
--    also default to nickname-only visibility.
ALTER TABLE public.user_privacy_settings
    ALTER COLUMN profile_picture_visibility SET DEFAULT 'private',
    ALTER COLUMN username_visibility        SET DEFAULT 'private',
    ALTER COLUMN first_name_visibility      SET DEFAULT 'private',
    ALTER COLUMN last_name_visibility       SET DEFAULT 'private',
    ALTER COLUMN nickname_visibility        SET DEFAULT 'public',
    ALTER COLUMN country_visibility         SET DEFAULT 'private',
    ALTER COLUMN phone_number_visibility    SET DEFAULT 'private',
    ALTER COLUMN whatsapp_number_visibility SET DEFAULT 'private',
    ALTER COLUMN bio_visibility             SET DEFAULT 'private',
    ALTER COLUMN social_links_visibility    SET DEFAULT 'private';

COMMIT;
