Admin User Search & Filtering Guide

This document details the usage, response structure, and architecture of the Advanced User Search endpoint. This feature allows for complex filtering, searching, sorting, and pagination across all user fields.

1. Response Structure

The API uses a standardized envelope. Pagination details are returned in the meta field, keeping the data field exclusively for the list of user objects.

A. Success Response

Status Code: 200 OK

code
JSON
download
content_copy
expand_less
{
  "data": [
    {
      "counter": 4749,
      "user_id": 100930312,
      "username": "alex_doe",
      "first_name": "Alex",
      "country": "Germany",
      "score": 50,
      "join_date": 1747691518,
      "is_ban": false,
      "updated_at": "2025-11-27T09:17:09.310Z"
      // ... other fields
    },
    { ... }
  ],
  "meta": {
    "total": 45,      // Total records matching filters
    "page": 1,        // Current page number
    "size": 20,       // Items per page
    "pages": 3        // Total pages available
  },
  "error": {}
}
B. Error Response

Status Codes: 422 (Invalid Input), 401 (Unauthorized), 403 (Forbidden).

code
JSON
download
content_copy
expand_less
{
  "data": {},
  "meta": {},
  "error": {
    "code": "INVALID_INPUT",   # Machine-readable code
    "message": "Invalid parameters" # Human-readable details
  }
}
2. API Usage Guide

Endpoint: GET /api/admin/users-management/

A. Pagination (Defaulted)

Control the number of results returned.

page: Page number (starts at 1). Default: 1.

size: Items per page. Default: 20.

Example: ?page=2&size=50

B. Global Search

Searches across username, first_name, last_name, nickname, accounting_code, phone_number, whatsapp_number, and country.

search: The term to look for. (Case-insensitive, partial match).

Example: ?search=john (Matches "John Doe", "Elton John", "Johnson", etc.)

C. Specific Field Filters

All filters below act as AND conditions.

1. Text Fields (Exact & Partial Matches)

For text fields, you can choose between an exact match or a partial "contains" search.

a) Exact Match
Use the field name directly. The value must match exactly (case-sensitive depending on DB collation).

username

first_name

last_name

nickname

country

phone_number

whatsapp_number

profile_path

Example: ?country=Germany (Finds users where country is exactly "Germany")

b) Partial Match (Contains)
Append _contains to the field name. The system automatically applies wildcards (e.g., %value%) and ignores case.

username_contains

first_name_contains

last_name_contains

nickname_contains

country_contains

phone_number_contains

whatsapp_number_contains

profile_path_contains

Example: ?country_contains=many (Matches "Germany", "Romany", etc.)

2. Exact Matches (IDs & Codes)

Must match the value exactly.

user_id (Telegram ID)

counter (Database Primary Key)

accounting_code

telegram_message_id

group_message_id

public_message_id

public_group_message_id

mode (e.g., 'none', 'active')

Example: ?user_id=7067469580

3. Boolean Flags

Accepts true, false, 1, 0.

is_ban

is_registered

chat_not_found

Example: ?is_ban=true (Show only banned users)

4. Range Filters (Numbers & Dates)

Filter by values greater than (gte) or less than (lte).

Numbers:

min_score / max_score

min_ban_time

Unix Timestamps (Integer Seconds):

joined_after_unix (e.g., 1747691518)

joined_before_unix

ISO Timestamps (DateTime strings):

updated_after / updated_before (e.g., 2024-01-01T00:00:00Z)

channel_updated_after / channel_updated_before

Example: ?min_score=100&joined_after_unix=1700000000

5. Null Checks ("Is Empty")

Use these to find records where a specific field is missing/null in the database.
Set the value to true to find nulls, false to find non-nulls.

no_user_id

no_accounting_code

no_username

no_first_name

no_last_name

no_nickname

no_phone_number

no_whatsapp_number

no_country

no_password

no_mode

no_join_date

no_profile_path

no_telegram_msg_id

no_group_msg_id

no_public_msg_id

no_public_group_msg_id

no_channel_update

Example: ?no_country=true (List users with no country set)

D. Sorting

Control the order of results.

order_by: Field name.

Prefix with - for Descending (Newest/Highest first).

No prefix for Ascending.

Default: -counter (Newest users first)

Valid Sort Fields: counter, user_id, score, join_date, updated_at, etc.

Example: ?order_by=-score (Highest score first)

3. Implementation Details

This feature follows the Screaming Architecture pattern, separating filtering logic from standard CRUD.

Relevant Files

Filter Definition: app/modules/admin/users_management/filters/user_filter.py

Defines the aliases (e.g., min_score -> score__gte).

Defines separate fields for exact matches (username) and partial matches (username__ilike alias username_contains).

Contains a validator to automatically wrap _contains text searches in %.

Repository: app/modules/admin/users_management/repositories/user_search.py

Extends UserBaseRepository.

Manually builds the Global Search (OR logic) and applies the Filter (AND logic).

Service: app/modules/admin/users_management/services/user_service.py

Calls the repo and formats the raw result into { items: [...], pagination: {...} }.

Router: app/modules/admin/users_management/router.py

Splits the service result into the standard API response format (Data vs Meta).