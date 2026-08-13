from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_audit_log import AdminAuditLog


class AdminAuditRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_user_update(
        self,
        *,
        admin_id: int,
        admin_username: str,
        user_id: int,
        changes: dict,
        sync_channels: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AdminAuditLog:
        audit_log = AdminAuditLog(
            admin_id=admin_id,
            admin_username=admin_username,
            action="user.update",
            target_type="user",
            target_id=str(user_id),
            changes=jsonable_encoder(changes),
            sync_channels=sync_channels,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(audit_log)
        await self.db.flush()
        return audit_log

    async def list_logs(
        self,
        *,
        page: int,
        size: int,
        admin_id: int | None = None,
        admin_username: str | None = None,
        target_user_id: int | None = None,
        action: str | None = None,
        changed_field: str | None = None,
        created_after=None,
        created_before=None,
        sync_channels: bool | None = None,
    ) -> tuple[list[AdminAuditLog], int]:
        stmt = select(AdminAuditLog)

        if admin_id is not None:
            stmt = stmt.where(AdminAuditLog.admin_id == admin_id)
        if admin_username:
            stmt = stmt.where(AdminAuditLog.admin_username.ilike(f"%{admin_username}%"))
        if target_user_id is not None:
            stmt = stmt.where(AdminAuditLog.target_id == str(target_user_id))
        if action:
            stmt = stmt.where(AdminAuditLog.action == action)
        if changed_field:
            stmt = stmt.where(AdminAuditLog.changes.has_key(changed_field))
        if created_after is not None:
            stmt = stmt.where(AdminAuditLog.created_at >= created_after)
        if created_before is not None:
            stmt = stmt.where(AdminAuditLog.created_at <= created_before)
        if sync_channels is not None:
            stmt = stmt.where(AdminAuditLog.sync_channels == sync_channels)

        count_result = await self.db.execute(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            stmt.order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc())
            .limit(size)
            .offset((page - 1) * size)
        )
        return result.scalars().all(), total

    async def get_by_id(self, audit_id: int) -> AdminAuditLog | None:
        return await self.db.get(AdminAuditLog, audit_id)
