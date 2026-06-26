# app/modules/eurobot/channels/schemas/set_hilfen_message_request.py
from pydantic import BaseModel, ConfigDict

class ExternalReply(BaseModel):
    # Used to lookup the user (The ID of the post in the Main Channel)
    message_id: int

class ForwardOrigin(BaseModel):
    # Maps to hilfen_message_id
    message_id: int

class Message(BaseModel):
    # Maps to hilfen_group_message_id
    message_id: int
    forward_origin: ForwardOrigin
    external_reply: ExternalReply

class OriginalUpdate(BaseModel):
    message: Message

class SetHilfenMessageRequest(BaseModel):
    original_update: OriginalUpdate

    # Ignore extra fields from Telegram to ensure API stability
    model_config = ConfigDict(extra='ignore')