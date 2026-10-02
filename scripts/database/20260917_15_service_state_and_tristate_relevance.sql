-- Migration 15.
-- Realigns the service directory with the clarified product model:
--
--   * Location is GERMANY. Adds `state` (the German Bundesland) as the
--     first-level administrative area, alongside city / postal code / address.
--     `state` is plain text on purpose: this step must not build a geographic
--     reference system, and must not make future scope outside Germany
--     impossible.
--
--   * The four Iranian/Persian relevance signals become tri-state
--     (true / false / NULL = not assessed) and `persian_provider` is added.
--     Ownership, provider identity, language and the nature of the service are
--     four independent facts about a listing in Germany, not facts about a
--     location.
--
-- Additive only: migrations 12-14 are left exactly as published. Nothing here
-- touches users_eurobot, its timestamp functions, or any other shared table.
--
-- Run against the unified database after migration 14.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. services.state — first-level administrative area (German Bundesland).
-- ---------------------------------------------------------------------------
DO $BODY$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'services'
          AND column_name = 'state'
    ) THEN
        ALTER TABLE public.services ADD COLUMN state text;
        COMMENT ON COLUMN public.services.state IS
            'First-level administrative area. In the German scope this is the Bundesland (e.g. Hessen, Bayern, Berlin). Free text, deliberately not a reference table.';
    END IF;
END
$BODY$;

-- ---------------------------------------------------------------------------
-- 2. services.persian_provider — new, independent of ownership.
-- ---------------------------------------------------------------------------
DO $BODY$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'services'
          AND column_name = 'persian_provider'
    ) THEN
        ALTER TABLE public.services ADD COLUMN persian_provider boolean;
        COMMENT ON COLUMN public.services.persian_provider IS
            'Whether the person actually providing the service is Iranian/Persian in origin. Independent of persian_owned: a German-owned clinic with an Iranian dentist has persian_owned = false and persian_provider = true. NULL means not assessed.';
    END IF;
END
$BODY$;

-- ---------------------------------------------------------------------------
-- 3. Tri-state relevance.
--
-- The three existing flags were NOT NULL DEFAULT false, which silently turned
-- "we do not know" into "no". Relax them to nullable so unknown can be stored.
--
-- Existing rows: a NOT NULL DEFAULT false column cannot currently hold NULL, so
-- any value already present is an assertion somebody actually made. Those are
-- preserved as-is rather than being rewritten to unknown. The local development
-- database holds no service rows, so in practice this converts nothing.
-- ---------------------------------------------------------------------------
DO $BODY$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'services'
          AND column_name = 'persian_owned'
          AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE public.services ALTER COLUMN persian_owned DROP NOT NULL;
        ALTER TABLE public.services ALTER COLUMN persian_owned DROP DEFAULT;
        COMMENT ON COLUMN public.services.persian_owned IS
            'Tri-state: true = explicitly Iranian/Persian-owned, false = explicitly not, NULL = not assessed. About ownership, never about spoken language.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'services'
          AND column_name = 'persian_language'
          AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE public.services ALTER COLUMN persian_language DROP NOT NULL;
        ALTER TABLE public.services ALTER COLUMN persian_language DROP DEFAULT;
        COMMENT ON COLUMN public.services.persian_language IS
            'Tri-state: true = the service can be received in Persian, false = explicitly not, NULL = not assessed. Says nothing about the origin of the owner or the provider.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'services'
          AND column_name = 'persian_service'
          AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE public.services ALTER COLUMN persian_service DROP NOT NULL;
        ALTER TABLE public.services ALTER COLUMN persian_service DROP DEFAULT;
        COMMENT ON COLUMN public.services.persian_service IS
            'Tri-state: true = the product/service itself is Iranian/Persian in nature, false = explicitly not, NULL = not assessed. The provider need not be Iranian.';
    END IF;
END
$BODY$;

-- ---------------------------------------------------------------------------
-- 4. Index the German location columns, which are the intended public search
--    dimensions ("dentists in Frankfurt", "restaurants in Hessen"). Plain
--    btree indexes on text are enough at this stage; a dedicated geo or
--    reference-table design can come later without rewriting this migration.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS services_state_idx
    ON public.services (lower(state))
    WHERE state IS NOT NULL;

CREATE INDEX IF NOT EXISTS services_city_idx
    ON public.services (lower(city))
    WHERE city IS NOT NULL;

-- Tri-state filtering ("Persian language: yes" vs "not assessed yet") is a
-- very common admin query, and a partial index on the affirmative case keeps
-- it cheap.
CREATE INDEX IF NOT EXISTS services_persian_owned_true_idx
    ON public.services (id)
    WHERE persian_owned IS TRUE;

CREATE INDEX IF NOT EXISTS services_persian_provider_true_idx
    ON public.services (id)
    WHERE persian_provider IS TRUE;

CREATE INDEX IF NOT EXISTS services_persian_language_true_idx
    ON public.services (id)
    WHERE persian_language IS TRUE;

CREATE INDEX IF NOT EXISTS services_persian_service_true_idx
    ON public.services (id)
    WHERE persian_service IS TRUE;

COMMIT;