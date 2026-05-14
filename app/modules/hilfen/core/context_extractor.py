# app/modules/hilfen/core/context_extractor.py
def extract_context(update: dict) -> dict:
    """
    Normalize Telegram update payloads into a unified context object.

    Extracts fields common to all handlers: user info, chat info, text,
    contact, photo array, media_group_id (for albums), external reply info,
    and a flag indicating whether this update is an assembled album composite.
    Handles message, edited_message, channel_post, and callback_query updates.
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
        "message_id": None,
        # Auto‑forwarded comment fields
        "is_automatic_forward": False,
        "sender_chat_id": None,
        "sender_chat_type": None,
        "forward_origin_message_id": None,
        # Extra text from callback_query's replied message (admin preview edits)
        "callback_query_reply_text": None,
        # ID of an externally replied message (e.g. channel comment reply)
        "external_reply_message_id": None,
        # Signature of the admin who posted on behalf of the channel
        "author_signature": None,
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

        # External reply (e.g. linked channel comment)
        external_reply = msg.get("external_reply")
        if external_reply and isinstance(external_reply, dict):
            context["external_reply_message_id"] = external_reply.get("message_id")

        context["is_automatic_forward"] = msg.get("is_automatic_forward", False)
        sender_chat = msg.get("sender_chat")
        if sender_chat:
            context["sender_chat_id"] = sender_chat.get("id")
            context["sender_chat_type"] = sender_chat.get("type")
        forward_origin = msg.get("forward_origin")
        if forward_origin and isinstance(forward_origin, dict):
            context["forward_origin_message_id"] = forward_origin.get("message_id")

        author_sig = msg.get("author_signature")
        if author_sig:
            context["author_signature"] = author_sig

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

        external_reply = msg.get("external_reply")
        if external_reply and isinstance(external_reply, dict):
            context["external_reply_message_id"] = external_reply.get("message_id")

        context["is_automatic_forward"] = msg.get("is_automatic_forward", False)
        sender_chat = msg.get("sender_chat")
        if sender_chat:
            context["sender_chat_id"] = sender_chat.get("id")
            context["sender_chat_type"] = sender_chat.get("type")
        forward_origin = msg.get("forward_origin")
        if forward_origin and isinstance(forward_origin, dict):
            context["forward_origin_message_id"] = forward_origin.get("message_id")

        author_sig = msg.get("author_signature")
        if author_sig:
            context["author_signature"] = author_sig

    # ---- channel_post ----
    elif "channel_post" in update:
        msg = update["channel_post"]
        chat_obj = msg.get("chat", {})

        context["update_type"] = "channel_post"
        context["user_id"] = msg.get("from", {}).get("id")
        context["is_bot"] = msg.get("from", {}).get("is_bot", False)
        context["chat_id"] = chat_obj.get("id")
        context["chat_type"] = chat_obj.get("type")
        context["text"] = msg.get("text")
        context["username"] = msg.get("from", {}).get("username")
        context["first_name"] = msg.get("from", {}).get("first_name")
        context["last_name"] = msg.get("from", {}).get("last_name")
        context["message_id"] = msg.get("message_id")

        reply_msg = msg.get("reply_to_message")
        if reply_msg:
            context["reply_to_message_id"] = reply_msg.get("message_id")

        external_reply = msg.get("external_reply")
        if external_reply and isinstance(external_reply, dict):
            context["external_reply_message_id"] = external_reply.get("message_id")

        # channel_post may have is_automatic_forward? Usually not, but handle.
        context["is_automatic_forward"] = msg.get("is_automatic_forward", False)
        sender_chat = msg.get("sender_chat")
        if sender_chat:
            context["sender_chat_id"] = sender_chat.get("id")
            context["sender_chat_type"] = sender_chat.get("type")
        forward_origin = msg.get("forward_origin")
        if forward_origin and isinstance(forward_origin, dict):
            context["forward_origin_message_id"] = forward_origin.get("message_id")

        author_sig = msg.get("author_signature")
        if author_sig:
            context["author_signature"] = author_sig

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

        # Expose the text/caption of the message that the callback button was
        # attached to (i.e. the admin handler message's reply‑to preview).
        # This allows the confirm handler to pick up admin edits.
        reply_msg = msg.get("reply_to_message")
        if reply_msg:
            reply_text = reply_msg.get("text") or reply_msg.get("caption")
            if reply_text:
                context["callback_query_reply_text"] = reply_text

        # If the callback message itself has an external reply, surface its id.
        external_reply = msg.get("external_reply")
        if external_reply and isinstance(external_reply, dict):
            context["external_reply_message_id"] = external_reply.get("message_id")

        author_sig = msg.get("author_signature")
        if author_sig:
            context["author_signature"] = author_sig

    return context