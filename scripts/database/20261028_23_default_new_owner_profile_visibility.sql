-- New business/person assignments start visible when admin and personal privacy
-- also allow it. No existing row or explicit per-business opt-out is rewritten.
BEGIN;
ALTER TABLE public.services
    ALTER COLUMN owner_show_profile SET DEFAULT true;

CREATE OR REPLACE FUNCTION public.reset_service_owner_profile_consent()
RETURNS trigger LANGUAGE plpgsql AS $BODY$
BEGIN
    IF OLD.owner_user_id IS DISTINCT FROM NEW.owner_user_id THEN
        NEW.owner_show_profile := true;
    END IF;
    RETURN NEW;
END
$BODY$;

COMMENT ON COLUMN public.services.owner_show_profile IS
    'Person visibility preference for this business. Defaults on for new assignments; public reads also require admin show_owner and account privacy. Same-assignment opt-outs are preserved.';
COMMIT;
