# Hilfen API Guide

Welcome! This document explains how to talk to the Hoviat API from the
Hilfen side: how to create, update, and look up members (one at a time or in
bulk), how to get pre-formatted quote/reply data, and — importantly — which
fields you may and may not clear.

> **Base URL and bearer token:** provided separately by the Hoviat team.
> The examples below use two shell variables — set them once and every
> command becomes copy-pasteable:
>
> ```bash
> BASE="https://<provided-base-url>/webhook/hoviat/v1/hilfen"
> TOKEN="<provided-hilfen-token>"
> ```

---

## 1. The basics

### Authentication

Every request carries the Hilfen token as a Bearer header. If it is missing
or wrong, you get `403` back:

```json
{ "data": null, "meta": {}, "error": { "code": "UNAUTHORIZED", "message": "Invalid Hilfen Bot Token" } }
```

### The response envelope

Every response — success or failure — has the same shape:

```json
{
  "data":  { ... },   // the payload; null when something went wrong
  "meta":  { ... },   // extra info (bulk counts, etc.)
  "error": {}         // empty on success; filled on failure
}
```

So the first thing your code should do is look at `error`: if it is `{}`,
`data` is yours; otherwise `error.code` tells you what happened. Errors
get their own section (section 8) with the full catalog.

### One mental model for the data

A "member" is a flat object of **strings**. There is no nesting, no typed
numbers — everything arrives as text and everything you send is text too.
Numeric fields are converted server-side. Empty fields come back with
friendly defaults (`"0"`, `"notconfirm"`, `"none"`, `"[]"`, `""`) rather
than `null`, so you never need null-checks in the legacy parts of your code.

---

## 2. Field reference (what you send vs. what we store)

| API field | Stored as | Notes |
|---|---|---|
| `id` | `hilfen_id` | Hilfen's own ID for the person |
| `user_id` | `user_id` | The shared primary key (Telegram user ID) |
| `phonenumber` | `phone_number` | |
| `idcart_photo` | `hilfen_id_card_photo` | |
| `all_projects` | `hilfen_all_projects` | number |
| `all_projects_done` | `hilfen_all_projects_done` | number |
| `limits_time` | `hilfen_limits_time` | unix timestamp |
| `name` | `first_name` + `last_name` | split on first space on write, joined back on read |
| `country` | `country` | |
| `status` | `hilfen_status` | defaults to `"notconfirm"` |
| `date_join` | `hilfen_date_join` | unix timestamp |
| `command` | `hilfen_command` | defaults to `"none"` |
| `data` | `hilfen_data` | defaults to `"[]"` |

`name` is the only tricky one: `"Khaled D"` is stored as first name
`Khaled` + last name `D`, and read back as `"Khaled D"`.

---

## 3. Single-member endpoints

### 3.1 Read one member

```bash
curl "$BASE/read_member?user_id=68075693" \
  -H "Authorization: Bearer $TOKEN"
```

Response:

```json
{
  "data": {
    "id": "2",
    "user_id": "68075693",
    "phonenumber": "+4915732239255",
    "idcart_photo": "",
    "all_projects": "10",
    "all_projects_done": "5",
    "limits_time": "0",
    "name": "ح .",
    "country": "آلمان",
    "status": "confirm",
    "date_join": "1616966238",
    "command": "none",
    "data": "[]",
    "updated_at": "2026-08-28T10:20:06.058336Z",
    "channel_updated_at": "2026-08-27T18:53:16.826436Z",
    "field_updated_at": { "..." : "see section 6" }
  },
  "meta": {},
  "error": {}
}
```

If the user does not exist you get `404` with
`error.code = "USERID_NOT_FOUND"`.

### 3.2 Create a member

```bash
curl -X POST "$BASE/insert_member" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "41238",
    "user_id": "251864141",
    "phonenumber": "+989031329472",
    "name": "Khaled",
    "country": "Norway",
    "status": "confirm",
    "date_join": "1695848541"
  }'
```

If a member with that `user_id` already exists you get `409
CONFLICT_OCCURRED` — use the upsert endpoint (3.4) if you do not care which
happens.

### 3.3 Update a member

```bash
curl -X POST "$BASE/update_member" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "2",
    "user_id": "68075693",
    "country": "آلمان",
    "status": "confirm"
  }'
```

Updates are **partial**: only the fields you actually send are applied,
everything else is left untouched. A missing member returns `404`.

⚠️ Before sending empty strings, read **section 5 (nullification)** — some
fields refuse to be cleared.

### 3.4 Create-or-update (upsert) — the one you will use most

```bash
curl -X POST "$BASE/upsert_member" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "2",
    "user_id": "68075693",
    "phonenumber": "+4915732239255",
    "name": "ح",
    "country": "آلمان",
    "status": "confirm",
    "date_join": "1616966238"
  }'
```

New `user_id` → created. Existing `user_id` → updated. Same body shape as
insert, same response shape as read. Ideal for sync loops where you do not
know (or care) whether the person exists yet.

### 3.5 Find a member by their Hilfen channel post

```bash
curl "$BASE/member_by_message?hilfen_message_id=26" \
  -H "Authorization: Bearer $TOKEN"
```

Given a message ID from the Hilfen channel, returns the member it belongs
to. Useful when your bot receives a reply/quote and you need to know who it
is about. `404` if no member matches.

### 3.6 Quote / reply info (pre-formatted strings)

```bash
curl "$BASE/quote_reply_info?user_id=68075693" \
  -H "Authorization: Bearer $TOKEN"
```

This one is special: instead of raw data, it returns **ready-to-display
strings** (Persian labels already included) for building a quote/reply card
in Telegram:

```json
{
  "data": {
    "channel_message_id": "415",
    "channel_id": "-1001129100618",
    "group_message_id": "443",
    "group_id": "-1002086581533",
    "public_group_message_id": "22",
    "public_group_id": "-1003238310244",
    "public_message_id": "21",
    "public_channel_id": "-1003443613002",
    "hilfen_message_id": "26",
    "hilfen_group_message_id": "179",
    "hilfen_channel_id": "-1002026011030",
    "hilfen_group_id": "-1002156702345",
    "is_registered": "وضعیت رجیستر : رجیستر شده",
    "first_name": "نام : ح",
    "username": "یوزر تلگرام : @safaeeee",
    "telegram_name": "نام در تلگرام : Hamed",
    "country": "کشور : آلمان",
    "phone_number": "شماره همراه: ++4915732239255",
    "score": "امتیاز : 0",
    "user_id": "آیدی : 68075693",
    "is_ban": "وضعیت بن : بن نیست",
    "footer_code": "$%^68075693^$%add_user",
    "hilfen_id": "آیدی در هیلفن : 2",
    "hilfen_status": "وضعیت در هیلفن : تایید شده",
    "hilfen_projects": "پروژه‌های هیلفن : 10 کل، 5 تکمیل شده",
    "hilfen_limits_time": "تاریخ محدودیت در هیلفن : محدود نشده"
  },
  "meta": {},
  "error": {}
}
```

(The full response contains more fields — every value is a display-ready
string.)

Two things to know:

- **Do not parse values out of these strings.** They are for display. When
  you need actual data, use `read_member`.
- The `*_message_id` / `*_channel_id` fields locate the member's posts
  across the channel network (main, public, hilfen). They may be empty
  early on — see section 7 for why.

---

## 4. Bulk endpoints

Every single-member write has a bulk twin, plus a bulk read:

```bash
# Read many at once
curl -X POST "$BASE/read_bulk_members" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_ids": [251864141, 68075693]}'

# Create-or-update many at once
curl -X POST "$BASE/upsert_bulk_members" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "users_info": [
      {
        "id": "41238",
        "user_id": "251864141",
        "phonenumber": "+989031329472",
        "name": ".",
        "country": ".",
        "status": "confirm",
        "date_join": "1695848541",
        "command": "none",
        "data": "[]",
        "all_projects": "0",
        "all_projects_done": "0",
        "limits_time": "0"
      },
      {
        "id": "2",
        "user_id": "68075693",
        "phonenumber": "+4915732239255",
        "idcart_photo": "",
        "all_projects": "10",
        "all_projects_done": "5",
        "limits_time": "0",
        "name": "ح",
        "country": "آلمان",
        "status": "confirm",
        "date_join": "1616966238",
        "command": "none",
        "data": "[]"
      }
    ]
  }'
```

(`insert_bulk_members` and `update_bulk_members` take the same `users_info`
body; `read_bulk_members` takes `user_ids` instead.)

### The rules

1. **At most 20 items per request.** Anything beyond item 20 is reported as
   failed with code `CONFLICT_OCCURRED` and is not processed. Chunk bigger
   sets yourself.
2. **Items are independent.** One bad item does not stop the others — you
   get a per-item verdict for everything.
3. Each verdict carries the item's `index` (its position in your original
   array), so matching results back to inputs is trivial.

### What a bulk response looks like

```json
{
  "data": {
    "successful": [
      {
        "index": 0,
        "status": "success",
        "user_id": "251864141",
        "data": { "id": "41238", "user_id": "251864141", "...": "full profile, same shape as read_member" }
      },
      {
        "index": 1,
        "status": "success",
        "user_id": "68075693",
        "data": { "id": "2", "user_id": "68075693", "...": "full profile" }
      }
    ],
    "failed": []
  },
  "meta": { "successful": 2, "failed": 0 },
  "error": {}
}
```

A failed item looks like this:

```json
{
  "index": 3,
  "status": "error",
  "code": "USERID_NOT_FOUND",
  "message": "No user exists with user_id 999"
}
```

`read_bulk_members` answers with a **map** keyed by user ID (as string) —
missing members are `null` rather than absent, so you always get an entry
per requested ID:

```json
{
  "data": { "251864141": { "...": "profile" }, "999": null },
  "meta": {},
  "error": {}
}
```

---

## 5. Nullification policy — read this before sending empty values

This is the section that prevents painful surprises. The API treats
fields in two different groups when you send an update or upsert.

### Protected fields — you cannot clear these (yet)

```
name        (stored as first_name / last_name)
phonenumber (phone_number)
country
id          (hilfen_id)
date_join   (hilfen_date_join)
```

If you send an **empty string** for any of these, the API interprets it as
"I don't have a value" — **not** "erase this" — and simply keeps the stored
value. The same applies to garbage values for the numeric ones (sending
`id: "abc"` skips the field rather than nulling it).

Why: this record is shared between systems. Until timestamp-based
reconciliation is in place (section 6), the API cannot distinguish "I have
no data for this field" from "I deliberately want to erase it" — so it
refuses to erase. This protects everyone from accidental wipes.

### Client-owned fields — yours to clear

All remaining fields (`status`, `command`, `data`, `idcart_photo`,
`all_projects`, `all_projects_done`, `limits_time`) are written **exactly
as you send them**: an explicit `""` or `null` really does clear them. One
exception: the numeric fields cannot store `""`, so an empty value there
becomes `null` (not the insert-time default `0`).

### Practical guidance

- Want to leave a field alone? **Omit it.** That is always safe.
- Want to set a value? Send it.
- Avoid sending `""` as a placeholder for "unknown" — on protected fields
  it does nothing, and everywhere else it destroys data. Say what you mean.

---

## 6. `field_updated_at` — per-field timestamps

Every member response carries three timestamps:

- `updated_at` — the last time anything in the row changed
- `channel_updated_at` — the last time the channel posts were synced
- `field_updated_at` — a map from **every field** to the last time *that
  specific field* changed (ISO 8601), or `null` if it was never set

```json
"field_updated_at": {
  "username": "2025-11-27T09:17:09.310514Z",
  "phone_number": "2026-08-28T10:20:06.043806Z",
  "hilfen_status": "2026-08-28T10:20:06.043806Z",
  "bio": null,
  "...": "..."
}
```

These are owned by our database (column-level triggers) — you can read
them, never write them.

**What they are for:** reconciling your copy of the data with ours. When
your side and ours disagree about a field, compare *when you last changed
it* against `field_updated_at.<field>` — whoever changed it later wins.
This comparison is the future foundation for safe nullification: once
clients demonstrate they reconcile this way, the API can start accepting
deliberate clears on the protected fields.

---

## 7. Channel sync — what happens after your write

Every successful insert / update / upsert **enqueues a background job**
that refreshes the member's posts in the Hilfen channel (and the shared
channels). Two practical consequences:

1. **`hilfen_message_id` and `hilfen_group_message_id` fill in
   asynchronously.** They are recorded by a Telegram-side webhook
   (`PUT /channels/set_hilfen_message_id`) — never call it yourself, and do
   not expect those IDs in the response of the write that triggered them.
2. **Channel updates run at roughly 3 members per minute** (shared with
   other background work). Bulk-importing 20 members is instant on the API
   side, but their channel posts appear over the following minutes. You do
   not need to throttle your API calls — just do not expect the channel to
   update in real time.

---

## 8. Errors — the full catalog

Every error is a normal HTTP status code plus the standard envelope with
`data: null` and a filled `error` object:

```json
{
  "data": null,
  "meta": {},
  "error": {
    "code": "USERID_NOT_FOUND",
    "message": "No user exists with user_id 999"
  }
}
```

The complete list of what you can receive:

| HTTP | `error.code` | When you get it | What to do |
|---|---|---|---|
| 403 | `FORBIDDEN` | The `Authorization` header is missing or the token is wrong | Check the header; token is case-sensitive |
| 404 | `USERID_NOT_FOUND` | `read_member`, `update_member`, `quote_reply_info`, or a bulk-update item referenced a `user_id` that does not exist | Create the member first (insert/upsert) |
| 409 | `CONFLICT_OCCURRED` | `insert_member` / `insert_bulk_members` on a `user_id` that already exists; rarely, a DB constraint violation | Use upsert instead of insert, or update the existing member |
| 422 | `INVALID_INPUT` | Malformed JSON, missing/invalid `user_id`, or a body that fails validation | Fix the body; the message names the problem |
| 500 | `INTERNAL_SERVER_ERROR` | Something broke on our side | Retry later; if it persists, contact us with the timestamp |

Example — inserting a user who already exists:

```json
{
  "data": null,
  "meta": {},
  "error": {
    "code": "CONFLICT_OCCURRED",
    "message": "duplicate key value violates unique constraint \"users_eurobot_pkey\""
  }
}
```

### Things that look like errors but are not

Some mistakes are handled **silently** rather than rejected:

1. **Empty values on protected fields** (section 5) — sending
   `"phonenumber": ""` or `id: "abc"` is not an error; the field is simply
   skipped and the stored value survives. The response will show the old
   value.
2. **Omitted fields** — never an error; they mean "leave untouched".
3. **Extra/unknown fields** in the body are ignored, not rejected.

### Errors in bulk requests

Bulk endpoints **never fail as a whole** because one item failed — a valid
request with 20 items where 5 are bad returns HTTP `200` with 15 entries in
`successful` and 5 in `failed` (each carrying its `index`, `code`, and
`message`). The top-level `error` object stays `{}`. Only a broken request
itself (bad JSON, wrong token, no `users_info` array) produces a top-level
error.

---

## 9. Quick reference

| Method | Path | Purpose |
|---|---|---|
| GET | `/read_member?user_id=` | One member, legacy format |
| POST | `/insert_member` | Create (409 if exists) |
| POST | `/update_member` | Partial update (404 if missing) |
| POST | `/upsert_member` | Create or update |
| GET | `/member_by_message?hilfen_message_id=` | Lookup by Hilfen channel post |
| GET | `/quote_reply_info?user_id=` | Pre-formatted quote/reply strings |
| POST | `/read_bulk_members` | Map of user_id → profile (null if missing) |
| POST | `/insert_bulk_members` | Bulk create, per-item results |
| POST | `/update_bulk_members` | Bulk partial update, per-item results |
| POST | `/upsert_bulk_members` | Bulk create-or-update, per-item results |

All paths are relative to the base URL. Bulk requests take at most 20
items.
