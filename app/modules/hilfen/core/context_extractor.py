def extract_context(update: dict) -> dict:
    """
    Normalize Telegram update payloads into a unified context object.

    Telegram updates may represent different event types such as messages,
    edited messages, callback queries, or contact sharing. This function 
    extracts the minimal common fields required by handlers.

    The dispatcher relies on this structure.
    """

    context = {
        "update_id": update.get("update_id"),
        "user_id": None,
        "chat_id": None,
        "chat_type": None,        # "private", "group", "supergroup", "channel" ...
        "text": None,
        "is_bot": False,
        "update_type": "unknown",
        "user_state": None,
        "username": None,
        "first_name": None,
        "last_name": None,
        "contact": None,
    }

    if "message" in update:
        msg = update["message"]
        chat_obj = msg.get("chat", {})

        context["update_type"] = "message"
        context["user_id"] = msg.get("from", {}).get("id")
        context["is_bot"] = msg.get("from", {}).get("is_bot", False)
        context["chat_id"] = chat_obj.get("id")
        context["chat_type"] = chat_obj.get("type")
        context["text"] = msg.get("text")

        # User profile data
        from_user = msg.get("from", {})
        context["username"] = from_user.get("username")
        context["first_name"] = from_user.get("first_name")
        context["last_name"] = from_user.get("last_name")

        # Shared contact
        context["contact"] = msg.get("contact")

    elif "edited_message" in update:
        msg = update["edited_message"]
        chat_obj = msg.get("chat", {})

        context["update_type"] = "edited_message"
        context["user_id"] = msg.get("from", {}).get("id")
        context["is_bot"] = msg.get("from", {}).get("is_bot", False)
        context["chat_id"] = chat_obj.get("id")
        context["chat_type"] = chat_obj.get("type")
        context["text"] = msg.get("text")

        from_user = msg.get("from", {})
        context["username"] = from_user.get("username")
        context["first_name"] = from_user.get("first_name")
        context["last_name"] = from_user.get("last_name")

    elif "callback_query" in update:
        cb = update["callback_query"]
        msg = cb.get("message", {})
        chat_obj = msg.get("chat", {})

        context["update_type"] = "callback_query"
        context["user_id"] = cb.get("from", {}).get("id")
        context["is_bot"] = cb.get("from", {}).get("is_bot", False)
        context["chat_id"] = chat_obj.get("id")
        context["chat_type"] = chat_obj.get("type")
        context["text"] = cb.get("data")

        from_user = cb.get("from", {})
        context["username"] = from_user.get("username")
        context["first_name"] = from_user.get("first_name")
        context["last_name"] = from_user.get("last_name")

    return context
