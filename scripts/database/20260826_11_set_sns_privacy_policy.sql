-- Migration 11.
-- Sets the SNS privacy policy for ALL users: nickname, country, profile
-- picture, bio and occupation are public by default; everything else private.
--
-- Migration 07 previously backfilled rows with nickname-only public. This
-- migration upgrades every existing row to the policy now enforced in code
-- (UpdateChannelPostService and SNS login ensure_privacy_row), and aligns the
-- column defaults so future rows created via the ORM match too.
--
-- Run against the unified production database (after migrations 01-10).

BEGIN;

-- 1. Apply the policy to every existing privacy row.
UPDATE public.user_privacy_settings
SET is_profile_discoverable      = true,
    profile_picture_visibility   = 'public',
    username_visibility          = 'private',
    first_name_visibility        = 'private',
    last_name_visibility         = 'private',
    nickname_visibility          = 'public',
    country_visibility           = 'public',
    phone_number_visibility      = 'private',
    whatsapp_number_visibility   = 'private',
    bio_visibility               = 'public',
    occupation_visibility        = 'public',
    social_links_visibility      = 'private',
    updated_at                   = now();

-- 2. Align column defaults with the same policy so rows created outside the
--    explicit code insert (e.g. via the ORM) inherit identical visibility.
ALTER TABLE public.user_privacy_settings
    ALTER COLUMN profile_picture_visibility SET DEFAULT 'public',
    ALTER COLUMN username_visibility        SET DEFAULT 'private',
    ALTER COLUMN first_name_visibility      SET DEFAULT 'private',
    ALTER COLUMN last_name_visibility       SET DEFAULT 'private',
    ALTER COLUMN nickname_visibility        SET DEFAULT 'public',
    ALTER COLUMN country_visibility         SET DEFAULT 'public',
    ALTER COLUMN phone_number_visibility    SET DEFAULT 'private',
    ALTER COLUMN whatsapp_number_visibility SET DEFAULT 'private',
    ALTER COLUMN bio_visibility             SET DEFAULT 'public',
    ALTER COLUMN occupation_visibility      SET DEFAULT 'public',
    ALTER COLUMN social_links_visibility    SET DEFAULT 'private';

COMMIT;