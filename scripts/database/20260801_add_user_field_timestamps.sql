-- Run this script in pgAdmin against the database used by this API.
-- It adds one database-controlled modification time for every user data field.

BEGIN;

ALTER TABLE public.users_eurobot
    ADD COLUMN IF NOT EXISTS counter_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS user_id_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS accounting_code_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS username_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS first_name_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS last_name_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS nickname_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS phone_number_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS whatsapp_number_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS country_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS password_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS mode_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS is_ban_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS is_registered_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS chat_not_found_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS is_in_eurobot_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS is_in_hilfen_bot_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS score_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS ban_time_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS join_date_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS profile_path_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS telegram_message_id_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS group_message_id_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS public_message_id_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS public_group_message_id_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS hilfen_id_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS hilfen_status_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS hilfen_date_join_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS hilfen_command_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS hilfen_data_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS hilfen_id_card_photo_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS hilfen_all_projects_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS hilfen_all_projects_done_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS hilfen_limits_time_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS hilfen_message_id_updated_at timestamptz,
    ADD COLUMN IF NOT EXISTS hilfen_group_message_id_updated_at timestamptz;

-- Do not let existing UPDATE triggers treat this one-time initialization as a
-- real user edit. Trigger state is safely restored before this transaction ends.
ALTER TABLE public.users_eurobot DISABLE TRIGGER USER;

-- Existing rows predate field-level tracking. Use their current row timestamp as
-- the best available starting time for every value that is already present.
UPDATE public.users_eurobot
SET
    counter_updated_at = CASE WHEN counter IS NOT NULL THEN COALESCE(counter_updated_at, updated_at) END,
    user_id_updated_at = CASE WHEN user_id IS NOT NULL THEN COALESCE(user_id_updated_at, updated_at) END,
    accounting_code_updated_at = CASE WHEN accounting_code IS NOT NULL THEN COALESCE(accounting_code_updated_at, updated_at) END,
    username_updated_at = CASE WHEN username IS NOT NULL THEN COALESCE(username_updated_at, updated_at) END,
    first_name_updated_at = CASE WHEN first_name IS NOT NULL THEN COALESCE(first_name_updated_at, updated_at) END,
    last_name_updated_at = CASE WHEN last_name IS NOT NULL THEN COALESCE(last_name_updated_at, updated_at) END,
    nickname_updated_at = CASE WHEN nickname IS NOT NULL THEN COALESCE(nickname_updated_at, updated_at) END,
    phone_number_updated_at = CASE WHEN phone_number IS NOT NULL THEN COALESCE(phone_number_updated_at, updated_at) END,
    whatsapp_number_updated_at = CASE WHEN whatsapp_number IS NOT NULL THEN COALESCE(whatsapp_number_updated_at, updated_at) END,
    country_updated_at = CASE WHEN country IS NOT NULL THEN COALESCE(country_updated_at, updated_at) END,
    password_updated_at = CASE WHEN password IS NOT NULL THEN COALESCE(password_updated_at, updated_at) END,
    mode_updated_at = CASE WHEN mode IS NOT NULL THEN COALESCE(mode_updated_at, updated_at) END,
    is_ban_updated_at = CASE WHEN is_ban IS NOT NULL THEN COALESCE(is_ban_updated_at, updated_at) END,
    is_registered_updated_at = CASE WHEN is_registered IS NOT NULL THEN COALESCE(is_registered_updated_at, updated_at) END,
    chat_not_found_updated_at = CASE WHEN chat_not_found IS NOT NULL THEN COALESCE(chat_not_found_updated_at, updated_at) END,
    is_in_eurobot_updated_at = CASE WHEN is_in_eurobot IS NOT NULL THEN COALESCE(is_in_eurobot_updated_at, updated_at) END,
    is_in_hilfen_bot_updated_at = CASE WHEN is_in_hilfen_bot IS NOT NULL THEN COALESCE(is_in_hilfen_bot_updated_at, updated_at) END,
    score_updated_at = CASE WHEN score IS NOT NULL THEN COALESCE(score_updated_at, updated_at) END,
    ban_time_updated_at = CASE WHEN ban_time IS NOT NULL THEN COALESCE(ban_time_updated_at, updated_at) END,
    join_date_updated_at = CASE WHEN join_date IS NOT NULL THEN COALESCE(join_date_updated_at, updated_at) END,
    profile_path_updated_at = CASE WHEN profile_path IS NOT NULL THEN COALESCE(profile_path_updated_at, updated_at) END,
    telegram_message_id_updated_at = CASE WHEN telegram_message_id IS NOT NULL THEN COALESCE(telegram_message_id_updated_at, updated_at) END,
    group_message_id_updated_at = CASE WHEN group_message_id IS NOT NULL THEN COALESCE(group_message_id_updated_at, updated_at) END,
    public_message_id_updated_at = CASE WHEN public_message_id IS NOT NULL THEN COALESCE(public_message_id_updated_at, updated_at) END,
    public_group_message_id_updated_at = CASE WHEN public_group_message_id IS NOT NULL THEN COALESCE(public_group_message_id_updated_at, updated_at) END,
    hilfen_id_updated_at = CASE WHEN hilfen_id IS NOT NULL THEN COALESCE(hilfen_id_updated_at, updated_at) END,
    hilfen_status_updated_at = CASE WHEN hilfen_status IS NOT NULL THEN COALESCE(hilfen_status_updated_at, updated_at) END,
    hilfen_date_join_updated_at = CASE WHEN hilfen_date_join IS NOT NULL THEN COALESCE(hilfen_date_join_updated_at, updated_at) END,
    hilfen_command_updated_at = CASE WHEN hilfen_command IS NOT NULL THEN COALESCE(hilfen_command_updated_at, updated_at) END,
    hilfen_data_updated_at = CASE WHEN hilfen_data IS NOT NULL THEN COALESCE(hilfen_data_updated_at, updated_at) END,
    hilfen_id_card_photo_updated_at = CASE WHEN hilfen_id_card_photo IS NOT NULL THEN COALESCE(hilfen_id_card_photo_updated_at, updated_at) END,
    hilfen_all_projects_updated_at = CASE WHEN hilfen_all_projects IS NOT NULL THEN COALESCE(hilfen_all_projects_updated_at, updated_at) END,
    hilfen_all_projects_done_updated_at = CASE WHEN hilfen_all_projects_done IS NOT NULL THEN COALESCE(hilfen_all_projects_done_updated_at, updated_at) END,
    hilfen_limits_time_updated_at = CASE WHEN hilfen_limits_time IS NOT NULL THEN COALESCE(hilfen_limits_time_updated_at, updated_at) END,
    hilfen_message_id_updated_at = CASE WHEN hilfen_message_id IS NOT NULL THEN COALESCE(hilfen_message_id_updated_at, updated_at) END,
    hilfen_group_message_id_updated_at = CASE WHEN hilfen_group_message_id IS NOT NULL THEN COALESCE(hilfen_group_message_id_updated_at, updated_at) END;

ALTER TABLE public.users_eurobot ENABLE TRIGGER USER;

CREATE OR REPLACE FUNCTION public.set_user_field_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $BODY$
DECLARE
    changed_at timestamptz := now();
BEGIN
    IF TG_OP = 'INSERT' THEN
        NEW.counter_updated_at := CASE WHEN NEW.counter IS NOT NULL THEN changed_at END;
        NEW.user_id_updated_at := CASE WHEN NEW.user_id IS NOT NULL THEN changed_at END;
        NEW.accounting_code_updated_at := CASE WHEN NEW.accounting_code IS NOT NULL THEN changed_at END;
        NEW.username_updated_at := CASE WHEN NEW.username IS NOT NULL THEN changed_at END;
        NEW.first_name_updated_at := CASE WHEN NEW.first_name IS NOT NULL THEN changed_at END;
        NEW.last_name_updated_at := CASE WHEN NEW.last_name IS NOT NULL THEN changed_at END;
        NEW.nickname_updated_at := CASE WHEN NEW.nickname IS NOT NULL THEN changed_at END;
        NEW.phone_number_updated_at := CASE WHEN NEW.phone_number IS NOT NULL THEN changed_at END;
        NEW.whatsapp_number_updated_at := CASE WHEN NEW.whatsapp_number IS NOT NULL THEN changed_at END;
        NEW.country_updated_at := CASE WHEN NEW.country IS NOT NULL THEN changed_at END;
        NEW.password_updated_at := CASE WHEN NEW.password IS NOT NULL THEN changed_at END;
        NEW.mode_updated_at := CASE WHEN NEW.mode IS NOT NULL THEN changed_at END;
        NEW.is_ban_updated_at := CASE WHEN NEW.is_ban IS NOT NULL THEN changed_at END;
        NEW.is_registered_updated_at := CASE WHEN NEW.is_registered IS NOT NULL THEN changed_at END;
        NEW.chat_not_found_updated_at := CASE WHEN NEW.chat_not_found IS NOT NULL THEN changed_at END;
        NEW.is_in_eurobot_updated_at := CASE WHEN NEW.is_in_eurobot IS NOT NULL THEN changed_at END;
        NEW.is_in_hilfen_bot_updated_at := CASE WHEN NEW.is_in_hilfen_bot IS NOT NULL THEN changed_at END;
        NEW.score_updated_at := CASE WHEN NEW.score IS NOT NULL THEN changed_at END;
        NEW.ban_time_updated_at := CASE WHEN NEW.ban_time IS NOT NULL THEN changed_at END;
        NEW.join_date_updated_at := CASE WHEN NEW.join_date IS NOT NULL THEN changed_at END;
        NEW.profile_path_updated_at := CASE WHEN NEW.profile_path IS NOT NULL THEN changed_at END;
        NEW.telegram_message_id_updated_at := CASE WHEN NEW.telegram_message_id IS NOT NULL THEN changed_at END;
        NEW.group_message_id_updated_at := CASE WHEN NEW.group_message_id IS NOT NULL THEN changed_at END;
        NEW.public_message_id_updated_at := CASE WHEN NEW.public_message_id IS NOT NULL THEN changed_at END;
        NEW.public_group_message_id_updated_at := CASE WHEN NEW.public_group_message_id IS NOT NULL THEN changed_at END;
        NEW.hilfen_id_updated_at := CASE WHEN NEW.hilfen_id IS NOT NULL THEN changed_at END;
        NEW.hilfen_status_updated_at := CASE WHEN NEW.hilfen_status IS NOT NULL THEN changed_at END;
        NEW.hilfen_date_join_updated_at := CASE WHEN NEW.hilfen_date_join IS NOT NULL THEN changed_at END;
        NEW.hilfen_command_updated_at := CASE WHEN NEW.hilfen_command IS NOT NULL THEN changed_at END;
        NEW.hilfen_data_updated_at := CASE WHEN NEW.hilfen_data IS NOT NULL THEN changed_at END;
        NEW.hilfen_id_card_photo_updated_at := CASE WHEN NEW.hilfen_id_card_photo IS NOT NULL THEN changed_at END;
        NEW.hilfen_all_projects_updated_at := CASE WHEN NEW.hilfen_all_projects IS NOT NULL THEN changed_at END;
        NEW.hilfen_all_projects_done_updated_at := CASE WHEN NEW.hilfen_all_projects_done IS NOT NULL THEN changed_at END;
        NEW.hilfen_limits_time_updated_at := CASE WHEN NEW.hilfen_limits_time IS NOT NULL THEN changed_at END;
        NEW.hilfen_message_id_updated_at := CASE WHEN NEW.hilfen_message_id IS NOT NULL THEN changed_at END;
        NEW.hilfen_group_message_id_updated_at := CASE WHEN NEW.hilfen_group_message_id IS NOT NULL THEN changed_at END;
        RETURN NEW;
    END IF;

    IF NEW.counter IS DISTINCT FROM OLD.counter THEN NEW.counter_updated_at := changed_at; ELSE NEW.counter_updated_at := OLD.counter_updated_at; END IF;
    IF NEW.user_id IS DISTINCT FROM OLD.user_id THEN NEW.user_id_updated_at := changed_at; ELSE NEW.user_id_updated_at := OLD.user_id_updated_at; END IF;
    IF NEW.accounting_code IS DISTINCT FROM OLD.accounting_code THEN NEW.accounting_code_updated_at := changed_at; ELSE NEW.accounting_code_updated_at := OLD.accounting_code_updated_at; END IF;
    IF NEW.username IS DISTINCT FROM OLD.username THEN NEW.username_updated_at := changed_at; ELSE NEW.username_updated_at := OLD.username_updated_at; END IF;
    IF NEW.first_name IS DISTINCT FROM OLD.first_name THEN NEW.first_name_updated_at := changed_at; ELSE NEW.first_name_updated_at := OLD.first_name_updated_at; END IF;
    IF NEW.last_name IS DISTINCT FROM OLD.last_name THEN NEW.last_name_updated_at := changed_at; ELSE NEW.last_name_updated_at := OLD.last_name_updated_at; END IF;
    IF NEW.nickname IS DISTINCT FROM OLD.nickname THEN NEW.nickname_updated_at := changed_at; ELSE NEW.nickname_updated_at := OLD.nickname_updated_at; END IF;
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

DROP TRIGGER IF EXISTS a_set_user_field_updated_at ON public.users_eurobot;
CREATE TRIGGER a_set_user_field_updated_at
BEFORE INSERT OR UPDATE ON public.users_eurobot
FOR EACH ROW
EXECUTE FUNCTION public.set_user_field_updated_at();

-- Keep the existing row-level timestamp behavior, but ignore all field timestamp
-- metadata when deciding whether real user data changed.
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
