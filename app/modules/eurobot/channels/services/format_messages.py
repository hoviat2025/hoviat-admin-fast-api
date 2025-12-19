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
    except (ValueError, TypeError):
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
        "is_ban":          f"وضعیت بن : {ban_status_val}",
        "ban_time":        f"تاریخ بن شدن : {ban_date_val}",
        "chat_not_found":  f"چت یافت نشد : {chat_not_found_val}",
        "new_user_alert":  "❗️مشتری جدید",
        "stars":           f"ستاره ها : « {stars_string} »",
        "footer_code":     f"$%^{user_id}^$%{command}"
    }

    # --- 3. Construct the Full Message ---
    # Current time in milliseconds (JS Date.now())
    current_time_ms = int(time.time() * 1000)

    full_message = f"""{components['is_registered']}
{components['first_name']}
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
{components['is_ban']}
{components['ban_time']}
{components['chat_not_found']}
{components['new_user_alert']}
{components['stars']}
{components['footer_code']}
{current_time_ms}"""

    # Return Result
    return {
        "text": full_message,
        "components": components
    }