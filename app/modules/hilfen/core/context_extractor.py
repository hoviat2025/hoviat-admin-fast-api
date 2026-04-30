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

        context["update_type"] = "message"
        context["user_id"] = msg.get("from", {}).get("id")
        context["is_bot"] = msg.get("from", {}).get("is_bot", False)
        context["chat_id"] = msg.get("chat", {}).get("id")
        context["text"] = msg.get("text")
        
        # Extract user profile information
        from_user = msg.get("from", {})
        context["username"] = from_user.get("username")
        context["first_name"] = from_user.get("first_name")
        context["last_name"] = from_user.get("last_name")
        
        # Extract contact if shared
        context["contact"] = msg.get("contact")

    elif "edited_message" in update:
        msg = update["edited_message"]

        context["update_type"] = "edited_message"
        context["user_id"] = msg.get("from", {}).get("id")
        context["is_bot"] = msg.get("from", {}).get("is_bot", False)
        context["chat_id"] = msg.get("chat", {}).get("id")
        context["text"] = msg.get("text")
        
        # Extract user profile information
        from_user = msg.get("from", {})
        context["username"] = from_user.get("username")
        context["first_name"] = from_user.get("first_name")
        context["last_name"] = from_user.get("last_name")

    elif "callback_query" in update:
        cb = update["callback_query"]

        context["update_type"] = "callback_query"
        context["user_id"] = cb.get("from", {}).get("id")
        context["is_bot"] = cb.get("from", {}).get("is_bot", False)
        context["chat_id"] = cb.get("message", {}).get("chat", {}).get("id")
        context["text"] = cb.get("data")
        
        # Extract user profile information
        from_user = cb.get("from", {})
        context["username"] = from_user.get("username")
        context["first_name"] = from_user.get("first_name")
        context["last_name"] = from_user.get("last_name")

    return context
