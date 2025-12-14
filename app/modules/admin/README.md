Admin Module Architecture & Contribution Guide

This document outlines the architectural standards, folder structure, and development workflow for the Admin Module.

Architecture Style: Feature-Based / Screaming Architecture.
Pattern: Router -> Dependency Injection -> Service -> Repository -> Database.

1. Folder Structure

We organize code by Feature, not by file type.

code
Text
download
content_copy
expand_less
app/modules/admin/
├── dependencies.py             # GLOBAL Admin Dependencies (Auth, Permissions, Repo Providers)
├── router.py                   # Main Router that gathers all feature routers
├── repositories/               # DATA ACCESS Layer (Specific to Admin Tables)
│   ├── admin.py
│   └── ...
└── {FEATURE_NAME}/             # e.g., 'auth' or 'users_management'
    ├── router.py               # CONTROLLER: Endpoints definition
    ├── dependencies.py         # WIRING: Injects Repositories into Services
    ├── services/               # LOGIC: Business rules, password checks, formatting
    │   └── {specific_logic}.py
    ├── schemas/                # DTOs: Pydantic models for Input/Output
    │   └── {specific_usage}.py
    └── repositories/           # (OPTIONAL) Feature-specific queries extending shared repos
        └── {extended_repo}.py
2. Naming Conventions

Folders: Snake_case, descriptive of the feature (e.g., users_management, not users).

Files: Descriptive of the specific content, not generic layer names.

❌ schemas/response.py (Too generic)

✅ schemas/get_user.py (Clear intent)

❌ services/logic.py

✅ services/user_service.py

Classes: PascalCase.

UserManagementService

AdminRepository

3. How to Add a New Endpoint

Follow this flow to add a new feature.

Step 1: Schemas (Data Transfer)

Define what you receive and what you return.

Location: admin/{feature}/schemas/ban_user.py

Response: Always design the schema for the data portion of the response.

Step 2: Repositories (Data Access)

This is where we decide Shared vs. Specific.

Scenario A: Generic Operation (CRUD)

If you just need get_by_id, create, or update on a shared table (like Users).

Action: Use app/shared/repositories/user_base.py.

Scenario B: Feature-Specific Query

If you need a complex query specific to this feature (e.g., "Find users with even IDs" or "Analytics stats").

Action: Create a new repository in your feature folder that Inherits from the base.

Location: admin/{feature}/repositories/user_analytics_repo.py

Code:

code
Python
download
content_copy
expand_less
from app.shared.repositories.user_base import UserBaseRepository

class UserAnalyticsRepository(UserBaseRepository):
    async def get_complex_stats(self):
        # ... custom SQL here ...
Step 3: Service (Business Logic)

Write the logic.

Location: admin/{feature}/services/{action}.py

Rule:

Raise ServiceError for failures.

Return Pydantic models or ORM objects.

Step 4: Feature Dependencies (The Wiring)

Connect the Repository to the Service.

Location: admin/{feature}/dependencies.py

Pattern:

code
Python
download
content_copy
expand_less
# Example 1: Using Shared Repo
def get_user_service(repo: UserBaseRepository = Depends(get_user_base_repository)):
    return UserService(repo)

# Example 2: Using Extended Specific Repo
def get_analytics_repo(db: AsyncSession = Depends(get_db)):
    return UserAnalyticsRepository(db)
Step 5: Router (The Controller)

Define the endpoint.

Location: admin/{feature}/router.py

Standardization:

Use StandardResponse[Schema] as response_model.

Return StandardResponse.success(result).

Add Security Dependencies here.

4. Standard Responses & Errors

We use a global wrapper to ensure consistency.

Returning Success

Wrap your data in StandardResponse.

code
Python
download
content_copy
expand_less
from app.core.schemas import StandardResponse

@router.get("/", response_model=StandardResponse[MySchema])
async def my_endpoint(service: MyService = Depends(...)):
    result = await service.do_work()
    return StandardResponse.success(result)
Raising Errors

Do not use HTTPException in Services. Use ServiceError.

code
Python
download
content_copy
expand_less
from app.core.exceptions import ServiceError
from fastapi import status

if something_wrong:
    raise ServiceError(
        code="USER_ALREADY_EXISTS",   # Machine readable string
        message="This user is already registered.", # Human readable
        status_code=status.HTTP_409_CONFLICT
    )
5. Security & Dependencies

We have two levels of dependencies.

Level 1: Global Admin Dependencies

File: app/modules/admin/dependencies.py
Use these to secure routes.

Authentication: get_current_admin

Decodes JWT.

Checks DB: Ensures Admin exists and is active.

Usage: Added to the router level in admin/router.py.

Authorization: e.g., require_read_users_permission

Checks flags (is_superadmin, has_all_rights).

Usage: Added to specific endpoints or sub-routers.

code
Python
download
content_copy
expand_less
@router.get("/", dependencies=[Depends(require_read_users_permission)])
Level 2: Feature Dependencies

File: app/modules/admin/{feature}/dependencies.py
Use these to inject Services into Routers.