-- Read-only verification. Run after migrations 01, 02, and 03.
-- A successful result is one row with unified_schema_ready = true.

DO $BODY$
DECLARE
    missing_user_columns text[];
    missing_field_timestamp_columns text[];
    missing_staging_columns text[];
    missing_queue_columns text[];
    missing_timestamp_rows bigint;
    primary_key_definition text;
    counter_is_nullable text;
    counter_is_unique boolean;
BEGIN
    IF to_regclass('public.job_queue') IS NULL THEN
        RAISE EXCEPTION 'Verification failed: public.job_queue is missing';
    END IF;

    SELECT array_agg(required.column_name ORDER BY required.column_name)
    INTO missing_user_columns
    FROM unnest(ARRAY[
        'is_in_eurobot',
        'is_in_hilfen_bot',
        'hilfen_id',
        'hilfen_status',
        'hilfen_date_join',
        'hilfen_command',
        'hilfen_data',
        'hilfen_id_card_photo',
        'hilfen_all_projects',
        'hilfen_all_projects_done',
        'hilfen_limits_time',
        'hilfen_message_id',
        'hilfen_group_message_id'
    ]) AS required(column_name)
    WHERE NOT EXISTS (
        SELECT 1
        FROM information_schema.columns existing
        WHERE existing.table_schema = 'public'
          AND existing.table_name = 'users_eurobot'
          AND existing.column_name = required.column_name
    );

    IF missing_user_columns IS NOT NULL THEN
        RAISE EXCEPTION
            'Verification failed: users_eurobot is missing columns %',
            missing_user_columns;
    END IF;

    SELECT array_agg(required.column_name ORDER BY required.column_name)
    INTO missing_field_timestamp_columns
    FROM (
        SELECT base_name || '_updated_at' AS column_name
        FROM unnest(ARRAY[
            'counter', 'user_id', 'accounting_code', 'username',
            'first_name', 'last_name', 'nickname', 'phone_number',
            'whatsapp_number', 'country', 'password', 'mode', 'is_ban',
            'is_registered', 'chat_not_found', 'is_in_eurobot',
            'is_in_hilfen_bot', 'score', 'ban_time', 'join_date',
            'profile_path', 'telegram_message_id', 'group_message_id',
            'public_message_id', 'public_group_message_id', 'hilfen_id',
            'hilfen_status', 'hilfen_date_join', 'hilfen_command',
            'hilfen_data', 'hilfen_id_card_photo', 'hilfen_all_projects',
            'hilfen_all_projects_done', 'hilfen_limits_time',
            'hilfen_message_id', 'hilfen_group_message_id'
        ]) AS tracked(base_name)
    ) required
    WHERE NOT EXISTS (
        SELECT 1
        FROM information_schema.columns existing
        WHERE existing.table_schema = 'public'
          AND existing.table_name = 'users_eurobot'
          AND existing.column_name = required.column_name
    );

    IF missing_field_timestamp_columns IS NOT NULL THEN
        RAISE EXCEPTION
            'Verification failed: users_eurobot is missing timestamp columns %',
            missing_field_timestamp_columns;
    END IF;

    SELECT array_agg(required.column_name ORDER BY required.column_name)
    INTO missing_staging_columns
    FROM unnest(ARRAY[
        'hilfen_message_id',
        'hilfen_group_message_id'
    ]) AS required(column_name)
    WHERE NOT EXISTS (
        SELECT 1
        FROM information_schema.columns existing
        WHERE existing.table_schema = 'public'
          AND existing.table_name = 'telegram_messages'
          AND existing.column_name = required.column_name
    );

    IF missing_staging_columns IS NOT NULL THEN
        RAISE EXCEPTION
            'Verification failed: telegram_messages is missing columns %',
            missing_staging_columns;
    END IF;

    SELECT array_agg(required.column_name ORDER BY required.column_name)
    INTO missing_queue_columns
    FROM unnest(ARRAY[
        'id', 'user_id', 'priority', 'status', 'attempts', 'max_attempts',
        'error_message', 'created_at', 'updated_at', 'completed_at', 'source'
    ]) AS required(column_name)
    WHERE NOT EXISTS (
        SELECT 1
        FROM information_schema.columns existing
        WHERE existing.table_schema = 'public'
          AND existing.table_name = 'job_queue'
          AND existing.column_name = required.column_name
    );

    IF missing_queue_columns IS NOT NULL THEN
        RAISE EXCEPTION
            'Verification failed: job_queue is missing columns %',
            missing_queue_columns;
    END IF;

    SELECT pg_get_constraintdef(constraint_row.oid)
    INTO primary_key_definition
    FROM pg_constraint constraint_row
    WHERE constraint_row.conrelid = 'public.users_eurobot'::regclass
      AND constraint_row.contype = 'p';

    IF primary_key_definition <> 'PRIMARY KEY (user_id)' THEN
        RAISE EXCEPTION
            'Verification failed: unexpected users primary key: %',
            primary_key_definition;
    END IF;

    SELECT column_row.is_nullable
    INTO counter_is_nullable
    FROM information_schema.columns column_row
    WHERE column_row.table_schema = 'public'
      AND column_row.table_name = 'users_eurobot'
      AND column_row.column_name = 'counter';

    IF counter_is_nullable <> 'YES' THEN
        RAISE EXCEPTION 'Verification failed: counter is not nullable';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM pg_constraint constraint_row
        JOIN pg_attribute attribute_row
          ON attribute_row.attrelid = constraint_row.conrelid
         AND attribute_row.attnum = constraint_row.conkey[1]
        WHERE constraint_row.conrelid = 'public.users_eurobot'::regclass
          AND constraint_row.contype = 'u'
          AND array_length(constraint_row.conkey, 1) = 1
          AND attribute_row.attname = 'counter'
    )
    INTO counter_is_unique;

    IF NOT counter_is_unique THEN
        RAISE EXCEPTION 'Verification failed: counter has no unique constraint';
    END IF;

    IF to_regprocedure('public.set_user_field_updated_at()') IS NULL THEN
        RAISE EXCEPTION
            'Verification failed: set_user_field_updated_at() is missing';
    END IF;

    IF to_regprocedure('public.set_updated_at()') IS NULL THEN
        RAISE EXCEPTION 'Verification failed: set_updated_at() is missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger trigger_row
        WHERE trigger_row.tgrelid = 'public.users_eurobot'::regclass
          AND trigger_row.tgname = 'a_set_user_field_updated_at'
          AND NOT trigger_row.tgisinternal
          AND trigger_row.tgenabled <> 'D'
    ) THEN
        RAISE EXCEPTION
            'Verification failed: per-field timestamp trigger is missing';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger trigger_row
        WHERE trigger_row.tgrelid = 'public.users_eurobot'::regclass
          AND trigger_row.tgname = 'trigger_set_updated_at'
          AND NOT trigger_row.tgisinternal
          AND trigger_row.tgenabled <> 'D'
    ) THEN
        RAISE EXCEPTION
            'Verification failed: global updated_at trigger is missing';
    END IF;

    SELECT COUNT(*)
    INTO missing_timestamp_rows
    FROM public.users_eurobot users
    WHERE EXISTS (
        SELECT 1
        FROM jsonb_each(to_jsonb(users)) field
        WHERE field.key LIKE '%\_updated\_at' ESCAPE '\'
          AND field.key NOT IN ('updated_at', 'channel_updated_at')
          AND field.value = 'null'::jsonb
    );

    IF missing_timestamp_rows > 0 THEN
        RAISE EXCEPTION
            'Verification failed: % users have missing field timestamps',
            missing_timestamp_rows;
    END IF;

    IF to_regclass('public.idx_job_queue_active_user_job') IS NULL
       OR to_regclass('public.idx_job_queue_fetch') IS NULL THEN
        RAISE EXCEPTION 'Verification failed: a job_queue index is missing';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_trigger trigger_row
        WHERE trigger_row.tgrelid = 'public.users_eurobot'::regclass
          AND trigger_row.tgname = 'a_freeze_experiment_user_fields'
          AND NOT trigger_row.tgisinternal
    ) THEN
        RAISE EXCEPTION
            'Verification failed: temporary experiment lock trigger still exists';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM public.users_eurobot
        WHERE user_id IS NULL
           OR is_in_eurobot IS NULL
           OR is_in_hilfen_bot IS NULL
    ) THEN
        RAISE EXCEPTION
            'Verification failed: a required user identity/presence value is null';
    END IF;
END;
$BODY$;

SELECT
    true AS unified_schema_ready,
    (SELECT COUNT(*) FROM public.users_eurobot) AS user_count,
    (SELECT COUNT(*) FROM public.telegram_messages) AS staged_message_count,
    (SELECT COUNT(*) FROM public.job_queue) AS queued_job_count;
