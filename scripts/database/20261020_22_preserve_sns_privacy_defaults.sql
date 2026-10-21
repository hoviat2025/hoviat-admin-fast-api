-- Migration 22: forward-only alignment of defaults for NEW privacy rows.
-- Prerequisite: the SNS user_privacy_settings schema, including occupation.
-- Apply through the normal reviewed migration procedure for the target DB.
--
-- The original migration 11 reset existing preferences. This migration does
-- not guess or restore their previous values: it preserves every existing row,
-- including is_profile_discoverable, all visibility fields and updated_at.
-- No INSERT/UPDATE/DELETE/backfill is performed, and row-update triggers do not
-- run. SET DEFAULT affects future INSERTs that omit the corresponding column.
-- Safe to rerun: setting these defaults repeatedly has the same schema result.

BEGIN;

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
