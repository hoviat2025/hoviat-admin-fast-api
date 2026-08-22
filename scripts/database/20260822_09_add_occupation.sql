-- Migration 09.
-- Adds the "occupation" self-presentation field to users_eurobot (mirroring
-- bio), its privacy visibility toggle, and wires occupation into the existing
-- per-field timestamp triggers.

BEGIN;

DO $BODY$
BEGIN
    IF to_regclass('public.users_eurobot') IS NULL THEN
        RAISE EXCEPTION 'Migration stopped: public.users_eurobot does not exist';
    END IF;
    IF to_regclass('public.user_privacy_settings') IS NULL THEN
        RAISE EXCEPTION 'Migration stopped: public.user_privacy_settings does not exist';
    END IF;
END;
$BODY$;

-- 1. Add occupation columns to users_eurobot (before the trigger functions
--    below, which reference them via %ROWTYPE).
ALTER TABLE public.users_eurobot
    ADD COLUMN IF NOT EXISTS occupation text,
    ADD COLUMN IF NOT EXISTS occupation_updated_at timestamptz;

-- 2. Add the privacy visibility toggle (defaults to private, matching the
--    minimal profile policy).
ALTER TABLE public.user_privacy_settings
    ADD COLUMN IF NOT EXISTS occupation_visibility privacy_scope NOT NULL DEFAULT 'private';

-- 3. Re-declare the per-field timestamp trigger to include occupation.
CREATE OR REPLACE FUNCTION public.set_user_field_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $BODY$
DECLARE
    changed_at timestamptz := now();
BEGIN
    IF TG_OP = 'INSERT' THEN
        NEW.counter_updated_at := changed_at;
        NEW.user_id_updated_at := changed_at;
        NEW.accounting_code_updated_at := changed_at;
        NEW.username_updated_at := changed_at;
        NEW.first_name_updated_at := changed_at;
        NEW.last_name_updated_at := changed_at;
        NEW.nickname_updated_at := changed_at;
        NEW.bio_updated_at := changed_at;
        NEW.occupation_updated_at := changed_at;
        NEW.phone_number_updated_at := changed_at;
        NEW.whatsapp_number_updated_at := changed_at;
        NEW.country_updated_at := changed_at;
        NEW.password_updated_at := changed_at;
        NEW.mode_updated_at := changed_at;
        NEW.is_ban_updated_at := changed_at;
        NEW.is_registered_updated_at := changed_at;
        NEW.chat_not_found_updated_at := changed_at;
        NEW.is_in_eurobot_updated_at := changed_at;
        NEW.is_in_hilfen_bot_updated_at := changed_at;
        NEW.score_updated_at := changed_at;
        NEW.ban_time_updated_at := changed_at;
        NEW.join_date_updated_at := changed_at;
        NEW.profile_path_updated_at := changed_at;
        NEW.telegram_message_id_updated_at := changed_at;
        NEW.group_message_id_updated_at := changed_at;
        NEW.public_message_id_updated_at := changed_at;
        NEW.public_group_message_id_updated_at := changed_at;
        NEW.hilfen_id_updated_at := changed_at;
        NEW.hilfen_status_updated_at := changed_at;
        NEW.hilfen_date_join_updated_at := changed_at;
        NEW.hilfen_command_updated_at := changed_at;
        NEW.hilfen_data_updated_at := changed_at;
        NEW.hilfen_id_card_photo_updated_at := changed_at;
        NEW.hilfen_all_projects_updated_at := changed_at;
        NEW.hilfen_all_projects_done_updated_at := changed_at;
        NEW.hilfen_limits_time_updated_at := changed_at;
        NEW.hilfen_message_id_updated_at := changed_at;
        NEW.hilfen_group_message_id_updated_at := changed_at;
        RETURN NEW;
    END IF;

    IF NEW.counter IS DISTINCT FROM OLD.counter THEN NEW.counter_updated_at := changed_at; ELSE NEW.counter_updated_at := OLD.counter_updated_at; END IF;
    IF NEW.user_id IS DISTINCT FROM OLD.user_id THEN NEW.user_id_updated_at := changed_at; ELSE NEW.user_id_updated_at := OLD.user_id_updated_at; END IF;
    IF NEW.accounting_code IS DISTINCT FROM OLD.accounting_code THEN NEW.accounting_code_updated_at := changed_at; ELSE NEW.accounting_code_updated_at := OLD.accounting_code_updated_at; END IF;
    IF NEW.username IS DISTINCT FROM OLD.username THEN NEW.username_updated_at := changed_at; ELSE NEW.username_updated_at := OLD.username_updated_at; END IF;
    IF NEW.first_name IS DISTINCT FROM OLD.first_name THEN NEW.first_name_updated_at := changed_at; ELSE NEW.first_name_updated_at := OLD.first_name_updated_at; END IF;
    IF NEW.last_name IS DISTINCT FROM OLD.last_name THEN NEW.last_name_updated_at := changed_at; ELSE NEW.last_name_updated_at := OLD.last_name_updated_at; END IF;
    IF NEW.nickname IS DISTINCT FROM OLD.nickname THEN NEW.nickname_updated_at := changed_at; ELSE NEW.nickname_updated_at := OLD.nickname_updated_at; END IF;
    IF NEW.bio IS DISTINCT FROM OLD.bio THEN NEW.bio_updated_at := changed_at; ELSE NEW.bio_updated_at := OLD.bio_updated_at; END IF;
    IF NEW.occupation IS DISTINCT FROM OLD.occupation THEN NEW.occupation_updated_at := changed_at; ELSE NEW.occupation_updated_at := OLD.occupation_updated_at; END IF;
    IF NEW.phone_number IS DISTINCT FROM OLD.phone_number THEN NEW.phone_number_updated_at := changed_at; ELSE NEW.phone_number_updated_at := OLD.phone_number_updated_at; END IF;
    IF NEW.whatsapp_number IS DISTINCT FROM OLD.whatsapp_number THEN NEW.whatsapp_number_updated_at := changed_at; ELSE NEW.whatsapp_number_updated_at := OLD.whatsapp_number_updated_at; END IF;
    IF NEW.country IS DISTINCT FROM OLD.country THEN NEW.country_updated_at := changed_at; ELSE NEW.country_updated_at := OLD.country_updated_at; END IF;
    IF NEW.password IS DISTINCT FROM OLD.password THEN NEW.password_updated_at := changed_at; ELSE NEW.password_updated_at := OLD.password_updated_at; END IF;
    IF NEW.mode IS DISTINCT FROM OLD.mode THEN NEW.mode_updated_at := changed_at; ELSE NEW.mode_updated_at := OLD.mode_updated_at; END IF;
    IF NEW.is_ban IS DISTINCT FROM OLD.is_ban THEN NEW.is_ban_updated_at := changed_at; ELSE NEW.is_ban_updated_at := OLD.is_ban_updated_at; END IF;
    IF NEW.is_registered IS DISTINCT FROM OLD.is_registered THEN NEW.is_registered_updated_at := changed_at; ELSE NEW.is_registered_updated_at := OLD.is_registered_updated_at; END IF;
    IF NEW.chat_not_found IS DISTINCT FROM OLD.chat_not_found THEN NEW.chat_not_found_updated_at := changed_at; ELSE NEW.chat_not_found_updated_at := OLD.chat_not_found_updated_at; END IF;
    IF NEW.is_in_eurobot IS DISTINCT FROM OLD.is_in_eurobot THEN NEW.is_in_eurobot_updated_at := changed_at; ELSE NEW.is_in_eurobot_updated_at := OLD.is_in_eurobot_updated_at; END IF;
    IF NEW.is_in_hilfen_bot IS DISTINCT FROM OLD.is_in_hilfen_bot THEN NEW.is_in_hilfen_bot_updated_at := changed_at; ELSE NEW.is_in_hilfen_bot_updated_at := OLD.is_in_hilfen_bot_updated_at; END IF;
    IF NEW.score IS DISTINCT FROM OLD.score THEN NEW.score_updated_at := changed_at; ELSE NEW.score_updated_at := OLD.score_updated_at; END IF;
    IF NEW.ban_time IS DISTINCT FROM OLD.ban_time THEN NEW.ban_time_updated_at := changed_at; ELSE NEW.ban_time_updated_at := OLD.ban_time_updated_at; END IF;
    IF NEW.join_date IS DISTINCT FROM OLD.join_date THEN NEW.join_date_updated_at := changed_at; ELSE NEW.join_date_updated_at := OLD.join_date_updated_at; END IF;
    IF NEW.profile_path IS DISTINCT FROM OLD.profile_path THEN NEW.profile_path_updated_at := changed_at; ELSE NEW.profile_path_updated_at := OLD.profile_path_updated_at; END IF;
    IF NEW.telegram_message_id IS DISTINCT FROM OLD.telegram_message_id THEN NEW.telegram_message_id_updated_at := changed_at; ELSE NEW.telegram_message_id_updated_at := OLD.telegram_message_id_updated_at; END IF;
    IF NEW.group_message_id IS DISTINCT FROM OLD.group_message_id THEN NEW.group_message_id_updated_at := changed_at; ELSE NEW.group_message_id_updated_at := OLD.group_message_id_updated_at; END IF;
    IF NEW.public_message_id IS DISTINCT FROM OLD.public_message_id THEN NEW.public_message_id_updated_at := changed_at; ELSE NEW.public_message_id_updated_at := OLD.public_message_id_updated_at; END IF;
    IF NEW.public_group_message_id IS DISTINCT FROM OLD.public_group_message_id THEN NEW.public_group_message_id_updated_at := changed_at; ELSE NEW.public_group_message_id_updated_at := OLD.public_group_message_id_updated_at; END IF;
    IF NEW.hilfen_id IS DISTINCT FROM OLD.hilfen_id THEN NEW.hilfen_id_updated_at := changed_at; ELSE NEW.hilfen_id_updated_at := OLD.hilfen_id_updated_at; END IF;
    IF NEW.hilfen_status IS DISTINCT FROM OLD.hilfen_status THEN NEW.hilfen_status_updated_at := changed_at; ELSE NEW.hilfen_status_updated_at := OLD.hilfen_status_updated_at; END IF;
    IF NEW.hilfen_date_join IS DISTINCT FROM OLD.hilfen_date_join THEN NEW.hilfen_date_join_updated_at := changed_at; ELSE NEW.hilfen_date_join_updated_at := OLD.hilfen_date_join_updated_at; END IF;
    IF NEW.hilfen_command IS DISTINCT FROM OLD.hilfen_command THEN NEW.hilfen_command_updated_at := changed_at; ELSE NEW.hilfen_command_updated_at := OLD.hilfen_command_updated_at; END IF;
    IF NEW.hilfen_data IS DISTINCT FROM OLD.hilfen_data THEN NEW.hilfen_data_updated_at := changed_at; ELSE NEW.hilfen_data_updated_at := OLD.hilfen_data_updated_at; END IF;
    IF NEW.hilfen_id_card_photo IS DISTINCT FROM OLD.hilfen_id_card_photo THEN NEW.hilfen_id_card_photo_updated_at := changed_at; ELSE NEW.hilfen_id_card_photo_updated_at := OLD.hilfen_id_card_photo_updated_at; END IF;
    IF NEW.hilfen_all_projects IS DISTINCT FROM OLD.hilfen_all_projects THEN NEW.hilfen_all_projects_updated_at := changed_at; ELSE NEW.hilfen_all_projects_updated_at := OLD.hilfen_all_projects_updated_at; END IF;
    IF NEW.hilfen_all_projects_done IS DISTINCT FROM OLD.hilfen_all_projects_done THEN NEW.hilfen_all_projects_done_updated_at := changed_at; ELSE NEW.hilfen_all_projects_done_updated_at := OLD.hilfen_all_projects_done_updated_at; END IF;
    IF NEW.hilfen_limits_time IS DISTINCT FROM OLD.hilfen_limits_time THEN NEW.hilfen_limits_time_updated_at := changed_at; ELSE NEW.hilfen_limits_time_updated_at := OLD.hilfen_limits_time_updated_at; END IF;
    IF NEW.hilfen_message_id IS DISTINCT FROM OLD.hilfen_message_id THEN NEW.hilfen_message_id_updated_at := changed_at; ELSE NEW.hilfen_message_id_updated_at := OLD.hilfen_message_id_updated_at; END IF;
    IF NEW.hilfen_group_message_id IS DISTINCT FROM OLD.hilfen_group_message_id THEN NEW.hilfen_group_message_id_updated_at := changed_at; ELSE NEW.hilfen_group_message_id_updated_at := OLD.hilfen_group_message_id_updated_at; END IF;

    RETURN NEW;
END;
$BODY$;

-- 4. Re-declare the updated_at trigger so occupation_updated_at is ignored as
--    a "real change" when deciding whether to bump updated_at.
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $BODY$
DECLARE
    comparison_row users_eurobot%ROWTYPE;
BEGIN
    comparison_row := NEW;

    comparison_row.channel_updated_at := OLD.channel_updated_at;
    comparison_row.chat_not_found := OLD.chat_not_found;
    comparison_row.telegram_message_id := OLD.telegram_message_id;
    comparison_row.group_message_id := OLD.group_message_id;
    comparison_row.public_message_id := OLD.public_message_id;
    comparison_row.public_group_message_id := OLD.public_group_message_id;
    comparison_row.updated_at := OLD.updated_at;

    comparison_row.counter_updated_at := OLD.counter_updated_at;
    comparison_row.user_id_updated_at := OLD.user_id_updated_at;
    comparison_row.accounting_code_updated_at := OLD.accounting_code_updated_at;
    comparison_row.username_updated_at := OLD.username_updated_at;
    comparison_row.first_name_updated_at := OLD.first_name_updated_at;
    comparison_row.last_name_updated_at := OLD.last_name_updated_at;
    comparison_row.nickname_updated_at := OLD.nickname_updated_at;
    comparison_row.bio_updated_at := OLD.bio_updated_at;
    comparison_row.occupation_updated_at := OLD.occupation_updated_at;
    comparison_row.phone_number_updated_at := OLD.phone_number_updated_at;
    comparison_row.whatsapp_number_updated_at := OLD.whatsapp_number_updated_at;
    comparison_row.country_updated_at := OLD.country_updated_at;
    comparison_row.password_updated_at := OLD.password_updated_at;
    comparison_row.mode_updated_at := OLD.mode_updated_at;
    comparison_row.is_ban_updated_at := OLD.is_ban_updated_at;
    comparison_row.is_registered_updated_at := OLD.is_registered_updated_at;
    comparison_row.chat_not_found_updated_at := OLD.chat_not_found_updated_at;
    comparison_row.is_in_eurobot_updated_at := OLD.is_in_eurobot_updated_at;
    comparison_row.is_in_hilfen_bot_updated_at := OLD.is_in_hilfen_bot_updated_at;
    comparison_row.score_updated_at := OLD.score_updated_at;
    comparison_row.ban_time_updated_at := OLD.ban_time_updated_at;
    comparison_row.join_date_updated_at := OLD.join_date_updated_at;
    comparison_row.profile_path_updated_at := OLD.profile_path_updated_at;
    comparison_row.telegram_message_id_updated_at := OLD.telegram_message_id_updated_at;
    comparison_row.group_message_id_updated_at := OLD.group_message_id_updated_at;
    comparison_row.public_message_id_updated_at := OLD.public_message_id_updated_at;
    comparison_row.public_group_message_id_updated_at := OLD.public_group_message_id_updated_at;
    comparison_row.hilfen_id_updated_at := OLD.hilfen_id_updated_at;
    comparison_row.hilfen_status_updated_at := OLD.hilfen_status_updated_at;
    comparison_row.hilfen_date_join_updated_at := OLD.hilfen_date_join_updated_at;
    comparison_row.hilfen_command_updated_at := OLD.hilfen_command_updated_at;
    comparison_row.hilfen_data_updated_at := OLD.hilfen_data_updated_at;
    comparison_row.hilfen_id_card_photo_updated_at := OLD.hilfen_id_card_photo_updated_at;
    comparison_row.hilfen_all_projects_updated_at := OLD.hilfen_all_projects_updated_at;
    comparison_row.hilfen_all_projects_done_updated_at := OLD.hilfen_all_projects_done_updated_at;
    comparison_row.hilfen_limits_time_updated_at := OLD.hilfen_limits_time_updated_at;
    comparison_row.hilfen_message_id_updated_at := OLD.hilfen_message_id_updated_at;
    comparison_row.hilfen_group_message_id_updated_at := OLD.hilfen_group_message_id_updated_at;

    IF comparison_row IS DISTINCT FROM OLD THEN
        NEW.updated_at := now();
    END IF;

    RETURN NEW;
END;
$BODY$;

COMMIT;
