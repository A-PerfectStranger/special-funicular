CREATE OR REPLACE FUNCTION public.e2_import(operation text, batch_id uuid, payload text, expected_hash text,
  operator_name text, approval_ref text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE pid uuid; b public.school_roster_importbatch; data jsonb; item jsonb; stamp timestamptz:=clock_timestamp();
BEGIN
  IF session_user<>'retiro_importer' OR operator_name IS NULL OR length(btrim(operator_name)) NOT BETWEEN 1 AND 160
    OR operation NOT IN ('STAGE','APPROVE','PROMOTE') OR expected_hash !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'technical command denied' USING ERRCODE='42501'; END IF;
  PERFORM pg_advisory_xact_lock(hashtextextended(batch_id::text,2));
  SELECT * INTO b FROM public.school_roster_importbatch WHERE id=batch_id FOR UPDATE;
  IF operation='STAGE' THEN
    IF length(payload)>4000000 OR encode(sha256(convert_to(payload,'UTF8')),'hex')<>expected_hash THEN
      RAISE EXCEPTION 'batch hash mismatch' USING ERRCODE='22023'; END IF;
    IF b.id IS NOT NULL THEN
      IF b.digest<>expected_hash OR b.payload<>payload THEN RAISE EXCEPTION 'batch conflict' USING ERRCODE='22023'; END IF;
    ELSE
      data:=payload::jsonb;
      IF (data->>'id')::uuid<>batch_id THEN RAISE EXCEPTION 'batch conflict' USING ERRCODE='22023'; END IF;
      PERFORM public.e2_validate_batch(data);
      INSERT INTO public.school_roster_importbatch(id,school_id,payload,digest,operator,approval,staged_at)
        VALUES(batch_id,(data->>'school_id')::uuid,payload,expected_hash,operator_name,'',stamp);
      PERFORM public.e1_append('BULK_STAGED',NULL,(data->>'school_id')::uuid,batch_id,
        jsonb_build_object('digest',expected_hash,'operator',operator_name,'credential',session_user));
    END IF;
  ELSE
    IF b.id IS NULL OR b.digest<>expected_hash
      OR encode(sha256(convert_to(b.payload,'UTF8')),'hex')<>b.digest THEN
      RAISE EXCEPTION 'batch conflict' USING ERRCODE='22023'; END IF;
    IF operation='APPROVE' THEN
      IF length(btrim(approval_ref)) NOT BETWEEN 1 AND 160 OR
        (b.approved_at IS NOT NULL AND b.approval<>approval_ref) THEN
        RAISE EXCEPTION 'approval mismatch' USING ERRCODE='22023'; END IF;
      IF b.approved_at IS NULL THEN
        UPDATE public.school_roster_importbatch SET approved_at=stamp,approval=approval_ref WHERE id=batch_id;
        PERFORM public.e1_append('BULK_APPROVED',NULL,b.school_id,batch_id,
          jsonb_build_object('digest',b.digest,'approval',approval_ref,'operator',operator_name));
      END IF;
    ELSIF b.promoted_at IS NULL THEN
      IF b.approved_at IS NULL THEN RAISE EXCEPTION 'approval required' USING ERRCODE='42501'; END IF;
      PERFORM 1 FROM public.school_roster_school WHERE id=b.school_id AND active FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION 'school unavailable' USING ERRCODE='22023'; END IF;
      data:=b.payload::jsonb;
      -- Parent identity is global even though the approved family scope is one school.
      -- Serialize first enrollment across different school locks in canonical UUID order.
      FOR pid IN SELECT DISTINCT (value->>'id')::uuid FROM jsonb_array_elements(data->'parents') ORDER BY 1 LOOP
        PERFORM pg_advisory_xact_lock(hashtextextended(pid::text,5));
      END LOOP;
      PERFORM public.e2_validate_batch(data);
      FOR item IN SELECT value FROM jsonb_array_elements(data->'parents') LOOP
        INSERT INTO public.school_roster_parent(id) VALUES((item->>'id')::uuid) ON CONFLICT(id) DO NOTHING;
        INSERT INTO public.school_roster_enrollment(parent_id,school_id,contact,approval)
          VALUES((item->>'id')::uuid,b.school_id,item->>'contact',b.approval) ON CONFLICT(parent_id) DO NOTHING;
        PERFORM 1 FROM public.school_roster_enrollment WHERE parent_id=(item->>'id')::uuid
          AND school_id=b.school_id AND contact=item->>'contact' FOR SHARE;
        IF NOT FOUND THEN RAISE EXCEPTION 'family scope conflict' USING ERRCODE='22023'; END IF;
      END LOOP;
      FOR item IN SELECT value FROM jsonb_array_elements(data->'students') LOOP
        INSERT INTO public.school_roster_student(id,school_id,site_id,display_name,active)
          VALUES((item->>'id')::uuid,b.school_id,(item->>'site_id')::uuid,item->>'name',true);
        INSERT INTO public.authorization_policy(student_id,windows,blocked,version)
          VALUES((item->>'id')::uuid,item->'windows',(item->>'blocked')::boolean,1);
      END LOOP;
      FOR item IN SELECT value FROM jsonb_array_elements(data->'links') LOOP
        INSERT INTO public.school_roster_link(id,school_id,student_id,parent_id,active,principal,version)
          VALUES(gen_random_uuid(),b.school_id,(item->>'student_id')::uuid,(item->>'parent_id')::uuid,
            true,(item->>'principal')::boolean,1);
      END LOOP;
      UPDATE public.school_roster_importbatch SET promoted_at=stamp WHERE id=batch_id;
      PERFORM public.e1_append('BULK_PROMOTED',NULL,b.school_id,batch_id,
        jsonb_build_object('digest',b.digest,'approval',b.approval,'operator',operator_name,
          'students',jsonb_array_length(data->'students'),'parents',jsonb_array_length(data->'parents')));
    END IF;
  END IF;
  SELECT * INTO b FROM public.school_roster_importbatch WHERE id=batch_id;
  RETURN jsonb_build_object('id',b.id,'digest',b.digest,'approved',b.approved_at IS NOT NULL,
    'promoted',b.promoted_at IS NOT NULL);
END $$;


ALTER FUNCTION public.e2_import(text,uuid,text,text,text,text) OWNER TO retiro_evidence_writer;
REVOKE ALL ON FUNCTION public.e2_import(text,uuid,text,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.e2_import(text,uuid,text,text,text,text) TO retiro_importer;
