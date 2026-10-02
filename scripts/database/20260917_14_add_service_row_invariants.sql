-- Migration 14.
-- Adds PostgreSQL-level CHECK constraints for the simple row invariants of the
-- service directory, and nothing else.
--
-- Deliberately narrow: only facts about a SINGLE row can be enforced here
-- (required fields, and paired optional fields). Cross-table rules - publishing
-- requires a category, exactly one primary, active primary for a published
-- service, category cycles, provenance uniqueness across rows - stay in the
-- application/domain layer, which can express them without trigger gymnastics.
--
-- Additive only. Migrations 01-13 are left exactly as published.
--
-- Run against the unified database after migrations 01-13.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. services: name required, and the two paired optional field groups.
-- ---------------------------------------------------------------------------
DO $BODY$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'services_name_not_blank'
    ) THEN
        ALTER TABLE public.services
            ADD CONSTRAINT services_name_not_blank
            CHECK (btrim(name) <> '');
    END IF;

    -- Coordinates are only meaningful as a pair.
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'services_coordinates_pair'
    ) THEN
        ALTER TABLE public.services
            ADD CONSTRAINT services_coordinates_pair
            CHECK ((latitude IS NULL) = (longitude IS NULL));
    END IF;

    -- Import provenance is all-or-nothing.
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'services_provenance_pair'
    ) THEN
        ALTER TABLE public.services
            ADD CONSTRAINT services_provenance_pair
            CHECK ((source IS NULL) = (external_id IS NULL));
    END IF;
END;
$BODY$;

-- ---------------------------------------------------------------------------
-- 2. categories: name and slug required.
-- ---------------------------------------------------------------------------
DO $BODY$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'categories_name_not_blank'
    ) THEN
        ALTER TABLE public.categories
            ADD CONSTRAINT categories_name_not_blank
            CHECK (btrim(name) <> '');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'categories_slug_not_blank'
    ) THEN
        ALTER TABLE public.categories
            ADD CONSTRAINT categories_slug_not_blank
            CHECK (btrim(slug) <> '');
    END IF;
END;
$BODY$;

-- ---------------------------------------------------------------------------
-- 3. service_contacts: title and value required.
-- ---------------------------------------------------------------------------
DO $BODY$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'service_contacts_title_not_blank'
    ) THEN
        ALTER TABLE public.service_contacts
            ADD CONSTRAINT service_contacts_title_not_blank
            CHECK (btrim(title) <> '');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'service_contacts_value_not_blank'
    ) THEN
        ALTER TABLE public.service_contacts
            ADD CONSTRAINT service_contacts_value_not_blank
            CHECK (btrim(value) <> '');
    END IF;
END;
$BODY$;

COMMENT ON CONSTRAINT services_name_not_blank ON public.services IS
    'A listing must have a non-blank name';
COMMENT ON CONSTRAINT services_coordinates_pair ON public.services IS
    'latitude and longitude are present together or both NULL';
COMMENT ON CONSTRAINT services_provenance_pair ON public.services IS
    'source and external_id are present together or both NULL';

COMMIT;