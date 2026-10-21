-- Independent per-business consent from the assigned person. Existing
-- associations remain private until the person explicitly opts in.
BEGIN;
ALTER TABLE public.services
    ADD COLUMN IF NOT EXISTS owner_show_profile boolean NOT NULL DEFAULT false;
COMMENT ON COLUMN public.services.owner_show_profile IS
    'Assigned person consent for this business. Public reads also require admin show_owner and a public personal profile. Reset on reassignment.';
CREATE OR REPLACE FUNCTION public.reset_service_owner_profile_consent()
RETURNS trigger LANGUAGE plpgsql AS $BODY$
BEGIN
    IF OLD.owner_user_id IS DISTINCT FROM NEW.owner_user_id THEN
        NEW.owner_show_profile := false;
    END IF;
    RETURN NEW;
END
$BODY$;
DROP TRIGGER IF EXISTS service_owner_profile_consent ON public.services;
CREATE TRIGGER service_owner_profile_consent
BEFORE UPDATE OF owner_user_id ON public.services
FOR EACH ROW EXECUTE FUNCTION public.reset_service_owner_profile_consent();
COMMIT;
