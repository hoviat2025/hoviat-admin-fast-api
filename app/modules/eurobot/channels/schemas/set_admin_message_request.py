from pydantic import BaseModel, ConfigDict

class ExternalReply(BaseModel):
    # Used to lookup the user (The ID of the post in Main Channel)
    message_id: int

class ForwardOrigin(BaseModel):
    # Maps to admin_message_id
    message_id: int

class Message(BaseModel):
    # Maps to admin_group_message_id
    message_id: int
    forward_origin: ForwardOrigin
    external_reply: ExternalReply

class OriginalUpdate(BaseModel):
    message: Message

class SetAdminMessageRequest(BaseModel):
    original_update: OriginalUpdate

    # Ignore extra fields from Telegram
    model_config = ConfigDict(extra='ignore')
