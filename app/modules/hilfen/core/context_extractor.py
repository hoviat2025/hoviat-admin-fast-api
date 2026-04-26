def extract_context(update: dict) -> dict:
    """
    Normalize Telegram update payloads into a unified context object.

    Telegram updates may represent different event types such as messages,
    edited messages, or callback queries. This function extracts the
    minimal common fields required by handlers.

    The dispatcher relies on this structure.
    """

    context = {
        "update_id": update.get("update_id"),
        "user_id": None,
        "chat_id": None,
        "text": None,
        "is_bot": False,
        "update_type": "unknown",
        "user_state": None,
    }

    if "message" in update:
        msg = update["message"]

        context["update_type"] = "message"
        context["user_id"] = msg.get("from", {}).get("id")
        context["is_bot"] = msg.get("from", {}).get("is_bot", False)
        context["chat_id"] = msg.get("chat", {}).get("id")
        context["text"] = msg.get("text")

    elif "edited_message" in update:
        msg = update["edited_message"]

        context["update_type"] = "edited_message"
        context["user_id"] = msg.get("from", {}).get("id")
        context["is_bot"] = msg.get("from", {}).get("is_bot", False)
        context["chat_id"] = msg.get("chat", {}).get("id")
        context["text"] = msg.get("text")

    elif "callback_query" in update:
        cb = update["callback_query"]

        context["update_type"] = "callback_query"
        context["user_id"] = cb.get("from", {}).get("id")
        context["is_bot"] = cb.get("from", {}).get("is_bot", False)
        context["chat_id"] = cb.get("message", {}).get("chat", {}).get("id")
        context["text"] = cb.get("data")

    return context
