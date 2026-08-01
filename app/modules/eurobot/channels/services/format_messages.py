import time
from datetime import datetime, timezone

def format_unix_date(timestamp):
    """
    Formats Unix timestamp (seconds) to YYYY/MM/DD.
    Matches JS: new Date(Number(timestamp) * 1000).toISOString()...
    """
    if not timestamp or str(timestamp) == "0" or timestamp == 0:
        return None
    
    try:
        # JS toISOString returns UTC dates, so we use utcfromtimestamp
        dt = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
        return dt.strftime("%Y/%m/%d")
    except (ValueError, TypeError, OverflowError, OSError):
        return None

def create_telegram_message(data):
    """
    Converts input dictionary into formatted Telegram message and components.
    """
    # --- 1. Process Values (Logic Layer) ---

    # Basic extractions with defaults
    f_name = data.get("first_name") or ""
    l_name = data.get("last_name") or ""
    telegram_name = data.get("nickname") or ""
    username = data.get("username") or ""
    
    phone_raw = data.get("phone_number")
    phone = f"+{phone_raw}" if phone_raw else ""
    
    user_id = data.get("user_id") or ""
    command = "add_user"

    # Complex Logic
    # Handle boolean truthiness similar to JS
    register_status_val = "رجیستر شده" if data.get("is_registered") else "رجیستر نشده"
    
    join_date_processed = format_unix_date(data.get("join_date"))
    join_date_val = join_date_processed if join_date_processed else ""

    ban_status_val = "بن هست" if data.get("is_ban") else "بن نیست"

    ban_time_input = data.get("ban_time")
    if not ban_time_input or str(ban_time_input) == "0" or ban_time_input == 0:
        ban_date_val = "بن نیست"
    else:
        ban_date_val = format_unix_date(ban_time_input) or ""

    chat_not_found_val = "صحیح" if data.get("chat_not_found") else "خیر"

    is_in_eurobot = bool(data.get("is_in_eurobot"))
    is_in_hilfen_bot = bool(data.get("is_in_hilfen_bot"))
    eurobot_membership_val = "بله" if is_in_eurobot else "خیر"
    hilfen_membership_val = "بله" if is_in_hilfen_bot else "خیر"

    hilfen_status_raw = data.get("hilfen_status")
    hilfen_status_val = {
        "confirm": "تایید شده",
        "notconfirm": "تایید نشده",
    }.get(hilfen_status_raw, str(hilfen_status_raw) if hilfen_status_raw else "نامشخص")

    hilfen_join_date_val = format_unix_date(data.get("hilfen_date_join")) or "نامشخص"

    hilfen_limits_time = data.get("hilfen_limits_time")
    if not hilfen_limits_time or str(hilfen_limits_time) == "0":
        hilfen_limits_time_val = "محدود نشده"
    else:
        hilfen_limits_time_val = format_unix_date(hilfen_limits_time) or "نامشخص"

    try:
        hilfen_all_projects = int(data.get("hilfen_all_projects") or 0)
    except (ValueError, TypeError):
        hilfen_all_projects = 0

    try:
        hilfen_all_projects_done = int(data.get("hilfen_all_projects_done") or 0)
    except (ValueError, TypeError):
        hilfen_all_projects_done = 0

    # Score Logic
    try:
        score_val = int(data.get("score", 0))
    except (ValueError, TypeError):
        score_val = 0
        
    # Stars Logic (Hardcoded to 5 stars in original JS)
    stars_string = "⭐️" * 5

    # --- 2. Create Mini Texts (Components) ---
    components = {
        "is_registered":   f"وضعیت رجیستر : {register_status_val}",
        "first_name":      f"نام : {f_name}",
        "last_name":       f"نام خانوادگی : {l_name}",
        "username":        f"یوزر تلگرام : @{username}",
        "telegram_name":   f"نام در تلگرام : {telegram_name}",
        "country":         f"کشور : {data.get('country') or ''}",
        "phone_number":    f"شماره همراه: {phone}",
        "join_date":       f"تاریخ عضویت : {join_date_val}",
        "whatsapp_number": f"شماره واتساپ : {data.get('whatsapp_number') or ''}",
        "score":           f"امتیاز : {score_val}",
        "user_id":         f"آیدی : {user_id}",
        "password":        f"پسورد : {data.get('password') or ''}",
        "accounting_code": f"کد حسابداری : {data.get('accounting_code') or ''}",
        "is_in_eurobot":   f"عضویت در یوروبات : {eurobot_membership_val}",
        "is_in_hilfen_bot": f"عضویت در هیلفن : {hilfen_membership_val}",
        "is_ban":          f"وضعیت بن : {ban_status_val}",
        "ban_time":        f"تاریخ بن شدن : {ban_date_val}",
        "chat_not_found":  f"چت یافت نشد : {chat_not_found_val}",
        "new_user_alert":  "❗️مشتری جدید",
        "stars":           f"ستاره ها : « {stars_string} »",
        "footer_code":     f"$%^{user_id}^$%{command}"
    }

    hilfen_component_keys = []
    if is_in_hilfen_bot:
        components.update({
            "hilfen_id": f"آیدی در هیلفن : {data.get('hilfen_id') or 'نامشخص'}",
            "hilfen_status": f"وضعیت در هیلفن : {hilfen_status_val}",
            "hilfen_date_join": f"تاریخ عضویت در هیلفن : {hilfen_join_date_val}",
            "hilfen_projects": (
                f"پروژه‌های هیلفن : {hilfen_all_projects} کل، "
                f"{hilfen_all_projects_done} تکمیل شده"
            ),
            "hilfen_limits_time": f"تاریخ محدودیت در هیلفن : {hilfen_limits_time_val}",
        })
        hilfen_component_keys = [
            "hilfen_id",
            "hilfen_status",
            "hilfen_date_join",
            "hilfen_projects",
            "hilfen_limits_time",
        ]

    hilfen_details_section = "\n".join(
        components[key] for key in hilfen_component_keys
    )

    # --- 3. Construct the Full Message ---
    current_time_ms = int(time.time() * 1000)

    full_message = f"""{components['first_name']}
{components['last_name']}
{components['username']}
{components['telegram_name']}
{components['country']}
{components['phone_number']}
{components['join_date']}
{components['whatsapp_number']}

{components['score']}
{components['user_id']}
{components['password']}
{components['accounting_code']}
{components['is_registered']}
{components['is_ban']}
{components['ban_time']}
{components['chat_not_found']}
{components['new_user_alert']}
{components['stars']}
{components['is_in_eurobot']}


{components['is_in_hilfen_bot']}

{hilfen_details_section}
{components['footer_code']}
{current_time_ms}"""

    # Return Result
    return {
        "text": full_message,
        "components": components
    }
