# app/modules/hilfen/core/context_extractor.py
def extract_context(update: dict) -> dict:
    """
    Normalize Telegram update payloads into a unified context object.

    Extracts fields common to all handlers: user info, chat info, text,
    contact, photo array, media_group_id (for albums), and a flag indicating
    whether this update is an assembled album composite.
    """

    context = {
        "update_id": update.get("update_id"),
        "user_id": None,
        "chat_id": None,
        "chat_type": None,
        "text": None,
        "is_bot": False,
        "update_type": "unknown",
        "user_state": None,
        "username": None,
        "first_name": None,
        "last_name": None,
        "contact": None,
        "photo": None,
        "media_group_id": None,
        "is_album_composite": False,
        "album_photos": None,
        "reply_to_message_id": None,
        "message_id": None,                    # <-- new
        # Auto‑forwarded comment fields
        "is_automatic_forward": False,
        "sender_chat_id": None,
        "sender_chat_type": None,
        "forward_origin_message_id": None,
    }

    # ---- message ----
    if "message" in update:
        msg = update["message"]
        chat_obj = msg.get("chat", {})

        context["update_type"] = "message"
        context["user_id"] = msg.get("from", {}).get("id")
        context["is_bot"] = msg.get("from", {}).get("is_bot", False)
        context["chat_id"] = chat_obj.get("id")
        context["chat_type"] = chat_obj.get("type")
        context["text"] = msg.get("text")
        context["username"] = msg.get("from", {}).get("username")
        context["first_name"] = msg.get("from", {}).get("first_name")
        context["last_name"] = msg.get("from", {}).get("last_name")
        context["contact"] = msg.get("contact")
        context["photo"] = msg.get("photo")
        context["media_group_id"] = msg.get("media_group_id")
        context["is_album_composite"] = msg.get("is_album_composite", False)
        context["album_photos"] = msg.get("album_photos")
        context["message_id"] = msg.get("message_id")

        reply_msg = msg.get("reply_to_message")
        if reply_msg:
            context["reply_to_message_id"] = reply_msg.get("message_id")

        context["is_automatic_forward"] = msg.get("is_automatic_forward", False)
        sender_chat = msg.get("sender_chat")
        if sender_chat:
            context["sender_chat_id"] = sender_chat.get("id")
            context["sender_chat_type"] = sender_chat.get("type")
        forward_origin = msg.get("forward_origin")
        if forward_origin and isinstance(forward_origin, dict):
            context["forward_origin_message_id"] = forward_origin.get("message_id")

    # ---- edited_message ----
    elif "edited_message" in update:
        msg = update["edited_message"]
        chat_obj = msg.get("chat", {})

        context["update_type"] = "edited_message"
        context["user_id"] = msg.get("from", {}).get("id")
        context["is_bot"] = msg.get("from", {}).get("is_bot", False)
        context["chat_id"] = chat_obj.get("id")
        context["chat_type"] = chat_obj.get("type")
        context["text"] = msg.get("text")
        context["username"] = msg.get("from", {}).get("username")
        context["first_name"] = msg.get("from", {}).get("first_name")
        context["last_name"] = msg.get("from", {}).get("last_name")
        context["photo"] = msg.get("photo")
        context["media_group_id"] = msg.get("media_group_id")
        context["is_album_composite"] = msg.get("is_album_composite", False)
        context["album_photos"] = msg.get("album_photos")
        context["message_id"] = msg.get("message_id")

        reply_msg = msg.get("reply_to_message")
        if reply_msg:
            context["reply_to_message_id"] = reply_msg.get("message_id")

        context["is_automatic_forward"] = msg.get("is_automatic_forward", False)
        sender_chat = msg.get("sender_chat")
        if sender_chat:
            context["sender_chat_id"] = sender_chat.get("id")
            context["sender_chat_type"] = sender_chat.get("type")
        forward_origin = msg.get("forward_origin")
        if forward_origin and isinstance(forward_origin, dict):
            context["forward_origin_message_id"] = forward_origin.get("message_id")

    # ---- callback_query ----
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
        context["username"] = cb.get("from", {}).get("username")
        context["first_name"] = cb.get("from", {}).get("first_name")
        context["last_name"] = cb.get("from", {}).get("last_name")

    return context