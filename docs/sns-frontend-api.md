# SNS Frontend API Guide

Everything the web frontend needs to integrate with the SNS (user panel) API:
login, profiles, search, account management, and bookmarks.

---

## 1. Base URL & Conventions

```
Base URL (staging): https://staging.185.202.113.95.nip.io/api/sns
```

Every response uses the same JSON envelope:

```json
{
  "data": { ... },     // the payload; null on errors
  "meta":  { ... },    // auxiliary info (pagination totals, etc.)
  "error": {}          // empty object on success; details on failure
}
```

### Error format

On failure, `error` contains a machine-readable code and a human message:

```json
{
  "data": null,
  "meta": {},
  "error": {
    "code": "INVALID_LOGIN_TOKEN",
    "message": "Login token is invalid, expired, or already used."
  }
}
```

Common codes you should handle:

| HTTP | code | Meaning |
|---|---|---|
| 400 | `INVALID_INPUT` | Request body/query failed validation |
| 401 | `UNAUTHORIZED` / `INVALID_LOGIN_TOKEN` | Missing/expired JWT or bad login code |
| 403 | `FORBIDDEN` / `Account is banned` | Banned account or bad credentials |
| 404 | `NOT_FOUND` / `USER_NOT_FOUND` | Unknown route, user, or hidden profile |
| 409 | `CONFLICT_OCCURRED` | Uniqueness conflict |
| 429 | `RATE_LIMITED` | Too many requests - slow down |
| 500 | `INTERNAL_SERVER_ERROR` | Our fault; retry later |

### Rate limits (per IP unless noted)

| Endpoints | Limit |
|---|---|
| `POST /auth/exchange-token` | 10 / minute |
| `GET /profiles/search` | 60 / minute |
| `GET /profiles/{user_id}` | 60 / minute |
| `POST/DELETE /me/profile-picture` | 10 / hour per user, 20 / hour per IP |

A `429` response body says `"Rate limit exceeded. Please slow down."`

---

## 2. Authentication (Login via Bot Code)

There are no passwords. Users log in with a one-time code they receive from
the Telegram bot:

```
User opens website → clicks "Login" → site shows "enter your code"
User opens Telegram bot → presses «ورود به سایت» → bot sends a code
User types the code into the website → website exchanges it for a JWT
```

The frontend only participates in the **last step**.

### Exchange the code

```
POST /auth/exchange-token
Content-Type: application/json

{ "token": "<32-character-code-from-the-bot>" }
```

Success (`200`):

```json
{
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "user_id": 880903158,
    "first_name": "Bardya",
    "username": "BardiaFar"
  },
  "meta": {},
  "error": {}
}
```

Failure cases (`401`, code `INVALID_LOGIN_TOKEN`):

- code mistyped
- older than ~5 minutes
- already used once (codes are single-use)

### Using the JWT

Send it as a Bearer header on every authenticated request:

```
Authorization: Bearer <access_token>
```

The JWT is valid for **7 days**. When it expires the API answers
`401 UNAUTHORIZED` - at that point just run the login flow again.
There is no refresh endpoint.

Storage is up to you (localStorage, cookie, memory). The API sets no cookies.

---

## 3. Search Public Profiles

```
GET /profiles/search
```

Public endpoint (no auth required).

### Query parameters

| Param | Type | Match style |
|---|---|---|
| `q` | string | Global multi-word text search (see below) |
| `username` | string | contains-match |
| `nickname` | string | contains-match |
| `first_name` | string | contains-match |
| `last_name` | string | contains-match |
| `bio` | string | contains-match |
| `occupation` | string | contains-match |
| `country` | string | **exact** match |
| `is_ban` | bool | exact |
| `is_registered` | bool | exact |
| `page` | int, default 1 | pagination |
| `size` | int, default 20, max 100 | page size |

All parameters are optional and combinable (they are ANDed together).

### How multi-word `q` works

Splitting `q` on spaces gives words like `iran doctor`. A profile matches only
if **every word appears in at least one of its *public* fields** (username,
nickname, first_name, last_name, bio, occupation, country).

- Word order does not matter: `doctor iran` == `iran doctor`
- Max **5 words** are used; extras are silently ignored
- More words = narrower results (strict AND)
- Privacy is respected per field: a word can only match through a field the
  user has made public

Examples:

```
GET /profiles/search?q=iran%20doctor        → Iranian doctors
GET /profiles/search?q=bardia               → single word
GET /profiles/search?country=Iran&is_registered=true
GET /profiles/search?q=ali&page=2&size=50
```

### Response

```json
{
  "data": [
    {
      "user_id": 880903158,
      "is_ban": false,
      "is_registered": true,
      "join_date": 1762401316,
      "username": "BardiaFar",
      "nickname": "Bardia",
      "first_name": "Bardya",
      "last_name": "far",
      "bio": "Hi",
      "occupation": null,
      "social_links": [
        { "id": 1, "platform": "instagram", "url": "https://instagram.com/ali", "label": null }
      ],
      "phone_number": "+989944473711",
      "whatsapp_number": null,
      "country": "Iran",
      "profile_url": null
    }
  ],
  "meta": { "total": 1, "page": 1, "size": 20, "pages": 1 },
  "error": {}
}
```

Use `meta.total` / `meta.pages` to render pagination controls.

### Important: `null` means "hidden", not "empty"

Fields are removed from the response when the owner hid them via privacy
settings. `occupation: null` can mean "no occupation set" OR "occupation is
private" - the API does not distinguish these for other users' profiles.
Design your UI around nullable fields everywhere.

---

## 4. View One Public Profile

```
GET /profiles/{user_id}
```

Public endpoint. Returns the same shape as one search item
(`SingleProfileResponse`). Responds with `404 USER_NOT_FOUND` when the user
does not exist **or** has disabled discovery (`is_profile_discoverable=false`)
- treat both identically ("profile not available").

---

## 5. My Account (authenticated)

All endpoints in this section require `Authorization: Bearer <jwt>`.

### 5.1 Get my profile

```
GET /account/me
```

Returns your **unfiltered** own profile plus current privacy settings:

```json
{
  "data": {
    "user_id": 880903158,
    "username": "BardiaFar",
    "first_name": "Bardya",
    "last_name": "far",
    "nickname": null,
    "bio": "Hi",
    "occupation": null,
    "phone_number": "+989944473711",
    "whatsapp_number": null,
    "country": "Iran",
    "profile_url": null,
    "is_ban": false,
    "is_registered": true,
    "join_date": 1762401316,
    "social_links": [],
    "privacy": {
      "is_profile_discoverable": true,
      "profile_picture_visibility": "public",
      "username_visibility": "public",
      "first_name_visibility": "public",
      "last_name_visibility": "public",
      "nickname_visibility": "public",
      "country_visibility": "public",
      "phone_number_visibility": "private",
      "whatsapp_number_visibility": "private",
      "bio_visibility": "public",
      "occupation_visibility": "public",
      "social_links_visibility": "public"
    }
  },
  "meta": {},
  "error": {}
}
```

Note: `username` comes from Telegram and cannot be changed here.

### 5.2 Update my profile

```
PATCH /account/profile
Content-Type: application/json
```

Editable fields: `first_name`, `last_name`, `bio`, `occupation`, `country`,
`whatsapp_number`.

Rules:

- **Partial update**: only include the fields you want to change
- Sending a field explicitly as `null` **clears** that field
- Omitted fields stay untouched
- Unknown fields are rejected (`400 INVALID_INPUT`) - send exactly this shape

```json
{ "bio": "New bio", "country": "Iran", "occupation": null }
```

Response: updated own profile (same shape as 5.1).

### 5.3 Update privacy settings

```
PATCH /account/privacy
```

Same partial-update rules. Every visibility value must be the string
`"public"` or `"private"`:

```json
{
  "is_profile_discoverable": true,
  "phone_number_visibility": "private",
  "country_visibility": "public"
}
```

Semantics of each flag:

| Flag | What it controls |
|---|---|
| `is_profile_discoverable` | Master switch: `false` removes the user from all searches and makes their profile return 404 |
| `*_visibility` | Whether that individual field appears to other users |

Response: updated own profile (same shape as 5.1).

### 5.4 Replace social links

```
PUT /account/social-links
Content-Type: application/json

{
  "links": [
    { "platform": "instagram", "url": "https://instagram.com/ali", "label": null },
    { "platform": "telegram",  "url": "https://t.me/bardia",       "label": "main" }
  ]
}
```

This is **replace-all**: the submitted list becomes the complete list.
Send an empty array to delete all links. `label` is optional.
Response: updated own profile (same shape as 5.1).

### 5.5 Upload profile picture

```
POST /account/me/profile-picture
Content-Type: multipart/form-data

file: <JPEG, PNG, or WebP image>
```

Example with fetch:

```js
const form = new FormData();
form.append("file", fileInput.files[0]);

await fetch(`${BASE}/account/me/profile-picture`, {
  method: "POST",
  headers: { Authorization: `Bearer ${token}` }, // do NOT set Content-Type manually
  body: form,
});
```

Response:

```json
{ "data": { "profile_url": "https://.../avatars/880903158.webp",
            "profile_picture_visibility": "public" }, ... }
```

### 5.6 Remove profile picture

```
DELETE /account/me/profile-picture
```

Returns `{ "profile_url": null, "profile_picture_visibility": "..." }`.

---

## 6. Bookmarks (authenticated)

Bookmarks are how users save other users' profiles.

### List my bookmarks

```
GET /bookmarks
```

Returns an array of `SingleProfileResponse` objects (same shape as search
items, privacy-filtered), newest first, with `meta.total`.

### Bookmark someone

```
POST /bookmarks/{user_id}
```

Response: `{ "user_id": 880903158, "bookmarked": true }`

Bookmarking twice is safe (idempotent).

### Remove a bookmark

```
DELETE /bookmarks/{user_id}
```

Response: `{ "user_id": 880903158, "bookmarked": false }`

Removing a non-existent bookmark is also safe.

---

## 7. Quick Reference

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/exchange-token` | - | Trade bot code for JWT |
| GET | `/profiles/search` | - | Search/filter public profiles |
| GET | `/profiles/{user_id}` | - | One public profile |
| GET | `/account/me` | JWT | Own profile + privacy settings |
| PATCH | `/account/profile` | JWT | Edit own profile fields |
| PATCH | `/account/privacy` | JWT | Change visibility flags |
| PUT | `/account/social-links` | JWT | Replace social links list |
| POST | `/account/me/profile-picture` | JWT | Upload avatar |
| DELETE | `/account/me/profile-picture` | JWT | Remove avatar |
| GET | `/bookmarks` | JWT | List bookmarked users |
| POST | `/bookmarks/{user_id}` | JWT | Add bookmark |
| DELETE | `/bookmarks/{user_id}` | JWT | Remove bookmark |

*(all paths relative to the base URL above)*
