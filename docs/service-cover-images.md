# Business cover images

Business covers use the existing R2/S3 storage client. The database stores a
managed object key in `services.cover_image_path`; responses expose only
`cover_image_url: string | null`. This field is included in admin, owner and
public business responses, including saved businesses. Public listing/status
and owner authorization rules continue to control those responses.

## Database migration

Apply `scripts/database/20261018_18_add_service_cover_image.sql` to the intended
database **before starting the backend version with the new model**. It adds
one nullable text column and is safe to rerun. No existing images or listings
are modified. For the existing local development database, use the configured
database role and password with:

```powershell
rtk proxy psql -h 127.0.0.1 -p 5433 -d hoviat_service_dev -U <database-role> -v ON_ERROR_STOP=1 -f scripts/database/20261018_18_add_service_cover_image.sql
```

Migration 18 has been applied to the local development database
`127.0.0.1:5433/hoviat_service_dev`, after verifying the configured loopback
connection, PostgreSQL's current database/server address and disabled background
workers. Production and other databases still require the migration before this
backend version is deployed. Application startup does not apply it automatically.

## Storage configuration

The existing `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` and
`R2_BUCKET_NAME` settings provide storage. `SERVICE_MEDIA_URL` optionally sets
the public HTTP(S) base URL for covers; otherwise `PROFILE_MEDIA_URL` is reused.
The public base URL must serve keys from that bucket. Upload refuses with 503
when no valid public base URL is configured, so it never saves an unusable raw
storage path as a public image URL.

Generated objects have keys `business-covers/{service_id}/{random_uuid}.jpg`.
The client cannot choose keys, submit image URLs through service JSON writes,
or request deletion of another listing's object.

## Admin API

Both endpoints require the existing admin JWT and write-users permission.
Create the service first so it has an ID and `updated_at` value.

* `POST /api/admin/service-management/services/{id}/cover-image`: multipart
  form with `file` and `expected_updated_at` (the currently loaded ISO timestamp).
* `DELETE /api/admin/service-management/services/{id}/cover-image`: query
  parameter `expected_updated_at` (URL encode the timestamp).

Both return the standard response envelope containing the full admin service,
including `cover_image_url` and the current `updated_at`. Image operations are
separate from aggregate JSON saves; the JSON save preserves the existing cover.
After a successful image operation, use the returned service as the editor's
baseline before its next aggregate save. Preserve any unsaved form edits while
updating that baseline. A stale timestamp returns 409 before any upload or
deletion. Missing services return 404.

Upload supports JPEG, PNG and WebP and verifies the decoded image instead of
trusting the filename or MIME header. The input limit is 5 MiB, dimensions are
at most 10,000 pixels per side and 25 million pixels total. Images are rotated
according to EXIF, resized to fit within 1600 × 1000 without enlarging or forcing
a crop, flattened on white and encoded as JPEG. EXIF/GPS and animation metadata
are omitted. Oversized files return 413; invalid formats/dimensions return 422;
storage upload failure returns 502.

The service row is locked throughout its image mutation. Its new key and admin
audit action commit together. On a failed database save, the new object is
removed when possible; on success, the previous managed object is removed only
after commit. Cleanup failures are logged and do not turn a committed image
change into an apparent failure. Removing an already absent cover is a no-op
when the supplied version is current.
