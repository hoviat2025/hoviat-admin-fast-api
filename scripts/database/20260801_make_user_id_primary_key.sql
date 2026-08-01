-- Run this first on the test database, during a short maintenance window.
-- Existing data values are preserved. Only key/constraint ownership changes.

BEGIN;

-- Stop instead of partially migrating if the assumptions are no longer true.
DO $BODY$
DECLARE
    missing_user_ids bigint;
    duplicate_user_ids bigint;
    counter_foreign_keys bigint;
BEGIN
    SELECT COUNT(*)
    INTO missing_user_ids
    FROM public.users_eurobot
    WHERE user_id IS NULL;

    SELECT COUNT(*)
    INTO duplicate_user_ids
    FROM (
        SELECT user_id
        FROM public.users_eurobot
        GROUP BY user_id
        HAVING COUNT(*) > 1
    ) duplicates;

    SELECT COUNT(*)
    INTO counter_foreign_keys
    FROM pg_constraint constraint_row
    WHERE constraint_row.contype = 'f'
      AND constraint_row.confrelid = 'public.users_eurobot'::regclass
      AND EXISTS (
          SELECT 1
          FROM unnest(constraint_row.confkey) referenced_column(attnum)
          JOIN pg_attribute attribute_row
            ON attribute_row.attrelid = constraint_row.confrelid
           AND attribute_row.attnum = referenced_column.attnum
          WHERE attribute_row.attname = 'counter'
      );

    IF missing_user_ids > 0 THEN
        RAISE EXCEPTION 'Migration stopped: % users have a null user_id', missing_user_ids;
    END IF;

    IF duplicate_user_ids > 0 THEN
        RAISE EXCEPTION 'Migration stopped: % duplicate user_id values exist', duplicate_user_ids;
    END IF;

    IF counter_foreign_keys > 0 THEN
        RAISE EXCEPTION 'Migration stopped: % foreign keys still reference counter', counter_foreign_keys;
    END IF;
END;
$BODY$;

-- Remove the current counter primary key, regardless of its generated name.
DO $BODY$
DECLARE
    primary_key_name text;
    primary_key_definition text;
BEGIN
    SELECT constraint_row.conname, pg_get_constraintdef(constraint_row.oid)
    INTO primary_key_name, primary_key_definition
    FROM pg_constraint constraint_row
    WHERE constraint_row.conrelid = 'public.users_eurobot'::regclass
      AND constraint_row.contype = 'p';

    IF primary_key_name IS NULL THEN
        RAISE EXCEPTION 'Migration stopped: users_eurobot has no primary key';
    END IF;

    IF primary_key_definition <> 'PRIMARY KEY (counter)' THEN
        RAISE EXCEPTION 'Migration stopped: unexpected existing primary key: %', primary_key_definition;
    END IF;

    EXECUTE format(
        'ALTER TABLE public.users_eurobot DROP CONSTRAINT %I',
        primary_key_name
    );
END;
$BODY$;

-- user_id already has a unique constraint. Remove that redundant constraint so
-- the new primary key can own the user_id uniqueness index instead.
DO $BODY$
DECLARE
    unique_constraint record;
BEGIN
    FOR unique_constraint IN
        SELECT constraint_row.conname
        FROM pg_constraint constraint_row
        WHERE constraint_row.conrelid = 'public.users_eurobot'::regclass
          AND constraint_row.contype = 'u'
          AND array_length(constraint_row.conkey, 1) = 1
          AND (
              SELECT attribute_row.attname
              FROM pg_attribute attribute_row
              WHERE attribute_row.attrelid = constraint_row.conrelid
                AND attribute_row.attnum = constraint_row.conkey[1]
          ) = 'user_id'
    LOOP
        EXECUTE format(
            'ALTER TABLE public.users_eurobot DROP CONSTRAINT %I',
            unique_constraint.conname
        );
    END LOOP;
END;
$BODY$;

-- counter is optional Eurobot-owned data. PostgreSQL must not generate it.
ALTER TABLE public.users_eurobot
    ALTER COLUMN counter DROP DEFAULT,
    ALTER COLUMN counter DROP NOT NULL;

-- Preserve the old guarantee that two users cannot have the same non-null
-- Eurobot counter. PostgreSQL allows multiple nulls in a UNIQUE column.
ALTER TABLE public.users_eurobot
    ADD CONSTRAINT users_eurobot_counter_key UNIQUE (counter);

-- Telegram user_id is now the required shared identity for the central row.
ALTER TABLE public.users_eurobot
    ALTER COLUMN user_id SET NOT NULL,
    ADD CONSTRAINT users_eurobot_pkey PRIMARY KEY (user_id);

COMMIT;

