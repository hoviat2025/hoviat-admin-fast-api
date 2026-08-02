# Manual user synchronization checks

Run the database migration first, deploy the matching API code, and use a disposable
Telegram user for these calls. Read the user after each write and compare both the
stored value and its entry in `field_updated_at`.

## 1. Eurobot can create an incomplete user

Call Eurobot `POST /upsert_member` with a new `user_id` and protected profile fields
set to `null`. Expect success and a new incomplete row; null fields should have null
field timestamps.

## 2. Hilfen can add information

Call Hilfen `POST /upsert_member` for that same user with a name, phone number, and
country. Expect those values to be stored and their field timestamps to be populated.

## 3. Eurobot cannot erase Hilfen information with null

Call Eurobot `POST /upsert_member` with the same `user_id` and explicit null values
for `first_name`, `last_name`, `phone_number`, `whatsapp_number`, `country`, `is_ban`,
`ban_time`, and `join_date`. Expect success, unchanged protected values, and unchanged
timestamps for those fields.

## 4. Real protected values can change

Send a new non-null country or phone number through Eurobot. Expect the new value to
be stored and only that field's timestamp to advance.

## 5. Unprotected fields can become null

First give the user a `mode`, `username`, or `nickname`, then upsert the same field as
null. Expect it to become null and its field timestamp to advance.

## 6. False and zero are not treated as null

Send `is_ban: false`, `ban_time: 0`, and `join_date: 0`. Expect all three values to be
accepted as real values.

## 7. Same-value writes do not move field timestamps

Read and save `country_updated_at`, send the exact current country again, then read the
user. Expect `country_updated_at` to remain unchanged.

## 8. Check the separate update endpoints

Repeat checks 3 through 6 using each bot's update endpoint. For Eurobot, repeat one
case through bulk update and bulk upsert as well.
