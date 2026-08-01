# Manual checks for the user_id primary-key migration

Run `20260802_02_make_user_id_primary_key.sql` on the test database, deploy the
matching API code, and restart the API before these checks.

## 1. Inspect the resulting constraints

```sql
SELECT
    column_name,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'users_eurobot'
  AND column_name IN ('user_id', 'counter')
ORDER BY column_name;

SELECT
    constraint_name,
    constraint_type
FROM information_schema.table_constraints
WHERE table_schema = 'public'
  AND table_name = 'users_eurobot'
  AND constraint_type IN ('PRIMARY KEY', 'UNIQUE')
ORDER BY constraint_type, constraint_name;
```

Expect `user_id` to be non-null and primary, and `counter` to be nullable,
unique, and without a default.

## 2. Existing Eurobot user without counter in the request

Upsert an existing user using only `user_id` and one harmless field. It should
succeed without the earlier counter conflict and must preserve the stored counter.

## 3. Hilfen-only user lifecycle

Create a new disposable user through Hilfen. Confirm the row has a user_id and a
null counter. Then upsert the same user through Eurobot with a real unused counter.
Confirm the same row receives that counter instead of creating another row.

## 4. Uniqueness

Try assigning an existing non-null counter to a different disposable user. Expect
a conflict. The original user's data must remain unchanged.

## 5. Existing behavior

Read/update one existing user, enqueue its channel synchronization, and open the
admin user list. Confirm all three continue to locate the user by user_id and that
the admin list defaults to newest rows first.
