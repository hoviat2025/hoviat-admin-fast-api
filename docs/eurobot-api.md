# Eurobot API Guide

Welcome! This document explains how to talk to the Hoviat API from the
Eurobot side: how to create, update, and look up members (one at a time or
in bulk), and how to get pre-formatted quote/reply data.

> **Base URL and bearer token:** provided separately by the Hoviat team.
> The examples below use two shell variables — set them once and every
> command becomes copy-pasteable:
>
> ```bash
> BASE="https://<provided-base-url>/webhook/hoviat/v1/eurobot"
> TOKEN="<provided-eurobot-token>"
> ```

---

## 1. The basics

### Authentication

Every request carries the Eurobot token as a Bearer header. If it is
missing or wrong, you get `403` back. See section 8 for the full error
catalog.

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
`data` is yours. Errors get their own section (section 8).

### One mental model for the data

A member response is a mix of types — **not** all-strings:

- IDs and unix timestamps come back as **strings** (`"user_id": "251864141"`,
  `"join_date": "1697708344"`) — but you may send them as JSON numbers,
  both are accepted
- `counter` and `score` are real **integers**
- `is_ban`, `is_registered`, `chat_not_found` are real **booleans**
- Everything else is a string, and unset string fields come back as
  `null` (not `""`) — so null-checks matter on your side

---

## 2. Field reference

### What you can send (create / upsert)

| Field | Type | Notes |
|---|---|---|
| `user_id` | int, **required** | The Telegram user ID — the primary key |
| `counter` | int | Eurobot-owned counter |
| `accounting_code` | string | |
| `first_name` / `last_name` | string | |
| `username` | string | Telegram username |
| `nickname` | string | Display name |
| `phone_number` / `whatsapp_number` | string | |
| `country` | string | |
| `password` | string | |
| `mode` | string | Bot UI state |
| `is_ban` / `is_registered` | bool | |
| `score` / `ban_time` | int | |
| `join_date` | int | unix timestamp |

Unknown extra fields are ignored, not rejected.

### What you can update (PATCH-style)

`PUT /update_member` accepts a **subset**: `counter`, `accounting_code`,
`ban_time`, `country`, `first_name`, `last_name`, `is_ban`, `is_registered`,
`join_date`, `password`, `phone_number`, `score`, `whatsapp_number`.

Note: `username`, `nickname`, and `mode` are **not updatable** through this
endpoint — they are identity/state fields owned by the Telegram/bot flow.
Updates are **partial**: only the fields you send are applied. Every
successful write marks the member as present in Eurobot
(`is_in_eurobot = true`).

### What you get back (every read/write)

The response is the **full stored record**, including fields you never
sent:

```json
{
  "user_id": "251864141",
  "ban_time": "0",
  "join_date": "1697708344",
  "telegram_message_id": "12184",
  "group_message_id": "12565",
  "public_message_id": "11002",
  "public_group_message_id": "11005",
  "counter": 21,
  "username": "ErfanEM_EE",
  "first_name": "عرفان",
  "last_name": "📜 نمایش لیست حواله ها",
  "nickname": "Erfan.EM",
  "phone_number": "989031329472",
  "whatsapp_number": null,
  "country": "ایران",
  "password": "9999",
  "mode": "MainMenu",
  "accounting_code": "9998",
  "is_ban": false,
  "is_registered": true,
  "chat_not_found": false,
  "score": 0,
  "profile_path": "AQADBAADaKgxG00kAw8ACAMAA00kAw8ABGnM7BrmRapXNgQ.jpg",
  "updated_at": "2026-08-27T18:13:14.782Z",
  "channel_updated_at": "2025-12-02T20:09:12.495Z",
  "field_updated_at": { "...": "see section 6" }
}
```

The four message-ID fields locate the member's posts across the channel
network (main channel, main group, public channel, public group). They fill
in **asynchronously** after your write — see section 7.

---

## 3. Single-member endpoints

### 3.1 Read one member

```bash
curl "$BASE/read_member?user_id=251864141" \
  -H "Authorization: Bearer $TOKEN"
```

Returns the full record (shape above), or `404` with
`error.code = "USERID_NOT_FOUND"`.

### 3.2 Create a member

```bash
curl -X POST "$BASE/insert_member" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 251864141,
    "first_name": "عرفان",
    "last_name": "محمدی",
    "username": "ErfanEM_EE",
    "nickname": "Erfan.EM",
    "country": "ایران",
    "phone_number": "989031329472",
    "is_registered": true
  }'
```

If a member with that `user_id` already exists you get `409
CONFLICT_OCCURRED` — use the upsert endpoint (3.4) if you do not care which
happens.

### 3.3 Update a member

```bash
curl -X PUT "$BASE/update_member" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 251864141,
    "country": "ایران",
    "score": 10
  }'
```

Note this is a **PUT**, not POST. Updates are **partial** (only sent fields
are applied) and restricted to the subset listed in section 2. A missing
member returns `404`.

⚠️ Before sending `null` or `""`, read **section 5 (nullification)**.

### 3.4 Create-or-update (upsert) — the one you will use most

```bash
curl -X POST "$BASE/upsert_member" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 251864141,
    "counter": 21,
    "first_name": "عرفان",
    "username": "ErfanEM_EE",
    "country": "ایران",
    "is_registered": true
  }'
```

New `user_id` → created. Existing `user_id` → updated. Same body shape as
insert, response is the full record. Ideal for sync loops.

### 3.5 Find a member by their public channel post

```bash
curl "$BASE/member_by_message?public_message_id=11002" \
  -H "Authorization: Bearer $TOKEN"
```

Given a message ID from the public channel, returns the member it belongs
to. `404` if no member matches.

### 3.6 Quote / reply info (pre-formatted strings)

```bash
curl "$BASE/quote_reply_info?user_id=251864141" \
  -H "Authorization: Bearer $TOKEN"
```

This one is special: instead of raw data, it returns **ready-to-display
strings** (Persian labels already included) for building a quote/reply card
in Telegram:

```json
{
  "data": {
    "channel_message_id": "16242",
    "channel_id": "-1001129100618",
    "group_message_id": "24326",
    "group_id": "-1002086581533",
    "public_group_message_id": "22492",
    "public_group_id": "-1003238310244",
    "public_message_id": "15020",
    "public_channel_id": "-1003443613002",
    "hilfen_message_id": null,
    "hilfen_group_message_id": null,
    "hilfen_channel_id": "-1002026011030",
    "hilfen_group_id": "-1002156702345",
    "is_registered": "وضعیت رجیستر : رجیستر شده",
    "first_name": "نام : ali",
    "last_name": "نام خانوادگی : mohammadi",
    "username": "یوزر تلگرام : @Ms550",
    "telegram_name": "نام در تلگرام : M",
    "country": "کشور : ایران",
    "phone_number": "شماره همراه: +989392340265",
    "join_date": "تاریخ عضویت : 2023/10/19",
    "score": "امتیاز : 0",
    "user_id": "آیدی : 3",
    "is_in_eurobot": "عضویت در یوروبات : بله",
    "is_in_hilfen_bot": "عضویت در هیلفن : بله",
    "is_ban": "وضعیت بن : بن نیست",
    "chat_not_found": "چت یافت نشد : صحیح",
    "new_user_alert": "❗️مشتری جدید",
    "stars": "ستاره ها : « ⭐️⭐️⭐️⭐️⭐️ »",
    "footer_code": "$%^3^$%add_user",
    "hilfen_id": "آیدی در هیلفن : نامشخص",
    "hilfen_status": "وضعیت در هیلفن : نامشخص",
    "hilfen_projects": "پروژه‌های هیلفن : 0 کل، 0 تکمیل شده",
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
- Hilfen-related fields are `null` / `"نامشخص"` when the member has no
  Hilfen presence yet — that is normal, not an error.

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
        "user_id": 251864141,
        "first_name": "عرفان",
        "username": "ErfanEM_EE",
        "country": "ایران",
        "is_registered": true
      },
      {
        "user_id": 68075693,
        "counter": 22,
        "first_name": "حامد",
        "username": "safaeeee",
        "country": "ایران",
        "phone_number": "4915732239255"
      }
    ]
  }'
```

(`insert_bulk_members` and `update_bulk_members` take the same `users_info`
body; `update_bulk_members` uses the update-restricted field set;
`read_bulk_members` takes `user_ids` instead.)

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
        "data": { "...": "full record, same shape as read_member" }
      }
    ],
    "failed": []
  },
  "meta": { "successful": 1, "failed": 0 },
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
  "data": { "251864141": { "...": "record" }, "999": null },
  "meta": {},
  "error": {}
}
```

---

## 5. Nullification policy — read this before sending empty values

This is the section that prevents painful surprises. On **update**
(and bulk update), fields are treated in two different groups.

### Protected fields — you cannot clear these

```
first_name
last_name
phone_number
whatsapp_number
country
is_ban
ban_time
join_date
```

Sending an explicit **`null`** for any of these is treated as
"not provided" and is **ignored** — the stored value survives.

Why: this record is shared between systems. Until timestamp-based
reconciliation is in place (section 6), the API cannot distinguish "I have
no data for this field" from "I deliberately want to erase it" — so it
refuses to erase.

Note the difference from empty **strings**: sending `""` for a protected
string field is *not* filtered (only `null` is) — so `""` **overwrites**.
If you mean "unknown", send nothing at all.

### Client-owned fields — passed through verbatim

`counter`, `accounting_code`, `password`, `score` are written exactly as
you send them: an explicit `null` really does clear them.

### Practical guidance

- Want to leave a field alone? **Omit it.** That is always safe.
- Want to set a value? Send it.
- Avoid `null` on protected fields as a placeholder for "unknown" — it is a
  no-op, but it makes intent unclear. And never send `""` unless you
  genuinely want an empty string stored.

---

## 6. `field_updated_at` — per-field timestamps

Every member response carries three timestamps:

- `updated_at` — the last time anything in the row changed
- `channel_updated_at` — the last time the channel posts were synced
- `field_updated_at` — a map from **every field** to the last time *that
  specific field* changed (ISO 8601 with milliseconds), or `null` if it was
  never set

```json
"field_updated_at": {
  "username": "2025-11-27T09:17:09.310Z",
  "country": "2026-08-27T18:53:11.589Z",
  "bio": null,
  "...": "..."
}
```

These are owned by our database (column-level triggers) — you can read
them, never write them.

**What they are for:** reconciling your copy of the data with ours. When
your side and ours disagree about a field, compare *when you last changed
it* against `field_updated_at.<field>` — whoever changed it later wins.

---

## 7. Channel sync — what happens after your write

Every successful insert / update / upsert **enqueues a background job**
that refreshes the member's posts in the main channel, the public channel,
and their discussion groups. Two practical consequences:

1. **The message-ID fields fill in asynchronously.** They are recorded by
   Telegram-side webhooks — never expect them in the response of the write
   that triggered them.
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

### Things that look like errors but are not

1. **`null` on protected fields** (section 5) — not an error; the field is
   skipped and the stored value survives.
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
| GET | `/read_member?user_id=` | One member, full record |
| POST | `/insert_member` | Create (409 if exists) |
| PUT | `/update_member` | Partial update (404 if missing) |
| POST | `/upsert_member` | Create or update |
| GET | `/member_by_message?public_message_id=` | Lookup by public channel post |
| GET | `/quote_reply_info?user_id=` | Pre-formatted quote/reply strings |
| POST | `/read_bulk_members` | Map of user_id → record (null if missing) |
| POST | `/insert_bulk_members` | Bulk create, per-item results |
| POST | `/update_bulk_members` | Bulk partial update, per-item results |
| POST | `/upsert_bulk_members` | Bulk create-or-update, per-item results |

All paths are relative to the base URL. Bulk requests take at most 20
items. Fill in `BASE` and `TOKEN` (top of this document) and every example
is ready to run.
