from pydantic import BaseModel, ConfigDict, BeforeValidator
from typing import Optional, Any, Annotated

def force_to_string(v: Any) -> Optional[str]:
    """
    Helper validator to coerce integer values into strings.
    
    This is necessary because some clients (e.g., JavaScript environments) cannot 
    safely handle 64-bit integers (Telegram IDs). Converting them to strings 
    prevents precision loss and ensures backward compatibility with legacy parsers.
    """
    if v is None:
        return None
    return str(v)

# Custom type alias to enforce string serialization for numeric IDs
StringifiedInt = Annotated[str, BeforeValidator(force_to_string)]

class QuoteReplyInfoResponse(BaseModel):
    """
    Schema for the Quote Reply info.
    
    Note: All message and channel IDs are typed as `StringifiedInt` to output 
    strings in the JSON response, regardless of the database storage type.
    """
    channel_message_id: Optional[StringifiedInt] = None
    channel_id: Optional[StringifiedInt] = None
    
    group_message_id: Optional[StringifiedInt] = None
    group_id: Optional[StringifiedInt] = None
    
    public_group_message_id: Optional[StringifiedInt] = None
    public_group_id: Optional[StringifiedInt] = None
    
    public_message_id: Optional[StringifiedInt] = None
    public_channel_id: Optional[StringifiedInt] = None

    model_config = ConfigDict(
        # 'extra="allow"' is enabled here to support dynamic fields generated 
        # at runtime (e.g., localized strings like "first_name": "نام : بردیا") 
        # that are not explicitly defined in the class attributes.
        extra='allow',
        from_attributes=True
    )