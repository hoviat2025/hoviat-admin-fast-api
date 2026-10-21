-- Migration 11.
-- Sets defaults for NEW SNS privacy rows: nickname, country, profile picture,
-- bio and occupation public; everything else private; profile discoverable.
--
-- Existing visibility choices and updated_at are preserved, including choices
-- made under migration 07's nickname-only defaults. Defaults are not consent to
-- change existing rows. Mirror the explicit inserts in UpdateChannelPostService
-- and SNS login ensure_privacy_row, and the ORM server defaults.
--
-- Corrected 2026-10-20: the original revision unconditionally reset every
-- existing privacy row. If it was already applied, use migration 22 for the
-- forward defaults-only path. Neither revision can restore earlier preferences;
-- restoration requires trustworthy backups/audit evidence and a separate plan.
--
-- Run against the unified production database (after migrations 01-10).

BEGIN;

-- Defaults affect only future inserts that omit the respective columns.
ALTER TABLE public.user_privacy_settings
    ALTER COLUMN is_profile_discoverable    SET DEFAULT true,
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
