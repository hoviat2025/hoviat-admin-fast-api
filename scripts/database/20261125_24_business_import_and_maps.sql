-- Additive, business-directory-only storage. No user, queue or Telegram changes.
BEGIN;
ALTER TABLE services ADD COLUMN IF NOT EXISTS google_maps_url text;
ALTER TABLE services ADD COLUMN IF NOT EXISTS description_original text;
ALTER TABLE services ADD COLUMN IF NOT EXISTS import_data jsonb;
COMMIT;
