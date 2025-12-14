from fastapi import Depends
from app.modules.admin.repositories.admin import AdminRepository
from app.modules.admin.dependencies import get_admin_repository
from app.modules.admin.auth.services.login import LoginService

def get_login_service(
    repo: AdminRepository = Depends(get_admin_repository)
) -> LoginService:
    """
    Injects the Repo into the LoginService.
    """
    return LoginService(repo)