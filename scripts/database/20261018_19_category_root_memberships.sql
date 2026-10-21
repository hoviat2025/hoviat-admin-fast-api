-- Two levels, with a child able to belong to several roots.
-- Existing category ids and service_categories assignments are preserved.
-- Existing deeper categories keep their ids and become children of their top root.
BEGIN;

SELECT pg_advisory_xact_lock(606125019);
LOCK TABLE public.categories IN SHARE ROW EXCLUSIVE MODE;

CREATE TABLE IF NOT EXISTS public.category_parents (
    category_id bigint NOT NULL REFERENCES public.categories(id) ON DELETE CASCADE,
    parent_id bigint NOT NULL REFERENCES public.categories(id) ON DELETE RESTRICT,
    PRIMARY KEY (category_id, parent_id),
    CONSTRAINT category_parent_not_self CHECK (category_id <> parent_id)
);
CREATE INDEX IF NOT EXISTS ix_category_parents_parent_id
    ON public.category_parents (parent_id);
LOCK TABLE public.category_parents IN SHARE ROW EXCLUSIVE MODE;

DROP TRIGGER IF EXISTS category_hierarchy_categories ON public.categories;
DROP TRIGGER IF EXISTS category_hierarchy_parents ON public.category_parents;

CREATE TEMP TABLE _category_root_map ON COMMIT DROP AS
WITH RECURSIVE ancestry AS (
    SELECT id AS category_id, id AS ancestor_id, parent_id, ARRAY[id] AS path
    FROM public.categories
    UNION ALL
    SELECT ancestry.category_id, parent.id, parent.parent_id, ancestry.path || parent.id
    FROM ancestry
    JOIN public.categories AS parent ON parent.id = ancestry.parent_id
    WHERE NOT parent.id = ANY(ancestry.path)
)
SELECT category_id, ancestor_id AS root_id
FROM ancestry WHERE parent_id IS NULL;

DO $BODY$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.categories category
        WHERE NOT EXISTS (SELECT 1 FROM _category_root_map roots WHERE roots.category_id = category.id)
    ) THEN
        RAISE EXCEPTION 'Existing category cycles must be repaired before migration 19';
    END IF;
END
$BODY$;

UPDATE public.categories category
SET parent_id = roots.root_id, updated_at = now()
FROM _category_root_map roots
WHERE roots.category_id = category.id
  AND category.parent_id IS NOT NULL
  AND category.parent_id IS DISTINCT FROM roots.root_id;

INSERT INTO public.category_parents (category_id, parent_id)
SELECT id, parent_id FROM public.categories WHERE parent_id IS NOT NULL
ON CONFLICT (category_id, parent_id) DO NOTHING;

CREATE OR REPLACE FUNCTION public.validate_category_root_memberships()
RETURNS trigger LANGUAGE plpgsql AS $BODY$
BEGIN
    PERFORM pg_advisory_xact_lock(606125019);
    IF EXISTS (
        SELECT 1 FROM public.categories child
        JOIN public.categories parent ON parent.id = child.parent_id
        WHERE parent.parent_id IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'Only roots may be parents; category depth cannot exceed two levels'
            USING ERRCODE = '23514';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.category_parents membership
        JOIN public.categories child ON child.id = membership.category_id
        JOIN public.categories parent ON parent.id = membership.parent_id
        WHERE child.parent_id IS NULL OR parent.parent_id IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'A child membership must connect a level-two category to a root'
            USING ERRCODE = '23514';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.categories child
        WHERE child.parent_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM public.category_parents membership
            WHERE membership.category_id = child.id AND membership.parent_id = child.parent_id
        )
    ) THEN
        RAISE EXCEPTION 'A category primary parent must be one of its root memberships'
            USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END
$BODY$;

-- Deferred checks permit changing primary parent and memberships atomically.
CREATE CONSTRAINT TRIGGER category_hierarchy_categories
AFTER INSERT OR UPDATE OR DELETE ON public.categories
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION public.validate_category_root_memberships();
CREATE CONSTRAINT TRIGGER category_hierarchy_parents
AFTER INSERT OR UPDATE OR DELETE ON public.category_parents
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION public.validate_category_root_memberships();

COMMENT ON TABLE public.category_parents IS
    'Membership of a child category under one or more roots. categories.parent_id is the primary membership; roots have no memberships.';

DO $BODY$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.category_parents membership
        JOIN public.categories child ON child.id = membership.category_id
        JOIN public.categories parent ON parent.id = membership.parent_id
        WHERE child.parent_id IS NULL OR parent.parent_id IS NOT NULL
    ) OR EXISTS (
        SELECT 1 FROM public.categories child
        JOIN public.categories parent ON parent.id = child.parent_id
        WHERE parent.parent_id IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'Existing secondary category memberships violate the two-level hierarchy; migration rolled back';
    END IF;
END
$BODY$;

COMMIT;
