-- Migration 16.
-- Turns the service location model into an international one, and introduces a
-- canonical, country-scoped first-level-region vocabulary.
--
-- Product context: the directory is presented Germany-first, but the data model
-- is international. Germany is NOT a domain invariant here: nothing in this
-- migration or the schema forbids a service in another country.
--
-- Changes:
--   1. services.country_code: canonical ISO-3166-1 alpha-2 code (DE, AT, CH...).
--      Replaces the free-text services.country column outright (see note below).
--   2. country_states: a country-scoped vocabulary of canonical first-level
--      administrative region names, seeded with the 16 German Bundeslaender and
--      their common aliases. Any country can be added by inserting rows; no
--      schema change is needed.
--   3. Indexes chosen from the search query shapes in migration-16's companion
--      code (published-only listing, country/state/city facets, category lookups).
--
-- Addditive with respect to migrations 12-15, which are left untouched.
-- users_eurobot and its triggers are not touched.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Canonical country identifier.
--
-- Migration decision on the old free-text `country` column:
-- it is DROPPED, not kept alongside the new code.
--
-- Keeping both would leave two columns able to disagree ("Germany" vs "DE"),
-- which is exactly the two-sources-of-truth problem: search would have to pick
-- one, filters would silently diverge, and the old column would keep accruing
-- unnormalised free text. Because the values already in this column are free
-- text with no reliable structure, the only honest conversion is best-effort
-- backfill to a code, then removal of the original.
--
-- The backfill maps the country spellings observed in this data set (English,
-- German and Persian forms) to DE. Unrecognised values are left NULL rather
-- than guessed: an unknown country is not the same as Germany, and a NULL is
-- representable and filterable, whereas a wrong guess is not.
-- ---------------------------------------------------------------------------
DO $BODY$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'services'
          AND column_name = 'country_code'
    ) THEN
        ALTER TABLE public.services ADD COLUMN country_code text;
        COMMENT ON COLUMN public.services.country_code IS
            'ISO-3166-1 alpha-2 country code, uppercase (e.g. DE, AT, CH). NULL means not stated. The directory is presented Germany-first, but the column is deliberately not constrained to DE.';
    END IF;
END
$BODY$;

DO $BODY$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'services'
          AND column_name = 'country'
    ) THEN
        -- Best-effort conversion of the observed spellings. Kept short and
        -- explicit rather than clever: an unexpected value stays NULL.
        UPDATE public.services
           SET country_code = 'DE'
         WHERE country_code IS NULL
           AND lower(btrim(country)) IN (
                'germany','german','deutschland','deutchland','alman','almani',
                'germai','germania','almaniya','almany','almanistan',
                'آلمان','المان','آلمین'
           );

        ALTER TABLE public.services DROP COLUMN country;
    END IF;
END
$BODY$;

-- A country code is always exactly two letters when present.
DO $BODY$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'services_country_code_format'
    ) THEN
        ALTER TABLE public.services
            ADD CONSTRAINT services_country_code_format
            CHECK (country_code IS NULL OR country_code ~ '^[A-Z]{2}$');
        COMMENT ON CONSTRAINT services_country_code_format ON public.services IS
            'country_code must be NULL or an uppercase ISO-3166-1 alpha-2 code.';
    END IF;
END
$BODY$;

-- ---------------------------------------------------------------------------
-- 2. Country-scoped first-level region vocabulary.
--
-- Only Germany's list is populated. `aliases` carries the spellings that would
-- otherwise fragment the column (English names, abbreviations, ASCII-folded
-- umlaut forms). Lookup is done case- and diacritic-insensitively in the
-- application layer, so the alias list does not have to enumerate every casing.
--
-- Adding another country is an INSERT, not a migration.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.country_states (
    id           bigserial PRIMARY KEY,
    country_code text NOT NULL,
    name         text NOT NULL,
    slug         text NOT NULL,
    aliases      text[] NOT NULL DEFAULT '{}',
    is_active    boolean NOT NULL DEFAULT true,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT country_states_country_code_format
        CHECK (country_code ~ '^[A-Z]{2}$'),
    CONSTRAINT country_states_name_not_blank
        CHECK (btrim(name) <> ''),
    CONSTRAINT country_states_slug_not_blank
        CHECK (btrim(slug) <> '')
);

-- One canonical name per country, compared case-insensitively.
CREATE UNIQUE INDEX IF NOT EXISTS country_states_country_name_key
    ON public.country_states (country_code, lower(name));

-- Slugs are globally unique because they are used as stable URL identifiers.
CREATE UNIQUE INDEX IF NOT EXISTS country_states_slug_key
    ON public.country_states (lower(slug));

COMMENT ON TABLE public.country_states IS
    'Canonical first-level administrative region names, per country. For DE these are the Bundeslaender. Unlisted countries simply have no rows, and their service.state values are stored as free text.';
COMMENT ON COLUMN public.country_states.aliases IS
    'Alternative spellings that must normalise to this canonical name (English names, abbreviations, ASCII-folded umlaut forms).';

-- Seed the 16 German Bundeslaender. Idempotent via ON CONFLICT DO NOTHING.
INSERT INTO public.country_states (country_code, name, slug, aliases) VALUES
    ('DE', 'Baden-Württemberg',  'de-baden-wuerttemberg',  ARRAY['Baden-Wurttemberg','BadenWuerttemberg','Wuerttemberg','BW']),
    ('DE', 'Bayern',            'de-bayern',              ARRAY['Bavaria','BY']),
    ('DE', 'Berlin',            'de-berlin',              ARRAY['BE']),
    ('DE', 'Brandenburg',       'de-brandenburg',         ARRAY['BB']),
    ('DE', 'Bremen',            'de-bremen',              ARRAY['HB']),
    ('DE', 'Hamburg',           'de-hamburg',             ARRAY['HH']),
    ('DE', 'Hessen',            'de-hessen',              ARRAY['Hesse','HE']),
    ('DE', 'Mecklenburg-Vorpommern', 'de-mecklenburg-vorpommern', ARRAY['Mecklenburg Western Pomerania','MV','Vorpommern']),
    ('DE', 'Niedersachsen',     'de-niedersachsen',       ARRAY['Lower Saxony','NI']),
    ('DE', 'Nordrhein-Westfalen', 'de-nordrhein-westfalen', ARRAY['North Rhine-Westphalia','Nordrhein Westfalen','Rheinland Westfalen','NW']),
    ('DE', 'Rheinland-Pfalz',   'de-rheinland-pfalz',     ARRAY['Rhineland-Palatinate','Rheinland Pfalz','RP']),
    ('DE', 'Saarland',          'de-saarland',            ARRAY['SL']),
    ('DE', 'Sachsen',           'de-sachsen',             ARRAY['Saxony','SN']),
    ('DE', 'Sachsen-Anhalt',    'de-sachsen-anhalt',      ARRAY['Saxony-Anhalt','ST']),
    ('DE', 'Schleswig-Holstein', 'de-schleswig-holstein',  ARRAY['SH']),
    ('DE', 'Thüringen',         'de-thueringen',          ARRAY['Thuringia','Thueringen','TH'])
ON CONFLICT DO NOTHING;

-- Note on aliases: the ASCII two-letter forms ("Thueringen", "BadenWuerttemberg")
-- are listed here rather than derived by a transliteration rule in code.
-- A blanket ue->u rewrite would fold "Neuss" to "ness" and "Freude" to "frde",
-- so two different names could collide and a lookup could resolve to the wrong
-- region. Every entry here is a reviewed, deliberate decision.

-- ---------------------------------------------------------------------------
-- 3. Indexes, chosen from the query shapes rather than speculatively.
--
-- The public/admin listing always filters `status`, and the Germany-first
-- frontend filters `country_code` first, so the leading-column combination is
-- (status, country_code). state and city are read as case-insensitive EXACT
-- values, and a plain btree on the raw text could not serve that; the indexes
-- are therefore on the lower() expressions the queries actually compare against.
-- ---------------------------------------------------------------------------
-- Superseded by the composite indexes below. A single-column (country_code)
-- index would never be chosen for these queries, because the leading predicate
-- is always status = 'published', so leaving it in place would only add write
-- cost.
DROP INDEX IF EXISTS public.services_state_idx;
DROP INDEX IF EXISTS public.services_city_idx;

-- Leading column is `status` because every listing constrains it; the public
-- endpoint pins status = 'published' and the admin endpoint may constrain it
-- too. That ordering makes the index usable for both an unfiltered country
-- listing and a country+region listing.
CREATE INDEX IF NOT EXISTS services_status_country_idx
    ON public.services (status, country_code);

-- state and city are read as case-insensitive EXACT values, so a plain btree on
-- the raw text cannot serve the comparison. The indexes are on the lower()
-- expressions the queries actually compare against, which is why the engine
-- marks these fields case_insensitive.
CREATE INDEX IF NOT EXISTS services_status_country_state_idx
    ON public.services (status, country_code, lower(state));

CREATE INDEX IF NOT EXISTS services_status_country_city_idx
    ON public.services (status, country_code, lower(city));

-- Admin-only: exact postal-code lookup on the (largely unique) provenance pair
-- index already exists, so nothing further is needed there.

-- Text search is ILIKE '%term%', which no btree can serve. Deliberately NOT
-- adding pg_trgm here: at current data volume the sequential scan is acceptable,
-- and an extension decision belongs in a separate, evidence-backed step.
-- See the report for the trigger conditions that would justify it.

-- service_categories.category_id already carries index=True on the column.
-- The reverse direction (service -> its links) is the table's primary key.
CREATE INDEX IF NOT EXISTS service_categories_category_service_idx
    ON public.service_categories (category_id, service_id);

COMMIT;