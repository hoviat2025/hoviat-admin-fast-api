-- Apply before deploying the service cover image model/API changes.
-- Additive and safe to rerun. No existing listing values are changed.
BEGIN;

ALTER TABLE public.services
    ADD COLUMN IF NOT EXISTS cover_image_path text;

COMMENT ON COLUMN public.services.cover_image_path IS
    'Managed object key for an uploaded business cover. Public APIs expose only a generated cover_image_url; JSON writes cannot set this key.';

COMMIT;
