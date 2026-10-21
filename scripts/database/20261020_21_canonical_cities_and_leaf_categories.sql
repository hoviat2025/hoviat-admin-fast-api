-- Shared location entities and leaf-only business classification.
-- Text location columns remain compatible API projections; database triggers
-- resolve them to catalogue rows and keep their spelling consistent.
BEGIN;
SELECT pg_advisory_xact_lock(606125021);
SELECT pg_advisory_xact_lock(606125019);
LOCK TABLE public.services, public.categories, public.service_categories IN SHARE ROW EXCLUSIVE MODE;

CREATE TABLE IF NOT EXISTS public.cities (
    id bigserial PRIMARY KEY,
    state_id bigint NOT NULL REFERENCES public.country_states(id) ON DELETE RESTRICT,
    name text NOT NULL CHECK (btrim(name) <> ''),
    aliases text[] NOT NULL DEFAULT '{}',
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS cities_state_name_key ON public.cities(state_id,lower(name));
ALTER TABLE public.services ADD COLUMN IF NOT EXISTS city_id bigint REFERENCES public.cities(id) ON DELETE RESTRICT;
ALTER TABLE public.services ADD COLUMN IF NOT EXISTS state_id bigint REFERENCES public.country_states(id) ON DELETE RESTRICT;
CREATE INDEX IF NOT EXISTS services_city_id_idx ON public.services(city_id);
CREATE INDEX IF NOT EXISTS services_state_id_idx ON public.services(state_id);

-- Initial curated catalogue, extended centrally by admins as needed. Aliases
-- resolve input spellings but are never extra cities in the selector.
INSERT INTO public.cities(state_id,name,aliases)
SELECT s.id,v.name,v.aliases FROM (VALUES
 ('de-berlin','Berlin',ARRAY['برلین']),
 ('de-bremen','Bremen',ARRAY['برمن']),
 ('de-bremen','Bremerhaven',ARRAY[]::text[]),
 ('de-hamburg','Hamburg',ARRAY['هامبورگ']),
 ('de-bayern','München',ARRAY['Munich','Muenchen','مونیخ']),
 ('de-bayern','Nürnberg',ARRAY['Nuremberg','Nuernberg','نورنبرگ']),
 ('de-bayern','Augsburg',ARRAY['آوگسبورگ']),
 ('de-bayern','Regensburg',ARRAY['رگنسبورگ']),
 ('de-bayern','Ingolstadt',ARRAY['اینگولشتات']),
 ('de-bayern','Würzburg',ARRAY['Wuerzburg']),
 ('de-bayern','Erlangen',ARRAY[]::text[]),
 ('de-bayern','Fürth',ARRAY['Fuerth']),
 ('de-bayern','Bamberg',ARRAY[]::text[]),
 ('de-baden-wuerttemberg','Stuttgart',ARRAY['اشتوتگارت']),
 ('de-baden-wuerttemberg','Mannheim',ARRAY['مانهایم']),
 ('de-baden-wuerttemberg','Karlsruhe',ARRAY['کارلسروهه']),
 ('de-baden-wuerttemberg','Heidelberg',ARRAY['هایدلبرگ']),
 ('de-baden-wuerttemberg','Freiburg im Breisgau',ARRAY['Freiburg','فرایبورگ']),
 ('de-baden-wuerttemberg','Ulm',ARRAY['اولم']),
 ('de-baden-wuerttemberg','Heilbronn',ARRAY[]::text[]),
 ('de-baden-wuerttemberg','Pforzheim',ARRAY[]::text[]),
 ('de-baden-wuerttemberg','Reutlingen',ARRAY[]::text[]),
 ('de-baden-wuerttemberg','Tübingen',ARRAY['Tuebingen']),
 ('de-brandenburg','Potsdam',ARRAY['پوتسدام']),
 ('de-brandenburg','Cottbus',ARRAY[]::text[]),
 ('de-hessen','Wiesbaden',ARRAY['ویسبادن']),
 ('de-hessen','Frankfurt am Main',ARRAY['Frankfurt','فرانکفورت']),
 ('de-hessen','Kassel',ARRAY['کاسل']),
 ('de-hessen','Darmstadt',ARRAY['دارمشتات']),
 ('de-hessen','Offenbach am Main',ARRAY['Offenbach']),
 ('de-hessen','Gießen',ARRAY['Giessen']),
 ('de-mecklenburg-vorpommern','Schwerin',ARRAY['شوِرین']),
 ('de-mecklenburg-vorpommern','Rostock',ARRAY['روستوک']),
 ('de-niedersachsen','Hannover',ARRAY['Hanover','هانوفر']),
 ('de-niedersachsen','Braunschweig',ARRAY['Brunswick']),
 ('de-niedersachsen','Oldenburg',ARRAY[]::text[]),
 ('de-niedersachsen','Osnabrück',ARRAY['Osnabrueck']),
 ('de-niedersachsen','Göttingen',ARRAY['Goettingen']),
 ('de-niedersachsen','Wolfsburg',ARRAY['ولفسبورگ']),
 ('de-nordrhein-westfalen','Düsseldorf',ARRAY['Dusseldorf','Duesseldorf','دوسلدورف']),
 ('de-nordrhein-westfalen','Köln',ARRAY['Cologne','Koeln','کلن']),
 ('de-nordrhein-westfalen','Dortmund',ARRAY['دورتموند']),
 ('de-nordrhein-westfalen','Essen',ARRAY['اسن']),
 ('de-nordrhein-westfalen','Duisburg',ARRAY['دویسبورگ']),
 ('de-nordrhein-westfalen','Bochum',ARRAY['بوخوم']),
 ('de-nordrhein-westfalen','Wuppertal',ARRAY['ووپرتال']),
 ('de-nordrhein-westfalen','Bonn',ARRAY['بن']),
 ('de-nordrhein-westfalen','Bielefeld',ARRAY['بیله‌فلد']),
 ('de-nordrhein-westfalen','Münster',ARRAY['Muenster','مونستر']),
 ('de-nordrhein-westfalen','Aachen',ARRAY['آخن']),
 ('de-nordrhein-westfalen','Mönchengladbach',ARRAY['Moenchengladbach']),
 ('de-nordrhein-westfalen','Gelsenkirchen',ARRAY[]::text[]),
 ('de-nordrhein-westfalen','Krefeld',ARRAY[]::text[]),
 ('de-nordrhein-westfalen','Oberhausen',ARRAY[]::text[]),
 ('de-rheinland-pfalz','Mainz',ARRAY['ماینتس']),
 ('de-rheinland-pfalz','Ludwigshafen am Rhein',ARRAY['Ludwigshafen']),
 ('de-rheinland-pfalz','Koblenz',ARRAY['کوبلنتس']),
 ('de-rheinland-pfalz','Trier',ARRAY['تریر']),
 ('de-rheinland-pfalz','Kaiserslautern',ARRAY[]::text[]),
 ('de-saarland','Saarbrücken',ARRAY['Saarbruecken','زاربروکن']),
 ('de-sachsen','Dresden',ARRAY['درسدن']),
 ('de-sachsen','Leipzig',ARRAY['لایپزیگ']),
 ('de-sachsen','Chemnitz',ARRAY['کمنیتس']),
 ('de-sachsen-anhalt','Magdeburg',ARRAY['ماگدبورگ']),
 ('de-sachsen-anhalt','Halle (Saale)',ARRAY['Halle']),
 ('de-schleswig-holstein','Kiel',ARRAY['کیل']),
 ('de-schleswig-holstein','Lübeck',ARRAY['Luebeck','لوبک']),
 ('de-schleswig-holstein','Flensburg',ARRAY[]::text[]),
 ('de-thueringen','Erfurt',ARRAY['ارفورت']),
 ('de-thueringen','Jena',ARRAY['ینا'])
) AS v(slug,name,aliases) JOIN public.country_states s ON s.slug=v.slug
ON CONFLICT DO NOTHING;

-- Keep unmapped old text privately for review; never invent a real city from
-- arbitrary legacy text. All recognized names/aliases are canonicalized.
CREATE TABLE IF NOT EXISTS public.service_location_legacy (
    service_id bigint PRIMARY KEY REFERENCES public.services(id) ON DELETE CASCADE,
    original_location jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO public.service_location_legacy(service_id,original_location)
SELECT id,jsonb_build_object('country_code',country_code,'state',state,'city',city)
FROM public.services WHERE city IS NOT NULL OR state IS NOT NULL
ON CONFLICT DO NOTHING;

UPDATE public.services service SET state_id=s.id, state=s.name,updated_at=now()
FROM public.country_states s
WHERE s.country_code=service.country_code AND
 (lower(btrim(service.state))=lower(s.name) OR EXISTS (
    SELECT 1 FROM unnest(s.aliases) a WHERE lower(a)=lower(btrim(service.state))));

UPDATE public.services service SET city_id=c.id,city=c.name,state_id=s.id,state=s.name,updated_at=now()
FROM public.cities c JOIN public.country_states s ON s.id=c.state_id
WHERE service.country_code=s.country_code AND service.state_id=s.id AND
 (lower(btrim(service.city))=lower(c.name) OR EXISTS (
    SELECT 1 FROM unnest(c.aliases) a WHERE lower(a)=lower(btrim(service.city))));

-- A unique city can supply its state when legacy state text was absent.
WITH candidates AS (
 SELECT service.id service_id,min(c.id) city_id FROM public.services service
 JOIN public.country_states s ON s.country_code=service.country_code
 JOIN public.cities c ON c.state_id=s.id
 WHERE service.city_id IS NULL AND service.state_id IS NULL AND
 (lower(btrim(service.city))=lower(c.name) OR EXISTS (
    SELECT 1 FROM unnest(c.aliases) a WHERE lower(a)=lower(btrim(service.city))))
 GROUP BY service.id HAVING count(*)=1
)
UPDATE public.services service SET city_id=c.id,city=c.name,state_id=s.id,state=s.name,updated_at=now()
FROM candidates candidate JOIN public.cities c ON c.id=candidate.city_id JOIN public.country_states s ON s.id=c.state_id
WHERE service.id=candidate.service_id;
UPDATE public.services SET city=NULL,updated_at=now() WHERE city IS NOT NULL AND city_id IS NULL;
UPDATE public.services SET state=NULL,updated_at=now() WHERE state IS NOT NULL AND state_id IS NULL;

CREATE OR REPLACE FUNCTION public.canonicalize_service_location()
RETURNS trigger LANGUAGE plpgsql AS $BODY$
DECLARE st public.country_states%ROWTYPE; ct public.cities%ROWTYPE; matches integer;
BEGIN
    NEW.country_code := nullif(upper(btrim(NEW.country_code)), '');
    NEW.city := nullif(regexp_replace(btrim(NEW.city), '\s+', ' ', 'g'), '');
    NEW.state := nullif(btrim(NEW.state), '');
    NEW.state_id := NULL; NEW.city_id := NULL;
    IF NEW.state IS NOT NULL THEN
        SELECT * INTO st FROM public.country_states s WHERE s.is_active AND s.country_code=NEW.country_code
          AND (lower(s.name)=lower(NEW.state) OR EXISTS (SELECT 1 FROM unnest(s.aliases) a WHERE lower(a)=lower(NEW.state)));
        IF NOT FOUND THEN RAISE EXCEPTION 'Choose a defined state' USING ERRCODE='23514'; END IF;
        NEW.state := st.name; NEW.state_id := st.id;
    END IF;
    IF NEW.city IS NOT NULL THEN
        SELECT count(*) INTO matches FROM public.cities c JOIN public.country_states s ON s.id=c.state_id
        WHERE c.is_active AND s.is_active AND s.country_code=NEW.country_code
          AND (NEW.state_id IS NULL OR s.id=NEW.state_id)
          AND (lower(c.name)=lower(NEW.city) OR EXISTS (SELECT 1 FROM unnest(c.aliases) a WHERE lower(a)=lower(NEW.city)));
        IF matches<>1 THEN RAISE EXCEPTION 'Choose a defined city and its state' USING ERRCODE='23514'; END IF;
        SELECT c.* INTO ct FROM public.cities c JOIN public.country_states s ON s.id=c.state_id
        WHERE c.is_active AND s.is_active AND s.country_code=NEW.country_code
          AND (NEW.state_id IS NULL OR s.id=NEW.state_id)
          AND (lower(c.name)=lower(NEW.city) OR EXISTS (SELECT 1 FROM unnest(c.aliases) a WHERE lower(a)=lower(NEW.city)));
        SELECT * INTO st FROM public.country_states WHERE id=ct.state_id;
        NEW.city_id:=ct.id; NEW.city:=ct.name; NEW.state_id:=st.id; NEW.state:=st.name;
    END IF;
    RETURN NEW;
END
$BODY$;
DROP TRIGGER IF EXISTS services_canonical_location ON public.services;
CREATE TRIGGER services_canonical_location BEFORE INSERT OR UPDATE OF city,state,country_code,city_id,state_id
ON public.services FOR EACH ROW EXECUTE FUNCTION public.canonicalize_service_location();

-- Keep compatibility text projections in sync when catalogue names change.
CREATE OR REPLACE FUNCTION public.sync_city_service_names()
RETURNS trigger LANGUAGE plpgsql AS $BODY$
BEGIN
    IF NEW.name IS DISTINCT FROM OLD.name OR NEW.state_id IS DISTINCT FROM OLD.state_id THEN
        UPDATE public.services service SET city=NEW.name,state=s.name,country_code=s.country_code,updated_at=now()
        FROM public.country_states s WHERE s.id=NEW.state_id AND service.city_id=NEW.id;
    END IF;
    RETURN NULL;
END
$BODY$;
DROP TRIGGER IF EXISTS city_service_names ON public.cities;
CREATE TRIGGER city_service_names AFTER UPDATE OF name,state_id ON public.cities
FOR EACH ROW EXECUTE FUNCTION public.sync_city_service_names();
CREATE OR REPLACE FUNCTION public.sync_state_service_names()
RETURNS trigger LANGUAGE plpgsql AS $BODY$
BEGIN
    IF NEW.name IS DISTINCT FROM OLD.name OR NEW.country_code IS DISTINCT FROM OLD.country_code THEN
        UPDATE public.services SET state=NEW.name,country_code=NEW.country_code,updated_at=now() WHERE state_id=NEW.id;
    END IF;
    RETURN NULL;
END
$BODY$;
DROP TRIGGER IF EXISTS state_service_names ON public.country_states;
CREATE TRIGGER state_service_names AFTER UPDATE OF name,country_code ON public.country_states
FOR EACH ROW EXECUTE FUNCTION public.sync_state_service_names();

-- Legacy group assignments are migrated without guessing a different service
-- type: keep existing leaves, otherwise create an explicit general child.
CREATE TEMP TABLE _legacy_roots ON COMMIT DROP AS
SELECT DISTINCT c.id,c.name,c.slug,c.is_active FROM public.categories c
JOIN public.service_categories sc ON sc.category_id=c.id WHERE c.parent_id IS NULL;
-- Resolve each group independently: a leaf from another group cannot replace
-- its meaning. Shared leaves count under every membership, not only primary.
CREATE TEMP TABLE _root_replacements ON COMMIT DROP AS
SELECT sc.service_id,r.id root_id,sc.is_primary was_primary,leaf.category_id
FROM public.service_categories sc JOIN _legacy_roots r ON r.id=sc.category_id
LEFT JOIN LATERAL (
 SELECT other.category_id FROM public.service_categories other
 JOIN public.categories child ON child.id=other.category_id
 WHERE other.service_id=sc.service_id AND child.is_active AND child.parent_id IS NOT NULL
 AND (child.parent_id=r.id OR EXISTS (SELECT 1 FROM public.category_parents p WHERE p.category_id=child.id AND p.parent_id=r.id))
 ORDER BY other.is_primary DESC,other.category_id LIMIT 1
) leaf ON true;
INSERT INTO public.categories(name,slug,parent_id,is_active)
SELECT name || ' — سایر خدمات', 'general-' || slug, id, is_active FROM _legacy_roots r
WHERE EXISTS (SELECT 1 FROM _root_replacements replacement WHERE replacement.root_id=r.id AND replacement.category_id IS NULL)
ON CONFLICT DO NOTHING;
INSERT INTO public.category_parents(category_id,parent_id)
SELECT child.id,child.parent_id FROM public.categories child JOIN _legacy_roots r ON child.slug='general-'||r.slug
ON CONFLICT DO NOTHING;
UPDATE _root_replacements replacement SET category_id=child.id
FROM _legacy_roots r JOIN public.categories child ON child.slug='general-'||r.slug AND child.parent_id=r.id
WHERE replacement.root_id=r.id AND replacement.category_id IS NULL;
DO $BODY$
BEGIN
 IF EXISTS (SELECT 1 FROM _root_replacements WHERE category_id IS NULL) THEN
    RAISE EXCEPTION 'A legacy group could not be migrated to its own child category';
 END IF;
END
$BODY$;
INSERT INTO public.service_categories(service_id,category_id,is_primary)
SELECT DISTINCT service_id,category_id,false FROM _root_replacements
ON CONFLICT DO NOTHING;
-- Remove group-primary flags before promoting leaves (partial unique index).
DELETE FROM public.service_categories sc USING _legacy_roots r WHERE sc.category_id=r.id;
UPDATE public.service_categories sc SET is_primary=true
WHERE (sc.service_id,sc.category_id) IN (
 SELECT service_id,category_id FROM _root_replacements WHERE was_primary
) AND NOT EXISTS (SELECT 1 FROM public.service_categories primary_link WHERE primary_link.service_id=sc.service_id AND primary_link.is_primary);
UPDATE public.services SET updated_at=now() WHERE id IN (SELECT service_id FROM _root_replacements);
DO $BODY$
BEGIN
 IF EXISTS (
    SELECT 1 FROM _root_replacements replacement JOIN public.services service ON service.id=replacement.service_id
    WHERE service.status='published' AND NOT EXISTS (
       SELECT 1 FROM public.service_categories sc JOIN public.categories c ON c.id=sc.category_id
       WHERE sc.service_id=service.id AND sc.is_primary AND c.is_active AND c.parent_id IS NOT NULL
    )
 ) THEN
    RAISE EXCEPTION 'Legacy published classification has no active replacement. Activate its general child or reclassify the listing before migration.';
 END IF;
END
$BODY$;

CREATE OR REPLACE FUNCTION public.validate_service_leaf_category()
RETURNS trigger LANGUAGE plpgsql AS $BODY$
BEGIN
    PERFORM pg_advisory_xact_lock(606125019);
    IF EXISTS (SELECT 1 FROM public.service_categories sc JOIN public.categories c ON c.id=sc.category_id
               WHERE c.parent_id IS NULL) THEN
        RAISE EXCEPTION 'First-level categories are groups; assign a second-level category' USING ERRCODE='23514';
    END IF;
    RETURN NULL;
END
$BODY$;
DROP TRIGGER IF EXISTS service_category_leaf_only ON public.service_categories;
CREATE CONSTRAINT TRIGGER service_category_leaf_only AFTER INSERT OR UPDATE ON public.service_categories
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.validate_service_leaf_category();
DROP TRIGGER IF EXISTS category_assigned_leaf_only ON public.categories;
CREATE CONSTRAINT TRIGGER category_assigned_leaf_only AFTER UPDATE ON public.categories
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.validate_service_leaf_category();

COMMENT ON TABLE public.cities IS 'Shared cities belonging to explicit country_states; aliases resolve alternate spellings. Add missing cities centrally, never per business.';
COMMENT ON TABLE public.service_location_legacy IS 'Internal pre-catalogue location snapshot. Not exposed in public business profiles.';
SET CONSTRAINTS ALL IMMEDIATE;
COMMIT;
