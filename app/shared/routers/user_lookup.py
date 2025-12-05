from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.shared.repositories.user_base import UserBaseRepository
from app.shared.schemas import SharedUserResponse
from app.shared.dependencies import verify_shared_auth

router = APIRouter()

@router.get(
    "/users/{user_id}", 
    response_model=SharedUserResponse,
    summary="Get Full User Info",
    description="Returns the complete user row. Requires Admin JWT or Eurobot Token."
)
async def get_user_by_id(
    user_id: int = Path(..., description="The Telegram User ID"),
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(verify_shared_auth) 
):
    repo = UserBaseRepository(db)
    user = await repo.get_by_id(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        
    return user