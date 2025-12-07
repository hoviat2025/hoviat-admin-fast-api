Eurobot Module Architecture
Overview

The Eurobot Module handles all API interactions for a Telegram Bot. Unlike a standard MVC structure, this module follows a Granular Domain-Driven Design (DDD) approach.

The core philosophy is "One File, One Responsibility." We avoid monolithic service.py or router.py files. Instead, features are grouped by Domain (e.g., members), and logic is split into specific Actions (e.g., update_member_service.py).

Directory Structure

The module is organized by Domain Groups.

code
Text
download
content_copy
expand_less
app/modules/eurobot/
├── README.md                # This documentation
├── dependencies.py          # Module-specific Auth (Bot Token Validation)
├── router.py                # Main Aggregator (Mounts domain groups like 'members')
│
└── members/                 # <--- DOMAIN GROUP 1: Member Management
    ├── __init__.py
    ├── router.py            # Endpoints specifically for 'members'
    │
    ├── schemas/             # Data Transfer Objects (DTOs)
    │   ├── bot_user_dto.py       # Output Schema (Response)
    │   └── update_request.py     # Input Schema (Request Body)
    │
    └── services/            # Business Logic (One file per action)
        ├── get_member_service.py    # Logic for Reading
        └── update_member_service.py # Logic for Updating
Key Design Principles
1. Granularity & Separation

We do not put all logic into one file.

Inputs vs. Outputs: We use separate Pydantic models for Requests (update_request.py) and Responses (bot_user_dto.py). We never re-use a Database Model as a Request Schema.

Service Isolation: Each major business action gets its own file (e.g., update_member_service.py). This prevents merge conflicts and keeps cognitive load low.

2. Transaction Management

Repositories (in app/shared/) handle SQL. They do NOT commit transactions.

Services (in app/modules/) handle Business Logic. They DO commit transactions.

Flow: Service calls Repo 
→
→
 Repo returns data 
→
→
 Service validates 
→
→
 Service Commits.

3. Shared Repositories

This module does not write raw SQL if a shared capability exists. It imports repositories from app/shared/repositories/ (e.g., UserBaseRepository) to ensure consistency with the Admin Panel and other modules.

Workflow: How a Request is Processed

Request: POST /webhook/hoviat/v1/eurobot/update_member

Auth: dependencies.verify_bot_token checks the Bearer Token.

Router: members/router.py receives the request and validates it against schemas/update_request.py.

Service: The router instantiates services/update_member_service.py.

The Service calls UserBaseRepository to perform the update.

The Service checks if the user exists (Business Logic).

The Service calls db.commit() (Transaction boundary).

Response: The router returns the data using schemas/bot_user_dto.py, wrapped in the global StandardResponse.

How to Add a New Feature

Example: Adding an "Orders" feature.

Create the Domain Folder:

Create app/modules/eurobot/orders/.

Create schemas/, services/, and router.py inside it.

Define the Contract (Schemas):

Create orders/schemas/create_order_request.py (Input).

Create orders/schemas/order_response.py (Output).

Implement Logic (Services):

Create orders/services/create_order_service.py.

Inject AsyncSession. Call Shared Repositories. Handle commit().

Create the Endpoint (Router):

In orders/router.py, create the endpoint and call the Service.

Register the Group:

Import the new router in app/modules/eurobot/router.py and mount it:

code
Python
download
content_copy
expand_less
router.include_router(orders_router, tags=["Orders"], dependencies=[Depends(verify_bot_token)])
Common Gotchas

Database Connections: Always inject db: AsyncSession in the Router and pass it to the Service class.

SQLAlchemy Async: Remember that commit() clears the object state. If you need to return the object after committing, you might need await db.refresh(obj) (unless expire_on_commit=False is set in config).

Naming: Use snake_case for files and PascalCase for classes.

File: update_member_service.py

Class: UpdateMemberService