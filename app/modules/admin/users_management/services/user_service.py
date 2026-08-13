import logging
from fastapi import status
from typing import Dict, Any

from app.core.exceptions import ServiceError
from app.shared.repositories.user_base import UserBaseRepository
from app.modules.admin.users_management.schemas.get_user import FullUserResponse
from app.modules.admin.users_management.schemas.update_user import UpdateUserRequest
from app.modules.admin.users_management.repositories.user_search import UserSearchRepository
from app.modules.admin.users_management.filters.user_filter import UserFilter
from app.shared.repositories.job_queue import JobQueueRepository
from app.models.admin import Admin
from app.modules.admin.audit.repository import AdminAuditRepository

logger = logging.getLogger(__name__)

class UserManagementService:
    def __init__(self, user_repo: UserSearchRepository):
        self.user_repo = user_repo

    async def fetch_user_by_id(self, user_id: int) -> FullUserResponse:
        user = await self.user_repo.get_by_id(user_id)
        
        if not user:
            raise ServiceError(
                code="USER_NOT_FOUND",
                message=f"User with ID {user_id} not found.",
                status_code=status.HTTP_404_NOT_FOUND
            )
            
        return user

    async def update_user(
        self,
        payload: UpdateUserRequest,
        sync_channels: bool = True,
        admin: Admin | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> FullUserResponse:
        """
        Updates a user based on user_id.
        """
        # 1. Read the current row so the audit record can contain before/after values.
        current_user = await self.user_repo.get_by_id_for_update(payload.user_id)
        if not current_user:
            raise ServiceError(
                code="USER_NOT_FOUND",
                message=f"Cannot update: User with ID {payload.user_id} not found.",
                status_code=status.HTTP_404_NOT_FOUND
            )

        # 2. Prepare data
        update_data = payload.model_dump(exclude_unset=True)
        
        if 'user_id' in update_data:
            del update_data['user_id']

        # SQLAlchemy may synchronize the already-loaded ORM object when the
        # UPDATE statement runs, so copy the original values before updating.
        before_values = {
            field: getattr(current_user, field)
            for field in update_data
        }

        # 3. Update
        updated_user = await self.user_repo.update(payload.user_id, update_data)

        # 4. Check
        if not updated_user:
            raise ServiceError(
                code="USER_NOT_FOUND",
                message=f"Cannot update: User with ID {payload.user_id} not found.",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # 5. Record the audit event in the same transaction as the user update.
        if admin is None:
            raise ServiceError(
                code="AUDIT_ADMIN_REQUIRED",
                message="An authenticated administrator is required for user updates.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        changes = {}
        for field in update_data:
            before = before_values[field]
            after = getattr(updated_user, field)
            if before != after:
                if field == "password":
                    changes[field] = {"before": "[REDACTED]", "after": "[REDACTED]"}
                else:
                    changes[field] = {"before": before, "after": after}

        audit_repo = AdminAuditRepository(self.user_repo.db)
        await audit_repo.record_user_update(
            admin_id=admin.id,
            admin_username=admin.username,
            user_id=updated_user.user_id,
            changes=changes,
            sync_channels=sync_channels,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # 6. Commit user update and audit record together.
        await self.user_repo.db.commit()

        # Queue synchronization is enabled by default and can be explicitly
        # disabled by the caller with sync_channels=false.
        # The user update is already committed, so a queue failure must not
        # turn a successful admin edit into a failed request.
        if sync_channels:
            if updated_user.is_in_eurobot and updated_user.is_in_hilfen_bot:
                source = "both"
            elif updated_user.is_in_hilfen_bot:
                source = "hilfenbot"
            else:
                source = "eurobot"

            try:
                queue_repo = JobQueueRepository(self.user_repo.db)
                await queue_repo.enqueue_medium_priority(
                    user_id=updated_user.user_id,
                    source=source,
                )
            except Exception:
                logger.exception(
                    "Admin user update succeeded, but channel synchronization "
                    "could not be queued (user_id=%s, source=%s)",
                    updated_user.user_id,
                    source,
                )
        
        return updated_user
    
    async def list_users(
        self, 
        user_filter: UserFilter, 
        search: str | None, 
        page: int, 
        size: int
    ) -> Dict[str, Any]:
        """
        Returns a dictionary containing the items and pagination stats.
        The Router will be responsible for splitting this into 'data' and 'meta'.
        """
        users, total = await self.user_repo.search_users(
            user_filter=user_filter,
            search_query=search,
            page=page,
            page_size=size
        )
        
        return {
            "items": users,
            "pagination": {
                "total": total,
                "page": page,
                "size": size,
                "pages": (total + size - 1) // size 
            }
        }
