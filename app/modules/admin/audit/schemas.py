from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: int
    admin_id: int
    admin_username: str
    action: str
    target_type: str
    target_id: str
    changes: Dict[str, Any]
    sync_channels: Optional[bool] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditPaginationMeta(BaseModel):
    total: int
    page: int
    size: int
    pages: int


AuditLogList = List[AuditLogResponse]
