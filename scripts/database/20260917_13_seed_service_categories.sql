-- Migration 13.
-- Seeds a minimal, curated category tree for the service directory.
-- Two levels: a broad parent and concrete child categories, which is what the
-- discovery flow ("choose a broad category, then a specific one") needs.
--
-- Idempotent: safe to re-run. Conflict on slug does nothing, so admin edits and
-- future additions are never overwritten.
--
-- `name` is Persian because it is shown to public users; `slug` stays Latin so
-- URLs remain clean and shareable.

BEGIN;

-- Parents
INSERT INTO public.categories (name, slug, display_order) VALUES
    ('غذا', 'food', 10),
    ('سلامت', 'healthcare', 20),
    ('خدمات حرفه‌ای', 'professional-services', 30),
    ('زیبایی', 'beauty', 40),
    ('خودرو', 'automotive', 50)
ON CONFLICT (slug) DO NOTHING;

-- Children, resolved to their parent by slug.
INSERT INTO public.categories (parent_id, name, slug, display_order)
SELECT parent.id, seed.name, seed.slug, seed.display_order
FROM (VALUES
    ('food', 'رستوران', 'restaurant', 10),
    ('food', 'خواربارفروشی', 'grocery-store', 20),
    ('food', 'کیترینگ', 'catering', 30),
    ('food', 'نانوایی', 'bakery', 40),
    ('healthcare', 'دندانپزشک', 'dentist', 10),
    ('healthcare', 'پزشک', 'doctor', 20),
    ('healthcare', 'کلینیک', 'clinic', 30),
    ('professional-services', 'وکیل', 'lawyer', 10),
    ('professional-services', 'حسابدار', 'accountant', 20),
    ('professional-services', 'املاک', 'real-estate', 30),
    ('professional-services', 'مترجم', 'translator', 40),
    ('beauty', 'آرایشگر', 'hairdresser', 10),
    ('automotive', 'تعمیرات خودرو', 'repair-service', 10)
) AS seed (parent_slug, name, slug, display_order)
JOIN public.categories AS parent ON parent.slug = seed.parent_slug
ON CONFLICT (slug) DO NOTHING;

COMMIT;
