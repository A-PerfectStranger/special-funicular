CREATE OR REPLACE FUNCTION public.e2_validate_batch(data jsonb) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE item jsonb; child jsonb; sid uuid := (data->>'school_id')::uuid;
BEGIN
  IF data IS NULL OR data->>'schema_version' IS DISTINCT FROM '1' OR NOT(data ?& ARRAY['id','school_id','parents','students','links'])
    OR NOT EXISTS(SELECT 1 FROM public.school_roster_school WHERE id=sid AND active)
    OR jsonb_typeof(data->'parents')<>'array' OR jsonb_typeof(data->'students')<>'array'
    OR jsonb_typeof(data->'links')<>'array'
    OR jsonb_array_length(data->'students') NOT BETWEEN 1 AND 1000
    OR jsonb_array_length(data->'parents') NOT BETWEEN 1 AND 2000
    OR jsonb_array_length(data->'links') NOT BETWEEN 1 AND 4000 THEN
    RAISE EXCEPTION 'invalid batch' USING ERRCODE='22023'; END IF;
  FOR item IN SELECT value FROM jsonb_array_elements(data->'parents') LOOP
    IF (item->>'contact') !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'
      OR length(item->>'contact')>254 OR (item->>'contact')<>lower(item->>'contact')
      OR NOT(item ?& ARRAY['id','contact'])
      OR (EXISTS(SELECT 1 FROM public.school_roster_parent WHERE id=(item->>'id')::uuid)
        AND NOT EXISTS(SELECT 1 FROM public.school_roster_enrollment WHERE parent_id=(item->>'id')::uuid
          AND school_id=sid AND contact=item->>'contact'))
      OR (SELECT count(*) FROM jsonb_array_elements(data->'parents') p
          WHERE (p->>'id')::uuid=(item->>'id')::uuid OR p->>'contact'=item->>'contact')<>1 THEN
      RAISE EXCEPTION 'invalid parent' USING ERRCODE='22023'; END IF;
  END LOOP;
  FOR child IN SELECT value FROM jsonb_array_elements(data->'students') LOOP
    IF NOT(child ?& ARRAY['id','site_id','name','windows','blocked'])
      OR length(btrim(child->>'name')) NOT BETWEEN 1 AND 160
      OR jsonb_typeof(child->'blocked')<>'boolean'
      OR NOT public.e2_validate_windows(child->'windows')
      OR NOT EXISTS(SELECT 1 FROM public.school_roster_site si WHERE si.id=(child->>'site_id')::uuid AND si.school_id=sid
        AND EXISTS(SELECT 1 FROM pg_timezone_names WHERE name=si.timezone))
      OR EXISTS(SELECT 1 FROM public.school_roster_student WHERE id=(child->>'id')::uuid)
      OR (SELECT count(*) FROM jsonb_array_elements(data->'students') s WHERE (s->>'id')::uuid=(child->>'id')::uuid)<>1
      OR (SELECT count(*) FROM jsonb_array_elements(data->'links') l
          WHERE (l->>'student_id')::uuid=(child->>'id')::uuid AND l->>'principal'='true')<>1 THEN
      RAISE EXCEPTION 'invalid student' USING ERRCODE='22023'; END IF;
  END LOOP;
  FOR item IN SELECT value FROM jsonb_array_elements(data->'links') LOOP
    IF NOT(item ?& ARRAY['student_id','parent_id','principal'])
      OR jsonb_typeof(item->'principal')<>'boolean'
      OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(data->'students') s WHERE (s->>'id')::uuid=(item->>'student_id')::uuid)
      OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(data->'parents') p WHERE (p->>'id')::uuid=(item->>'parent_id')::uuid)
      OR (SELECT count(*) FROM jsonb_array_elements(data->'links') l
          WHERE (l->>'student_id')::uuid=(item->>'student_id')::uuid AND (l->>'parent_id')::uuid=(item->>'parent_id')::uuid)<>1 THEN
      RAISE EXCEPTION 'invalid link' USING ERRCODE='22023'; END IF;
  END LOOP;
  IF EXISTS(SELECT 1 FROM jsonb_array_elements(data->'parents') p WHERE NOT EXISTS
    (SELECT 1 FROM jsonb_array_elements(data->'links') l WHERE (l->>'parent_id')::uuid=(p->>'id')::uuid)) THEN
    RAISE EXCEPTION 'unlinked parent' USING ERRCODE='22023'; END IF;
END $$;


ALTER FUNCTION public.e2_validate_batch(jsonb) OWNER TO retiro_evidence_writer;
REVOKE ALL ON FUNCTION public.e2_validate_batch(jsonb) FROM PUBLIC;
