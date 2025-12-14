# Admin Module - Authentication Feature

This document explains the architecture of the Admin Authentication system.
The system uses a **Feature-Based** file structure.

## File Structure & Responsibilities

### 1. Repository Layer (`repositories/admin.py`)
*   **Purpose:** Maps strictly to the Database Table (`admins`).
*   **Role:** Performs raw SQL queries. It does not know about JWTs or HTTP errors.
*   **Key Methods:** `get_by_username` (for login), `get_by_id` (for session validation).

### 2. Shared Dependencies (`dependencies.py`)
*   **Purpose:** Security and Common Tools.
*   **Key Function:** `get_current_admin`.
    *   This function runs on **every** protected request.
    *   It decodes the JWT.
    *   **Crucial:** It queries the DB to ensure the Admin still exists and `is_active=True`.
    *   If you ban an admin, they are blocked immediately, not when the token expires.

### 3. Auth Feature Folder (`auth/`)
Everything related to Authentication is self-contained here.

*   **`schemas/login.py`**: Defines the data shape for the Login response (Token + basic info).
*   **`services/login.py`**: Contains `LoginService`. This handles the actual business logic:
    *   Verifying Argon2 passwords.
    *   Checking account status.
    *   Generating 7-day JWTs.
*   **`dependencies.py`**: Dependency Injection factory. It constructs the `LoginService` by giving it the `AdminRepository`.
*   **`router.py`**: The HTTP Interface. It receives the request and calls the Service.

## Usage

**Login Flow:**
1. POST to `/api/admin/auth/login` with `username` and `password`.
2. Receive `access_token`.
3. Use header `Authorization: Bearer <access_token>` for future requests.