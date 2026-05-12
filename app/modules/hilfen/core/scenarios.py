# app/modules/hilfen/core/scenarios.py
"""
Scenario checkers for Telegram updates.

These functions work on the *normalized context* (returned by context_extractor)
and return boolean values that can be used in handler `match` conditions.

Constants are defined here so they can be easily modified or moved to
environment variables later.
"""

# ---------------------------------------------------------------------------
# Configuration (eventually from settings / environment)
# ---------------------------------------------------------------------------
BOT_SELF_ID = 1                # Your bot's Telegram user ID
ADMIN_CHAT_IDS = {2, 3, 4}     # Admin user IDs
MAIN_CHANNEL_CHAT_ID = 12       # Main channel chat ID

# ---------------------------------------------------------------------------
# Chat‑type checkers
# ---------------------------------------------------------------------------
def is_private_chat(context: dict) -> bool:
    """True if the conversation is a private chat between a user and the bot."""
    return context.get("chat_type") == "private"


def is_group_chat(context: dict) -> bool:
    """True for a group or supergroup."""
    return context.get("chat_type") in ("group", "supergroup")


def is_channel(context: dict) -> bool:
    """True for a channel post."""
    return context.get("chat_type") == "channel"


# ---------------------------------------------------------------------------
# Sender + chat combination checkers
# ---------------------------------------------------------------------------
def is_user_message_in_private(context: dict) -> bool:
    """
    The message was sent by a user (not the bot) in a private chat.
    
    In a private chat the `chat_id` equals the **user's** ID, not the bot's.
    So `user_id == chat_id` only holds for messages from the actual user.
    """
    if not is_private_chat(context):
        return False
    return context.get("user_id") == context.get("chat_id")


def is_bot_message_in_main_channel(context: dict) -> bool:
    """The bot itself sent a message in the main channel."""
    return (
        context.get("user_id") == BOT_SELF_ID
        and context.get("chat_id") == MAIN_CHANNEL_CHAT_ID
    )


def is_admin_in_group(context: dict) -> bool:
    """An admin sent a message in a group chat."""
    return is_group_chat(context) and context.get("user_id") in ADMIN_CHAT_IDS


def is_bot_itself(context: dict) -> bool:
    """Any message sent by the bot (regardless of chat)."""
    return context.get("user_id") == BOT_SELF_ID


def is_album_update(context: dict) -> bool:
    """
    True if the update is part of a media album (has media_group_id)
    and has NOT already been assembled into a composite.
    """
    return (
        context.get("media_group_id") is not None
        and not context.get("is_album_composite", False)
    )


def is_album_composite(context: dict) -> bool:
    """True if this context represents an assembled album (multiple photos)."""
    return context.get("is_album_composite", False)


def is_auto_forwarded_comment(context: dict) -> bool:
    """
    True if the update is an automatically‑forwarded comment from a channel
    into its discussion group.
    """
    return (
        context.get("is_automatic_forward") is True
        and context.get("sender_chat_type") == "channel"
        and context.get("forward_origin_message_id") is not None
    )