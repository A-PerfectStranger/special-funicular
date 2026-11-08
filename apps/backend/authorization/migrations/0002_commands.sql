-- E2 command boundary. No application credential receives free writes to these tables.
DO $$ DECLARE tab text;
BEGIN
  FOREACH tab IN ARRAY ARRAY['school_roster_importbatch','school_roster_enrollment',
    'identity_invitation','authorization_policy','authorization_caregiver',
    'authorization_authorization','authorization_command'] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',tab);
    EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',tab);
    EXECUTE format('CREATE POLICY command_writer ON public.%I TO retiro_evidence_writer USING(true) WITH CHECK(true)',tab);
    EXECUTE format('GRANT SELECT,INSERT,UPDATE ON public.%I TO retiro_evidence_writer',tab);
  END LOOP;
END $$;
GRANT INSERT,UPDATE ON public.identity_account,public.school_roster_parent,
  public.school_roster_student,public.school_roster_link,public.school_roster_school TO retiro_evidence_writer;

CREATE FUNCTION public.e2_validate_windows(windows jsonb) RETURNS boolean
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog AS $$
DECLARE w jsonb;
BEGIN
  IF windows IS NULL OR jsonb_typeof(windows)<>'array' OR jsonb_array_length(windows) NOT BETWEEN 1 AND 32 THEN RETURN false; END IF;
  FOR w IN SELECT value FROM jsonb_array_elements(windows) LOOP
    IF jsonb_typeof(w) IS DISTINCT FROM 'object' OR NOT (w ?& ARRAY['weekday','from','until','start_date','end_date'])
      OR EXISTS(SELECT 1 FROM jsonb_each(w) x WHERE x.value='null'::jsonb)
      OR jsonb_typeof(w->'weekday') IS DISTINCT FROM 'number'
      OR (w->>'weekday')::int NOT BETWEEN 1 AND 7
      OR (w->>'from') !~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'
      OR (w->>'until') !~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'
      OR (w->>'from')::time >= (w->>'until')::time
      OR (w->>'start_date') !~ '^\d{4}-\d{2}-\d{2}$'
      OR (w->>'end_date') !~ '^\d{4}-\d{2}-\d{2}$'
      OR (w->>'start_date')::date > (w->>'end_date')::date THEN RETURN false; END IF;
  END LOOP;
  RETURN true;
END $$;

CREATE FUNCTION public.e2_validate_batch(data jsonb) RETURNS void
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
          WHERE p->>'id'=item->>'id' OR p->>'contact'=item->>'contact')<>1 THEN
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
      OR (SELECT count(*) FROM jsonb_array_elements(data->'students') s WHERE s->>'id'=child->>'id')<>1
      OR (SELECT count(*) FROM jsonb_array_elements(data->'links') l
          WHERE l->>'student_id'=child->>'id' AND l->>'principal'='true')<>1 THEN
      RAISE EXCEPTION 'invalid student' USING ERRCODE='22023'; END IF;
  END LOOP;
  FOR item IN SELECT value FROM jsonb_array_elements(data->'links') LOOP
    IF NOT(item ?& ARRAY['student_id','parent_id','principal'])
      OR jsonb_typeof(item->'principal')<>'boolean'
      OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(data->'students') s WHERE s->>'id'=item->>'student_id')
      OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(data->'parents') p WHERE p->>'id'=item->>'parent_id')
      OR (SELECT count(*) FROM jsonb_array_elements(data->'links') l
          WHERE l->>'student_id'=item->>'student_id' AND l->>'parent_id'=item->>'parent_id')<>1 THEN
      RAISE EXCEPTION 'invalid link' USING ERRCODE='22023'; END IF;
  END LOOP;
  IF EXISTS(SELECT 1 FROM jsonb_array_elements(data->'parents') p WHERE NOT EXISTS
    (SELECT 1 FROM jsonb_array_elements(data->'links') l WHERE l->>'parent_id'=p->>'id')) THEN
    RAISE EXCEPTION 'unlinked parent' USING ERRCODE='22023'; END IF;
END $$;

CREATE FUNCTION public.e2_import(operation text, batch_id uuid, payload text, expected_hash text,
  operator_name text, approval_ref text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE b public.school_roster_importbatch; data jsonb; item jsonb; stamp timestamptz:=clock_timestamp();
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
    IF b.id IS NULL OR b.digest<>expected_hash THEN RAISE EXCEPTION 'batch conflict' USING ERRCODE='22023'; END IF;
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
      PERFORM public.e2_validate_batch(data);
      FOR item IN SELECT value FROM jsonb_array_elements(data->'parents') LOOP
        INSERT INTO public.school_roster_parent(id) VALUES((item->>'id')::uuid) ON CONFLICT(id) DO NOTHING;
        INSERT INTO public.school_roster_enrollment(parent_id,school_id,contact,approval)
          VALUES((item->>'id')::uuid,b.school_id,item->>'contact',b.approval) ON CONFLICT(parent_id) DO NOTHING;
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

CREATE FUNCTION public.e2_invite(parent_id uuid, token_hash text, operator_name text,
  approval_ref text, correlation uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE e public.school_roster_enrollment; stamp timestamptz:=clock_timestamp();
BEGIN
  IF session_user<>'retiro_importer' OR operator_name IS NULL OR token_hash !~ '^[0-9a-f]{64}$'
    OR length(btrim(operator_name)) NOT BETWEEN 1 AND 160 OR approval_ref IS NULL OR length(btrim(approval_ref)) NOT BETWEEN 1 AND 160 THEN
    RAISE EXCEPTION 'technical command denied' USING ERRCODE='42501'; END IF;
  SELECT * INTO e FROM public.school_roster_enrollment WHERE school_roster_enrollment.parent_id=e2_invite.parent_id FOR UPDATE;
  IF NOT FOUND OR NOT EXISTS(SELECT 1 FROM public.school_roster_parent p
    JOIN public.school_roster_school s ON s.id=e.school_id AND s.active
    WHERE p.id=e.parent_id AND p.account_id IS NULL) THEN
    RAISE EXCEPTION 'invitation denied' USING ERRCODE='28000'; END IF;
  UPDATE public.identity_invitation SET revoked_at=stamp WHERE identity_invitation.parent_id=e.parent_id
    AND used_at IS NULL AND revoked_at IS NULL;
  INSERT INTO public.identity_invitation(id,parent_id,token_hash,issued_at,expires_at)
    VALUES(correlation,e.parent_id,token_hash,stamp,stamp+interval '24 hours');
  PERFORM public.e1_append('INVITATION_ISSUED',NULL,e.school_id,correlation,
    jsonb_build_object('parent_id',e.parent_id,'operator',operator_name,'approval',approval_ref));
END $$;

CREATE FUNCTION public.e2_redeem(login_id uuid, token_hash text, issuer text, subject text,
  verified_contact text, authenticated_at timestamptz) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE inv public.identity_invitation; e public.school_roster_enrollment; aid uuid:=gen_random_uuid();
  stamp timestamptz:=clock_timestamp();
BEGIN
  -- Serialize against invitation replacement. Only this preloaded parent is associated.
  SELECT en.* INTO e FROM public.school_roster_enrollment en JOIN public.identity_invitation i
    ON i.parent_id=en.parent_id WHERE i.token_hash=e2_redeem.token_hash FOR UPDATE OF en;
  IF NOT FOUND THEN RAISE EXCEPTION 'activation denied' USING ERRCODE='28000'; END IF;
  SELECT * INTO inv FROM public.identity_invitation i WHERE i.token_hash=e2_redeem.token_hash FOR UPDATE;
  stamp:=clock_timestamp();
  IF inv.used_at IS NOT NULL OR inv.revoked_at IS NOT NULL OR inv.expires_at<=stamp
    OR verified_contact IS NULL OR e.contact<>lower(verified_contact)
    OR issuer IS NULL OR subject IS NULL OR length(subject) NOT BETWEEN 1 AND 255
    OR authenticated_at NOT BETWEEN stamp-interval '5 minutes' AND stamp+interval '30 seconds'
    OR NOT EXISTS(SELECT 1 FROM public.identity_loginrequest WHERE id=login_id
      AND purpose='activate' AND channel='mobile' AND consumed_at IS NOT NULL AND expires_at>stamp)
    OR NOT EXISTS(SELECT 1 FROM public.school_roster_school WHERE id=e.school_id AND active)
    OR EXISTS(SELECT 1 FROM public.school_roster_parent WHERE id=e.parent_id AND account_id IS NOT NULL)
    OR EXISTS(SELECT 1 FROM public.identity_account a WHERE a.issuer=e2_redeem.issuer AND a.subject=e2_redeem.subject) THEN
    RAISE EXCEPTION 'activation denied' USING ERRCODE='28000'; END IF;
  INSERT INTO public.identity_account(id,issuer,subject,role,active,version)
    VALUES(aid,issuer,subject,'PADRE',true,1);
  UPDATE public.school_roster_parent SET account_id=aid WHERE id=e.parent_id;
  UPDATE public.identity_invitation SET used_at=stamp WHERE id=inv.id;
  PERFORM public.e1_append('PARENT_ACTIVATED',aid,e.school_id,inv.id,
    jsonb_build_object('parent_id',e.parent_id,'result','ASSOCIATED'));
END $$;

CREATE FUNCTION public.e2_students() RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
 SELECT coalesce(jsonb_agg(jsonb_build_object('id',s.id,'name',s.display_name,'site_id',s.site_id,
   'timezone',si.timezone,'principal',l.principal,'link_version',l.version,
   'can_authorize',l.principal AND NOT coalesce(po.blocked,true),
   'windows',coalesce(po.windows,'[]'::jsonb),'blocked',coalesce(po.blocked,true)) ORDER BY s.id),'[]'::jsonb)
 FROM public.e1_current_account() a JOIN public.school_roster_parent p ON p.account_id=a.id
 JOIN public.school_roster_link l ON l.parent_id=p.id AND l.active
 JOIN public.school_roster_student s ON s.id=l.student_id AND s.active
 JOIN public.school_roster_school sch ON sch.id=s.school_id AND sch.active
 JOIN public.school_roster_site si ON si.id=s.site_id
 LEFT JOIN public.authorization_policy po ON po.student_id=s.id WHERE a.role='PADRE';
$$;

CREATE FUNCTION public.e2_schedule_valid(student uuid, schedule jsonb) RETURNS boolean
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE p public.authorization_policy; zone text; item jsonb; f timestamptz; t timestamptz;
  lf timestamp; lt timestamp; seen date[]:='{}';
BEGIN
 SELECT * INTO p FROM public.authorization_policy WHERE student_id=student;
 SELECT si.timezone INTO zone FROM public.school_roster_site si
 JOIN public.school_roster_student s ON s.site_id=si.id WHERE s.id=student;
 IF p.student_id IS NULL OR p.blocked OR schedule IS NULL OR jsonb_typeof(schedule)<>'array'
   OR jsonb_array_length(schedule) NOT BETWEEN 1 AND 366 THEN RETURN false; END IF;
 FOR item IN SELECT value FROM jsonb_array_elements(schedule) LOOP
   IF NOT(item ?& ARRAY['from','until']) OR item->>'from' IS NULL OR item->>'until' IS NULL
     OR (item->>'from') !~ '(Z|[+-][0-9]{2}:[0-9]{2})$'
     OR (item->>'until') !~ '(Z|[+-][0-9]{2}:[0-9]{2})$' THEN RETURN false; END IF;
   f:=(item->>'from')::timestamptz; t:=(item->>'until')::timestamptz;
   lf:=f AT TIME ZONE zone; lt:=t AT TIME ZONE zone;
   IF t<=f OR lf::date<>lt::date OR lf::date=ANY(seen)
     OR f<clock_timestamp() OR t>clock_timestamp()+interval '366 days'
     OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p.windows) w
       WHERE (w->>'weekday')::int=extract(isodow FROM lf)
         AND lf::date BETWEEN (w->>'start_date')::date AND (w->>'end_date')::date
         AND lf::time >= (w->>'from')::time AND lt::time <= (w->>'until')::time) THEN RETURN false; END IF;
   seen:=array_append(seen,lf::date);
 END LOOP;
 RETURN true;
END $$;

CREATE FUNCTION public.e2_family_command(operation text, correlation uuid, data jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.identity_account; student uuid:=(data->>'student_id')::uuid;
 l public.school_roster_link; cg public.authorization_caregiver; au public.authorization_authorization;
 p public.authorization_policy; c public.authorization_command; rid uuid:=gen_random_uuid();
 hash text:=encode(sha256(convert_to(jsonb_build_object('operation',operation,'data',data)::text,'UTF8')),'hex');
 result jsonb; eid uuid; seq bigint; school uuid; stamp timestamptz:=clock_timestamp();
BEGIN
 SELECT * INTO a FROM public.e1_current_account() WHERE role='PADRE';
 IF NOT FOUND THEN RAISE EXCEPTION 'family command denied' USING ERRCODE='42501'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(correlation::text,3));
 SELECT * INTO c FROM public.authorization_command WHERE id=correlation;
 IF FOUND THEN
   IF c.actor_id<>a.id OR c.digest<>hash THEN RAISE EXCEPTION 'command conflict' USING ERRCODE='22023'; END IF;
   RETURN c.result;
 END IF;
 SELECT school_id INTO school FROM public.school_roster_student WHERE id=student AND active FOR UPDATE;
 stamp:=clock_timestamp();
 SELECT li.* INTO l FROM public.school_roster_link li JOIN public.school_roster_parent pa ON pa.id=li.parent_id
   WHERE li.student_id=student AND pa.account_id=a.id AND li.active AND li.principal;
 IF l.id IS NULL OR school IS NULL OR NOT EXISTS(SELECT 1 FROM public.school_roster_school WHERE id=school AND active)
   OR NOT EXISTS(SELECT 1 FROM public.e1_current_account() WHERE id=a.id)
   OR NOT EXISTS(SELECT 1 FROM public.identity_session WHERE id IN
     (SELECT s.id FROM public.identity_session s WHERE s.access_hash=current_setting('app.session_hash',true))
       AND authenticated_at BETWEEN stamp-interval '5 minutes' AND stamp+interval '30 seconds') THEN
   RAISE EXCEPTION 'family command denied' USING ERRCODE='42501'; END IF;
 SELECT * INTO p FROM public.authorization_policy WHERE student_id=student;
 IF operation IN ('CREATE_CAREGIVER','UPDATE_CAREGIVER') THEN
   IF NOT(data ?& ARRAY['name','document','photo']) OR data->>'name' IS NULL OR data->>'document' IS NULL OR data->>'photo' IS NULL OR length(btrim(data->>'name')) NOT BETWEEN 1 AND 160
     OR length(btrim(data->>'document')) NOT BETWEEN 1 AND 40
     OR length(decode(data->>'photo','base64')) NOT BETWEEN 10 AND 300000
     OR encode(substring(decode(data->>'photo','base64') FROM 1 FOR 3),'hex')<>'ffd8ff' THEN
     RAISE EXCEPTION 'invalid caregiver' USING ERRCODE='22023'; END IF;
   IF operation='CREATE_CAREGIVER' THEN
     INSERT INTO public.authorization_caregiver(id,student_id,created_by_id,name,document,photo,version,active)
       VALUES(rid,student,a.id,data->>'name',data->>'document',decode(data->>'photo','base64'),1,true);
   ELSE
     SELECT * INTO cg FROM public.authorization_caregiver WHERE id=(data->>'id')::uuid AND student_id=student FOR UPDATE;
     IF NOT FOUND OR NOT cg.active OR data->>'version' IS NULL OR cg.version<>(data->>'version')::bigint THEN
       RAISE EXCEPTION 'caregiver conflict' USING ERRCODE='22023'; END IF;
     rid:=cg.id;
     UPDATE public.authorization_caregiver SET name=data->>'name',document=data->>'document',
       photo=decode(data->>'photo','base64'),version=version+1 WHERE id=rid;
     UPDATE public.authorization_authorization SET revoked_at=stamp,version=version+1
       WHERE caregiver_id=rid AND revoked_at IS NULL;
   END IF;
 ELSIF operation='CREATE_AUTHORIZATION' THEN
   SELECT * INTO cg FROM public.authorization_caregiver WHERE id=(data->>'caregiver_id')::uuid
     AND student_id=student AND active FOR UPDATE;
   IF NOT FOUND OR NOT public.e2_schedule_valid(student,data->'schedule') THEN
     RAISE EXCEPTION 'authorization denied' USING ERRCODE='22023'; END IF;
   INSERT INTO public.authorization_authorization(id,student_id,caregiver_id,created_by_id,
     caregiver_version,link_version,policy_version,schedule,version)
     VALUES(rid,student,cg.id,a.id,cg.version,l.version,p.version,data->'schedule',1);
 ELSIF operation='REVOKE_AUTHORIZATION' THEN
   SELECT * INTO au FROM public.authorization_authorization WHERE id=(data->>'id')::uuid AND student_id=student FOR UPDATE;
   IF NOT FOUND THEN RAISE EXCEPTION 'authorization denied' USING ERRCODE='42501'; END IF;
   rid:=au.id;
   UPDATE public.authorization_authorization SET revoked_at=coalesce(revoked_at,stamp),
     version=version+CASE WHEN revoked_at IS NULL THEN 1 ELSE 0 END WHERE id=rid;
 ELSE RAISE EXCEPTION 'unknown command' USING ERRCODE='22023';
 END IF;
 eid:=public.e1_append(operation,a.id,school,correlation,
   jsonb_build_object('student_id',student,'object_id',rid,'link_version',l.version,
     'command_digest',hash,'result','APPLIED'));
 SELECT sequence INTO seq FROM public.evidence_event WHERE id=eid;
 result:=jsonb_build_object('id',rid,'status','APPLIED','event_sequence',seq);
 INSERT INTO public.authorization_command(id,actor_id,digest,result) VALUES(correlation,a.id,hash,result);
 RETURN result;
END $$;

CREATE FUNCTION public.e2_family_records(student uuid) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM public.school_roster_student WHERE id=student AND active)
   OR NOT public.e1_can_read_student(student) THEN RAISE EXCEPTION 'family read denied' USING ERRCODE='42501'; END IF;
 RETURN jsonb_build_object('caregivers',coalesce((SELECT jsonb_agg(jsonb_build_object('id',c.id,
   'name',c.name,'document',c.document,'version',c.version) ORDER BY c.id)
   FROM public.authorization_caregiver c WHERE c.student_id=student AND c.active),'[]'::jsonb),
   'authorizations',coalesce((SELECT jsonb_agg(jsonb_build_object('id',au.id,'caregiver_id',au.caregiver_id,
     'schedule',au.schedule,'version',au.version,'revoked',au.revoked_at IS NOT NULL) ORDER BY au.id)
     FROM public.authorization_authorization au WHERE au.student_id=student),'[]'::jsonb));
END $$;

CREATE FUNCTION public.e2_caregiver_photo(caregiver uuid) RETURNS bytea
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
 SELECT c.photo FROM public.authorization_caregiver c JOIN public.school_roster_student s ON s.id=c.student_id AND s.active
 WHERE c.id=caregiver AND c.active AND public.e1_can_read_student(c.student_id);
$$;

-- Technical commands invalidate all authorizations under the same student lock that
-- future E3 issuance/confirmation must acquire before reading versions.
CREATE FUNCTION public.e2_technical(operation text, correlation uuid, school uuid, target uuid,
 data jsonb, operator_name text, approval_ref text, reason text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.identity_account; child record; current_parent uuid; affected uuid[]:='{}';
 hash text; event_id uuid; existing bytea; stamp timestamptz:=clock_timestamp();
BEGIN
 IF session_user<>'retiro_importer' OR operator_name IS NULL OR length(btrim(operator_name)) NOT BETWEEN 1 AND 160
   OR approval_ref IS NULL OR length(btrim(approval_ref)) NOT BETWEEN 1 AND 160 OR reason IS NULL OR length(btrim(reason)) NOT BETWEEN 1 AND 500
   OR operation NOT IN ('PROVISION','DEACTIVATE','CHANGE_PRINCIPAL','SET_POLICY','REVOKE_INVITATION') THEN
   RAISE EXCEPTION 'technical command denied' USING ERRCODE='42501'; END IF;
 hash:=encode(sha256(convert_to(jsonb_build_object('operation',operation,'school',school,'target',target,
   'data',data,'operator',operator_name,'approval',approval_ref,'reason',reason)::text,'UTF8')),'hex');
 PERFORM pg_advisory_xact_lock(hashtextextended(correlation::text,4));
 SELECT canonical INTO existing FROM public.evidence_event WHERE kind LIKE 'TECHNICAL_%' AND correlation_id=correlation;
 IF FOUND THEN
   IF (convert_from(existing,'UTF8')::jsonb->'snapshot'->>'command_digest')<>hash THEN
     RAISE EXCEPTION 'technical conflict' USING ERRCODE='22023'; END IF;
   RETURN jsonb_build_object('status','APPLIED');
 END IF;
 IF operation IN ('CHANGE_PRINCIPAL','SET_POLICY') THEN
   PERFORM 1 FROM public.school_roster_student WHERE id=target AND school_id=school AND active FOR UPDATE;
   IF NOT FOUND THEN RAISE EXCEPTION 'scope denied' USING ERRCODE='42501'; END IF;
   IF operation='CHANGE_PRINCIPAL' THEN
     IF NOT EXISTS(SELECT 1 FROM public.school_roster_link WHERE student_id=target
       AND parent_id=(data->>'parent_id')::uuid AND active) THEN
       RAISE EXCEPTION 'scope denied' USING ERRCODE='42501'; END IF;
     UPDATE public.school_roster_link SET principal=false,version=version+1 WHERE student_id=target AND active AND principal;
     UPDATE public.school_roster_link SET principal=true,version=version+1
       WHERE student_id=target AND parent_id=(data->>'parent_id')::uuid AND active;
   ELSE
     IF NOT public.e2_validate_windows(data->'windows') OR jsonb_typeof(data->'blocked') IS DISTINCT FROM 'boolean' THEN
       RAISE EXCEPTION 'invalid policy' USING ERRCODE='22023'; END IF;
     INSERT INTO public.authorization_policy(student_id,windows,blocked,version)
       VALUES(target,data->'windows',(data->>'blocked')::boolean,1)
       ON CONFLICT(student_id) DO UPDATE SET windows=EXCLUDED.windows,blocked=EXCLUDED.blocked,
         version=public.authorization_policy.version+1;
   END IF;
   UPDATE public.authorization_authorization SET revoked_at=stamp,version=version+1 WHERE student_id=target AND revoked_at IS NULL;
   UPDATE public.identity_account SET version=version+1 WHERE id IN
     (SELECT p.account_id FROM public.school_roster_parent p JOIN public.school_roster_link l ON l.parent_id=p.id
       WHERE l.student_id=target AND l.active);
 ELSIF operation='PROVISION' THEN
   IF NOT(data ?& ARRAY['role','issuer','subject','site_id']) OR data->>'role' IS NULL OR data->>'issuer' IS NULL OR data->>'subject' IS NULL OR data->>'role' NOT IN ('GUARDIA','ADMIN_ESCUELA','ADMIN_SISTEMA')
     OR length(data->>'issuer') NOT BETWEEN 1 AND 512 OR length(data->>'subject') NOT BETWEEN 1 AND 255
     OR (data->>'role'='ADMIN_SISTEMA' AND school IS NOT NULL)
     OR (data->>'role'<>'ADMIN_SISTEMA' AND NOT EXISTS(SELECT 1 FROM public.school_roster_school WHERE id=school AND active)) THEN
     RAISE EXCEPTION 'invalid provisioning' USING ERRCODE='22023'; END IF;
   INSERT INTO public.identity_account(id,issuer,subject,role,school_id,site_id,active,version)
     VALUES(target,data->>'issuer',data->>'subject',data->>'role',school,(data->>'site_id')::uuid,true,1);
 ELSIF operation='DEACTIVATE' THEN
   SELECT * INTO a FROM public.identity_account WHERE id=target;
   IF NOT FOUND OR (a.role<>'PADRE' AND a.school_id IS DISTINCT FROM school) OR
     (a.role='PADRE' AND NOT EXISTS(SELECT 1 FROM public.school_roster_parent p JOIN public.school_roster_link l ON l.parent_id=p.id
       WHERE p.account_id=a.id AND l.school_id=school AND l.active)) THEN
     RAISE EXCEPTION 'scope denied' USING ERRCODE='42501'; END IF;
   -- A parent account can span schools: its global disable locks all linked students.
   FOR child IN SELECT s.id FROM public.school_roster_student s JOIN public.school_roster_link l ON l.student_id=s.id
     JOIN public.school_roster_parent p ON p.id=l.parent_id WHERE p.account_id=a.id ORDER BY s.id FOR UPDATE OF s LOOP
     affected:=array_append(affected,child.id);
   END LOOP;
   UPDATE public.authorization_authorization SET revoked_at=stamp,version=version+1 WHERE student_id=ANY(affected) AND revoked_at IS NULL;
   UPDATE public.identity_account SET active=false WHERE id=target;
 ELSE
   UPDATE public.identity_invitation SET revoked_at=coalesce(revoked_at,stamp) WHERE id=target AND parent_id IN
     (SELECT parent_id FROM public.school_roster_enrollment WHERE school_id=school);
   IF NOT FOUND THEN RAISE EXCEPTION 'scope denied' USING ERRCODE='42501'; END IF;
 END IF;
 event_id:=public.e1_append('TECHNICAL_'||operation,NULL,school,correlation,
   jsonb_build_object('target',target,'operator',operator_name,'approval',approval_ref,'reason',reason,
     'credential',session_user,'command_digest',hash,'result','APPLIED'));
 RETURN jsonb_build_object('status','APPLIED');
END $$;

DO $$ DECLARE fn record;
BEGIN
 FOR fn IN SELECT p.oid::regprocedure signature FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
   WHERE n.nspname='public' AND p.proname LIKE 'e2_%' LOOP
   EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',fn.signature);
   EXECUTE format('ALTER FUNCTION %s OWNER TO retiro_evidence_writer',fn.signature);
 END LOOP;
END $$;
GRANT EXECUTE ON FUNCTION public.e2_import(text,uuid,text,text,text,text),
  public.e2_invite(uuid,text,text,text,uuid),public.e2_technical(text,uuid,uuid,uuid,jsonb,text,text,text) TO retiro_importer;
GRANT EXECUTE ON FUNCTION public.e2_redeem(uuid,text,text,text,text,timestamptz),public.e2_students(),
 public.e2_family_command(text,uuid,jsonb),public.e2_family_records(uuid),public.e2_caregiver_photo(uuid) TO retiro_runtime;
