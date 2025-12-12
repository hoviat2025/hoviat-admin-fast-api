from pydantic import BaseModel, ConfigDict, Field

class ForwardOrigin(BaseModel):
    # Maps to: original_update.message.forward_origin.message_id
    message_id: int

class Message(BaseModel):
    # Maps to: original_update.message.message_id
    message_id: int
    forward_origin: ForwardOrigin

class OriginalUpdate(BaseModel):
    message: Message

class SetGroupMessageRequest(BaseModel):
    extracted_user_id: int
    original_update: OriginalUpdate

    # extra='ignore' ensures the API doesn't crash if Telegram sends 
    # new/unexpected fields in the update object.
    model_config = ConfigDict(extra='ignore')