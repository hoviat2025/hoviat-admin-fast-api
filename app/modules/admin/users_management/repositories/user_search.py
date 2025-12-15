from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from typing import Optional, List, Tuple

from app.models.user import User
from app.shared.repositories.user_base import UserBaseRepository
from app.modules.admin.users_management.filters.user_filter import UserFilter

class UserSearchRepository(UserBaseRepository):

    async def search_users(
        self, 
        user_filter: UserFilter, 
        search_query: Optional[str],
        page: int, 
        page_size: int
    ) -> Tuple[List[User], int]:
        
        # --- DEBUG LOG ---
        # Useful to verify if exact match vs contains match is triggering correctly
        print(f"DEBUG: Global Search: {search_query}")
        print(f"DEBUG: Filter Dict: {user_filter.model_dump(exclude_unset=True)}")
        # -----------------

        stmt = select(User)

        # 1. Apply Universal Search (OR Logic)
        # This allows searching across multiple columns simultaneously without knowing specific field names.
        if search_query:
            term = f"%{search_query}%"
            stmt = stmt.where(
                or_(
                    User.username.ilike(term),
                    User.first_name.ilike(term),
                    User.last_name.ilike(term),
                    User.nickname.ilike(term),
                    User.accounting_code.ilike(term),
                    User.phone_number.ilike(term),
                    User.country.ilike(term)
                )
            )

        # 2. Apply Specific Filters (AND Logic)
        # This applies the exact matches, ranges, and 'contains' logic defined in UserFilter
        stmt = user_filter.filter(stmt)
        
        # 3. Apply Sorting
        stmt = user_filter.sort(stmt)

        # 4. Pagination
        # Calculate total count before applying limit/offset
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total_count = total_result.scalar_one()

        offset = (page - 1) * page_size
        stmt = stmt.limit(page_size).offset(offset)

        result = await self.db.execute(stmt)
        users = result.scalars().all()

        return users, total_count