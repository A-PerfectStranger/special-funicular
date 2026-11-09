-- Revalidate current access after acquiring the student lock. A session that
-- expired while waiting cannot read sensitive data or commit a pickup command.
-- Existing ownership, search_path and EXECUTE grants are preserved.

CREATE OR REPLACE FUNCTION public.e3_issue(action text, correlation uuid, aid uuid, requested timestamptz, token_hash text,
 source_episode uuid, origin_hash text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.identity_account; au public.authorization_authorization; s public.school_roster_student;
 l public.school_roster_link; ep public.pickup_episode; previous public.pickup_token; c public.pickup_command;
 zone text; finish timestamptz; day date; stamp timestamptz; eid uuid; result jsonb; tid uuid:=gen_random_uuid();
 hash text:=encode(sha256(convert_to(jsonb_build_object('action',action,'authorization',aid,'requested',requested,'source',source_episode)::text,'UTF8')),'hex');
BEGIN
 a:=public.e3_actor('PADRE');
 PERFORM pg_advisory_xact_lock(hashtextextended(correlation::text,30));
 PERFORM public.e3_actor('PADRE');
 SELECT * INTO c FROM public.pickup_command WHERE id=correlation;
 IF FOUND THEN
  IF c.actor_id<>a.id OR c.digest<>hash THEN RETURN jsonb_build_object('error','CONFLICT'); END IF;
  RETURN c.result||jsonb_build_object('issued',false);
 END IF;
 IF action NOT IN ('ISSUE','RESCHEDULE') OR requested IS NULL OR NOT isfinite(requested)
   OR token_hash IS NULL OR token_hash !~ '^[0-9a-f]{64}$' OR origin_hash IS NULL OR origin_hash !~ '^[0-9a-f]{64}$' THEN
  RAISE EXCEPTION 'invalid pickup input' USING ERRCODE='22023'; END IF;
 IF NOT public.e3_limit('issue:'||a.id::text) OR NOT public.e3_limit('issue-origin:'||origin_hash||':'||a.id::text) THEN
  RETURN jsonb_build_object('error','RATE_LIMITED'); END IF;
 SELECT * INTO au FROM public.authorization_authorization WHERE id=aid;
 SELECT * INTO s FROM public.school_roster_student WHERE id=au.student_id AND active FOR UPDATE;
 SELECT * INTO au FROM public.authorization_authorization WHERE id=aid FOR UPDATE;
 PERFORM public.e3_actor('PADRE');
 SELECT li.* INTO l FROM public.school_roster_link li JOIN public.school_roster_parent p ON p.id=li.parent_id
  WHERE li.student_id=s.id AND li.active AND li.principal AND p.account_id=a.id;
 stamp:=clock_timestamp();
 IF s.id IS NULL OR l.id IS NULL OR au.created_by_id<>a.id OR au.revoked_at IS NOT NULL
  OR NOT public.e3_clock_ok() OR NOT EXISTS(SELECT 1 FROM public.identity_session se WHERE se.access_hash=current_setting('app.session_hash',true)
   AND se.authenticated_at BETWEEN stamp-interval '5 minutes' AND stamp+interval '30 seconds') THEN
  RETURN jsonb_build_object('error','DENIED'); END IF;
 SELECT timezone INTO zone FROM public.school_roster_site WHERE id=s.site_id;
 day:=(requested AT TIME ZONE zone)::date;
 INSERT INTO public.pickup_episode(id,student_id,local_date) VALUES(gen_random_uuid(),s.id,day) ON CONFLICT(student_id,local_date) DO NOTHING;
 SELECT * INTO ep FROM public.pickup_episode WHERE student_id=s.id AND local_date=day FOR UPDATE;
 IF ep.closed_at IS NOT NULL THEN RETURN jsonb_build_object('error','CLOSED'); END IF;
 SELECT * INTO previous FROM public.pickup_token WHERE episode_id=ep.id ORDER BY issued_at DESC,id DESC LIMIT 1;
 IF action='ISSUE' AND previous.id IS NOT NULL THEN
  IF previous.authorization_id<>aid OR previous.valid_from<>requested THEN RETURN jsonb_build_object('error','RESCHEDULE_REQUIRED'); END IF;
  finish:=previous.expires_at;
 ELSE
  IF requested<stamp OR requested>stamp+interval '24 hours' THEN RETURN jsonb_build_object('error','INVALID_WINDOW'); END IF;
  SELECT least(requested+interval '15 minutes',(item->>'until')::timestamptz) INTO finish
   FROM jsonb_array_elements(au.schedule) item WHERE requested>=(item->>'from')::timestamptz AND requested<(item->>'until')::timestamptz LIMIT 1;
 END IF;
 IF finish IS NULL OR finish<=stamp OR finish<=requested OR requested>stamp+interval '24 hours' THEN RETURN jsonb_build_object('error','INVALID_WINDOW'); END IF;
 IF action='RESCHEDULE' THEN
  IF source_episode IS NULL OR NOT EXISTS(SELECT 1 FROM public.pickup_episode old JOIN public.pickup_token t ON t.episode_id=old.id
    WHERE old.id=source_episode AND old.student_id=s.id AND old.closed_at IS NULL AND t.authorization_id=aid) THEN
   RETURN jsonb_build_object('error','DENIED'); END IF;
  UPDATE public.pickup_token SET invalidated_at=coalesce(invalidated_at,stamp) WHERE episode_id=source_episode;
 END IF;
 UPDATE public.pickup_token SET invalidated_at=coalesce(invalidated_at,stamp) WHERE episode_id=ep.id;
 INSERT INTO public.pickup_token(id,episode_id,authorization_id,authorization_version,token_hash,issued_at,valid_from,expires_at)
  VALUES(tid,ep.id,aid,au.version,token_hash,stamp,requested,finish);
 IF NOT public.e3_versions(tid) THEN RAISE EXCEPTION 'pickup denied' USING ERRCODE='42501'; END IF;
 eid:=public.e1_append('QR_'||action,a.id,s.school_id,correlation,jsonb_build_object('episode_id',ep.id,'authorization_id',aid,
  'valid_from',requested,'expires_at',finish,'command_digest',hash));
 result:=jsonb_build_object('episode_id',ep.id,'valid_from',requested,'expires_at',finish,'issued',true,'event_sequence',(SELECT sequence FROM public.evidence_event WHERE id=eid));
 INSERT INTO public.pickup_command(id,actor_id,digest,result) VALUES(correlation,a.id,hash,result);
 RETURN result;
END $$;

CREATE OR REPLACE FUNCTION public.e3_resolve(token_hash text, origin_hash text, photo_only boolean DEFAULT false) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.identity_account; t public.pickup_token; s public.school_roster_student; au public.authorization_authorization;
 result jsonb; stamp timestamptz; ep public.pickup_episode;
BEGIN
 a:=public.e3_actor('GUARDIA');
 IF origin_hash IS NULL OR origin_hash !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'invalid pickup input' USING ERRCODE='22023'; END IF;
 IF NOT public.e3_limit('scan:'||a.id::text) OR NOT public.e3_limit('scan-origin:'||origin_hash||':'||a.id::text) THEN RETURN jsonb_build_object('error','RATE_LIMITED'); END IF;
 SELECT * INTO t FROM public.pickup_token tk WHERE tk.token_hash=e3_resolve.token_hash;
 SELECT st.* INTO s FROM public.school_roster_student st JOIN public.pickup_episode e ON e.student_id=st.id WHERE e.id=t.episode_id FOR UPDATE OF st;
 SELECT * INTO t FROM public.pickup_token WHERE id=t.id;
 SELECT * INTO ep FROM public.pickup_episode WHERE id=t.episode_id;
 PERFORM public.e3_actor('GUARDIA');
 stamp:=clock_timestamp();
 IF s.id IS NULL OR s.school_id<>a.school_id OR s.site_id<>a.site_id OR ep.closed_at IS NOT NULL OR t.consumed_at IS NOT NULL
   OR NOT public.e3_versions(t.id) OR NOT public.e3_clock_ok() OR stamp<t.valid_from OR stamp>=t.expires_at THEN
  PERFORM public.e1_append('QR_RESOLUTION_DENIED',a.id,a.school_id,gen_random_uuid(),jsonb_build_object('result','DENIED'));
  RETURN jsonb_build_object('error','DENIED'); END IF;
 SELECT * INTO au FROM public.authorization_authorization WHERE id=t.authorization_id;
 PERFORM public.e1_append('QR_SENSITIVE_READ',a.id,s.school_id,gen_random_uuid(),jsonb_build_object('episode_id',ep.id,'photo',photo_only));
 IF photo_only THEN RETURN (SELECT jsonb_build_object('photo',encode(photo,'base64')) FROM public.authorization_caregiver WHERE id=au.caregiver_id); END IF;
 result:=jsonb_build_object('episode_id',ep.id,'student_name',s.display_name,'valid_from',t.valid_from,'expires_at',t.expires_at,
  'server_now',clock_timestamp(),'caregiver',(SELECT jsonb_build_object('name',name,'document',document) FROM public.authorization_caregiver WHERE id=au.caregiver_id));
 RETURN result;
END $$;

CREATE OR REPLACE FUNCTION public.e3_confirm(correlation uuid, token_hash text, checks jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.identity_account; t public.pickup_token; s public.school_roster_student; ep public.pickup_episode;
 c public.pickup_command; eid uuid; deadline timestamptz; hash text; accepted boolean;
BEGIN
 a:=public.e3_actor('GUARDIA');
 hash:=encode(sha256(convert_to(jsonb_build_object('action','CONFIRM','token_hash',token_hash,'checks',checks)::text,'UTF8')),'hex');
 PERFORM pg_advisory_xact_lock(hashtextextended(correlation::text,30));
 PERFORM public.e3_actor('GUARDIA');
 SELECT * INTO c FROM public.pickup_command WHERE id=correlation;
 IF FOUND THEN
  IF c.actor_id<>a.id OR c.digest<>hash THEN RETURN jsonb_build_object('error','CONFLICT'); END IF;
  IF c.result ? 'error' THEN RETURN c.result; END IF;
  RETURN jsonb_build_object('operation_id',c.result->>'operation_id');
 END IF;
 IF checks IS NULL OR NOT(checks ?& ARRAY['student','caregiver','document']) OR (SELECT count(*) FROM jsonb_object_keys(checks))<>3
  OR EXISTS(SELECT 1 FROM jsonb_each(checks) x WHERE jsonb_typeof(x.value)<>'boolean') THEN
  RAISE EXCEPTION 'three explicit checks required' USING ERRCODE='22023'; END IF;
 SELECT * INTO t FROM public.pickup_token tk WHERE tk.token_hash=e3_confirm.token_hash;
 SELECT st.* INTO s FROM public.school_roster_student st JOIN public.pickup_episode e ON e.student_id=st.id WHERE e.id=t.episode_id FOR UPDATE OF st;
 SELECT * INTO ep FROM public.pickup_episode WHERE id=t.episode_id FOR UPDATE;
 SELECT * INTO t FROM public.pickup_token WHERE id=t.id FOR UPDATE;
 PERFORM public.e3_actor('GUARDIA');
 IF s.id IS NULL OR s.school_id<>a.school_id OR s.site_id<>a.site_id OR ep.closed_at IS NOT NULL OR t.consumed_at IS NOT NULL
   OR NOT public.e3_versions(t.id) OR NOT public.e3_clock_ok() OR clock_timestamp()<t.valid_from OR clock_timestamp()>=t.expires_at THEN
  PERFORM public.e1_append('PICKUP_CONFIRMATION_DENIED',a.id,a.school_id,correlation,jsonb_build_object('result','DENIED'));
  INSERT INTO public.pickup_command(id,actor_id,digest,result) VALUES(correlation,a.id,hash,jsonb_build_object('error','DENIED'));
  RETURN jsonb_build_object('error','DENIED'); END IF;
 accepted:=checks='{"student":true,"caregiver":true,"document":true}'::jsonb;
 UPDATE public.pickup_token SET consumed_at=clock_timestamp() WHERE id=t.id;
 UPDATE public.pickup_episode SET closed_at=clock_timestamp() WHERE id=ep.id;
 eid:=public.e1_append(CASE WHEN accepted THEN 'SALIDA_CONFIRMADA' ELSE 'RETIRO_RECHAZADO' END,a.id,s.school_id,correlation,
  jsonb_build_object('episode_id',ep.id,'authorization_id',t.authorization_id,'checks',checks,'operation_id',correlation));
 SELECT occurred_at+interval '5 seconds' INTO deadline FROM public.evidence_event WHERE id=eid;
 INSERT INTO public.pickup_operation(id,episode_id,token_id,guard_id,event_id,state,protection_deadline,incident_reason,report_result)
  VALUES(correlation,ep.id,t.id,a.id,eid,CASE WHEN accepted THEN 'PENDIENTE_ARCHIVO' ELSE 'INCIDENCIA' END,deadline,
   CASE WHEN accepted THEN '' ELSE 'PHYSICAL_MISMATCH' END,'');
 INSERT INTO public.pickup_command(id,actor_id,digest,result) VALUES(correlation,a.id,hash,jsonb_build_object('operation_id',correlation));
 RETURN jsonb_build_object('operation_id',correlation);
END $$;

CREATE OR REPLACE FUNCTION public.e3_get_operation(oid uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.identity_account; s public.school_roster_student;
BEGIN
 a:=public.e3_actor('GUARDIA');
 SELECT st.* INTO s FROM public.school_roster_student st JOIN public.pickup_episode ep ON ep.student_id=st.id
  JOIN public.pickup_operation o ON o.episode_id=ep.id WHERE o.id=oid AND o.guard_id=a.id AND st.site_id=a.site_id AND st.school_id=a.school_id FOR UPDATE OF st;
 PERFORM public.e3_actor('GUARDIA');
 IF s.id IS NULL THEN RETURN jsonb_build_object('error','DENIED'); END IF;
 PERFORM public.e3_advance(oid);
 RETURN public.e3_operation_json(oid);
END $$;

CREATE OR REPLACE FUNCTION public.e3_report(oid uuid, correlation uuid, delivered boolean, witnessed_at timestamptz, reason text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.identity_account; s public.school_roster_student; o public.pickup_operation; c public.pickup_command;
 hash text; eid uuid; late boolean; result jsonb;
BEGIN
 a:=public.e3_actor('GUARDIA');
 hash:=encode(sha256(convert_to(jsonb_build_object('action','REPORT','operation',oid,'delivered',delivered,'witnessed_at',witnessed_at,'reason',reason)::text,'UTF8')),'hex');
 PERFORM pg_advisory_xact_lock(hashtextextended(correlation::text,30));
 PERFORM public.e3_actor('GUARDIA');
 SELECT * INTO c FROM public.pickup_command WHERE id=correlation;
 IF FOUND THEN
  IF c.actor_id<>a.id OR c.digest<>hash THEN RETURN jsonb_build_object('error','CONFLICT'); END IF;
  RETURN c.result;
 END IF;
 SELECT st.* INTO s FROM public.school_roster_student st JOIN public.pickup_episode ep ON ep.student_id=st.id
  JOIN public.pickup_operation op ON op.episode_id=ep.id WHERE op.id=oid AND op.guard_id=a.id AND st.site_id=a.site_id AND st.school_id=a.school_id FOR UPDATE OF st;
 PERFORM public.e3_actor('GUARDIA');
 IF s.id IS NULL THEN RETURN jsonb_build_object('error','DENIED'); END IF;
 PERFORM public.e3_advance(oid);
 SELECT * INTO o FROM public.pickup_operation WHERE id=oid FOR UPDATE;
 IF o.report_event_id IS NOT NULL THEN RETURN jsonb_build_object('error','CONFLICT'); END IF;
 IF delivered IS NULL OR witnessed_at IS NULL OR NOT isfinite(witnessed_at) OR witnessed_at>clock_timestamp()+interval '1 second'
   OR witnessed_at<(SELECT occurred_at FROM public.evidence_event WHERE id=o.event_id)
   OR reason IS NULL OR length(btrim(reason)) NOT BETWEEN 1 AND 500 THEN RAISE EXCEPTION 'invalid report' USING ERRCODE='22023'; END IF;
 late:=o.state<>'HABILITADA' OR o.enabled_at IS NULL OR witnessed_at<o.enabled_at OR witnessed_at>=o.permission_expires_at;
 eid:=public.e1_append(CASE WHEN delivered THEN 'ENTREGA_FISICA_REPORTADA' ELSE 'NO_ENTREGA_REPORTADA' END,a.id,s.school_id,oid,
  jsonb_build_object('operation_id',oid,'related_event_id',o.event_id,'delivered',delivered,'witnessed_at',witnessed_at,
    'late_or_outside_permission',late,'reason',reason));
 UPDATE public.pickup_operation SET report_event_id=eid,report_result=CASE WHEN delivered THEN 'DELIVERED' ELSE 'NOT_DELIVERED' END,
   state=CASE WHEN late THEN 'INCIDENCIA' ELSE 'ENTREGA_REPORTADA' END,
   incident_reason=CASE WHEN late AND incident_reason='' THEN 'LATE_PHYSICAL_REPORT' ELSE incident_reason END WHERE id=oid;
 result:=jsonb_build_object('operation_id',oid,'report_event_id',eid,'event_sequence',(SELECT sequence FROM public.evidence_event WHERE id=eid));
 INSERT INTO public.pickup_command(id,actor_id,digest,result) VALUES(correlation,a.id,hash,result);
 RETURN result;
END $$;
