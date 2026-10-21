-- Private saved businesses. Separate from bookmarks, which saves people.
-- Apply after 20260917_12_add_services_domain.sql. Safe to rerun.
BEGIN;

CREATE TABLE IF NOT EXISTS public.service_bookmarks (
    bookmarker_id bigint NOT NULL
        REFERENCES public.users_eurobot(user_id) ON DELETE CASCADE,
    service_id bigint NOT NULL
        REFERENCES public.services(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (bookmarker_id, service_id)
);

CREATE INDEX IF NOT EXISTS service_bookmarks_user_created_idx
    ON public.service_bookmarks (bookmarker_id, created_at);
CREATE INDEX IF NOT EXISTS service_bookmarks_service_idx
    ON public.service_bookmarks (service_id);

COMMENT ON TABLE public.service_bookmarks IS
    'Private saved business listings. Public reads must exclude unpublished services and use the public service projection.';

COMMIT;
