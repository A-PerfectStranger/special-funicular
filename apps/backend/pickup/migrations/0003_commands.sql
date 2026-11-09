-- E3 is additive. Runtime has only narrow commands, never table writes.
DO $$ DECLARE tab text;
BEGIN
 FOREACH tab IN ARRAY ARRAY['pickup_episode','pickup_token','pickup_operation','pickup_command','pickup_clock','pickup_limit'] LOOP
  EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',tab);
  EXECUTE format('CREATE POLICY command_writer ON public.%I TO retiro_evidence_writer USING(true) WITH CHECK(true)',tab);
  EXECUTE format('GRANT SELECT,INSERT,UPDATE ON public.%I TO retiro_evidence_writer',tab);
 END LOOP;
END $$;
INSERT INTO public.pickup_clock(id,observed_at,trusted_until) VALUES(1,clock_timestamp(),'-infinity');
ALTER TABLE public.pickup_token ADD CONSTRAINT pickup_interval CHECK(expires_at>valid_from AND expires_at<=valid_from+interval '15 minutes');
ALTER TABLE public.pickup_operation ADD CONSTRAINT pickup_state CHECK(state IN ('PENDIENTE_ARCHIVO','HABILITADA','INCIDENCIA','ENTREGA_REPORTADA'));

CREATE FUNCTION public.e3_actor(expected_role text) RETURNS public.identity_account
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.identity_account;
BEGIN
 SELECT ac.* INTO a FROM public.e1_current_account() ac
 JOIN public.identity_session s ON s.account_id=ac.id AND s.access_hash=current_setting('app.session_hash',true)
 WHERE ac.role=expected_role AND s.channel='mobile' AND s.access_expires_at>clock_timestamp()
   AND s.expires_at>clock_timestamp() AND s.last_seen_at>clock_timestamp()-
     CASE WHEN expected_role='GUARDIA' THEN interval '5 minutes' ELSE interval '15 minutes' END;
 IF a.id IS NULL THEN RAISE EXCEPTION 'pickup access denied' USING ERRCODE='42501'; END IF;
 -- Guard deactivation takes this account lock before touching active operations.
 IF expected_role='GUARDIA' THEN
  PERFORM 1 FROM public.identity_account WHERE id=a.id AND active AND version=a.version FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'pickup access denied' USING ERRCODE='42501'; END IF;
 END IF;
 RETURN a;
END $$;

CREATE FUNCTION public.e3_clock_ok() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM public.pickup_clock WHERE id=1 AND observed_at<=clock_timestamp()
   AND trusted_until>clock_timestamp() AND trusted_until<=observed_at+interval '10 seconds');
$$;

CREATE FUNCTION public.e3_limit(bucket text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE row public.pickup_limit; remaining numeric; stamp timestamptz;
BEGIN
 INSERT INTO public.pickup_limit(key,available,observed_at,denied) VALUES(bucket,10,clock_timestamp(),0) ON CONFLICT DO NOTHING;
 SELECT * INTO row FROM public.pickup_limit WHERE key=bucket FOR UPDATE;
 stamp:=clock_timestamp();
 remaining:=least(10,row.available+greatest(0,extract(epoch FROM stamp-row.observed_at))/2);
 UPDATE public.pickup_limit SET available=greatest(0,remaining-1),observed_at=stamp,denied=denied+CASE WHEN remaining<1 THEN 1 ELSE 0 END WHERE key=bucket;
 RETURN remaining>=1;
END $$;

CREATE FUNCTION public.e3_versions(tid uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM public.pickup_token t JOIN public.pickup_episode ep ON ep.id=t.episode_id
 JOIN public.authorization_authorization au ON au.id=t.authorization_id AND au.revoked_at IS NULL AND au.version=t.authorization_version
 JOIN public.authorization_caregiver c ON c.id=au.caregiver_id AND c.active AND c.version=au.caregiver_version
 JOIN public.authorization_policy p ON p.student_id=ep.student_id AND NOT p.blocked AND p.version=au.policy_version
 JOIN public.school_roster_student s ON s.id=ep.student_id AND s.active
 JOIN public.school_roster_school sch ON sch.id=s.school_id AND sch.active
 JOIN public.school_roster_link l ON l.student_id=s.id AND l.active AND l.principal AND l.version=au.link_version
 JOIN public.school_roster_parent pa ON pa.id=l.parent_id AND pa.account_id=au.created_by_id
 JOIN public.identity_account a ON a.id=pa.account_id AND a.active
 WHERE t.id=tid AND t.invalidated_at IS NULL);
$$;

CREATE FUNCTION public.e3_incident(oid uuid, why text, causal uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE o public.pickup_operation; school uuid;
BEGIN
 SELECT * INTO o FROM public.pickup_operation WHERE id=oid FOR UPDATE;
 IF o.state NOT IN ('PENDIENTE_ARCHIVO','HABILITADA') THEN RETURN; END IF;
 UPDATE public.pickup_operation SET state='INCIDENCIA',incident_reason=why WHERE id=oid;
 SELECT s.school_id INTO school FROM public.school_roster_student s JOIN public.pickup_episode ep ON ep.student_id=s.id WHERE ep.id=o.episode_id;
 PERFORM public.e1_append(CASE WHEN why='EVIDENCE_TIMEOUT' THEN 'ENTREGA_NO_HABILITADA_POR_EVIDENCIA' ELSE 'PICKUP_INCIDENCE' END,
  causal,school,oid,jsonb_build_object('operation_id',oid,'reason',why,'related_event_id',o.event_id,'credential',session_user));
END $$;

CREATE FUNCTION public.e3_advance(oid uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE o public.pickup_operation; receipt public.evidence_receipt; stamp timestamptz;
BEGIN
 -- Caller holds the student lock; operational state is never a network transaction.
 SELECT * INTO o FROM public.pickup_operation WHERE id=oid FOR UPDATE;
 IF o.id IS NULL OR o.state NOT IN ('PENDIENTE_ARCHIVO','HABILITADA') THEN RETURN; END IF;
 stamp:=clock_timestamp();
 IF o.state='PENDIENTE_ARCHIVO' AND stamp>=o.protection_deadline THEN
  PERFORM public.e3_incident(oid,'EVIDENCE_TIMEOUT',o.guard_id); RETURN;
 ELSIF o.state='HABILITADA' AND o.permission_expires_at<=stamp THEN
  PERFORM public.e3_incident(oid,'PERMISSION_EXPIRED',o.guard_id); RETURN;
 END IF;
 IF NOT public.e3_versions(o.token_id) OR NOT EXISTS(SELECT 1 FROM public.identity_account WHERE id=o.guard_id AND active)
   OR NOT public.e3_clock_ok() THEN
  PERFORM public.e3_incident(oid,'VALIDATION_UNAVAILABLE',o.guard_id); RETURN;
 END IF;
 IF o.state='PENDIENTE_ARCHIVO' THEN
  SELECT r.* INTO receipt FROM public.evidence_receipt r JOIN public.evidence_event e ON e.id=r.event_id AND e.digest=r.digest
   WHERE r.event_id=o.event_id AND r.version_id<>'' AND r.manifest_version<>'' AND r.retained_until>stamp;
  IF receipt.event_id IS NOT NULL AND receipt.verified_at<=o.protection_deadline AND stamp<o.protection_deadline THEN
   UPDATE public.pickup_operation SET state='HABILITADA',enabled_at=stamp,permission_expires_at=stamp+interval '30 seconds' WHERE id=oid;
  ELSIF stamp>=o.protection_deadline THEN
   PERFORM public.e3_incident(oid,'EVIDENCE_TIMEOUT',o.guard_id);
  END IF;
 ELSIF o.permission_expires_at<=stamp THEN
  PERFORM public.e3_incident(oid,'PERMISSION_EXPIRED',o.guard_id);
 END IF;
END $$;

CREATE FUNCTION public.e3_operation_json(oid uuid) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
 SELECT jsonb_build_object('operation_id',o.id,'state',o.state,'server_now',clock_timestamp(),
  'protection_deadline',o.protection_deadline,'permission_expires_at',o.permission_expires_at,
  'may_handover',o.state='HABILITADA' AND o.permission_expires_at>clock_timestamp() AND public.e3_clock_ok(),
  'incident_reason',o.incident_reason,'report_result',o.report_result,
  'report_protected',EXISTS(SELECT 1 FROM public.evidence_receipt r WHERE r.event_id=o.report_event_id),
  'event_sequence',e.sequence)
 FROM public.pickup_operation o JOIN public.evidence_event e ON e.id=o.event_id WHERE o.id=oid;
$$;

CREATE FUNCTION public.e3_issue(action text, correlation uuid, aid uuid, requested timestamptz, token_hash text,
 source_episode uuid, origin_hash text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.identity_account; au public.authorization_authorization; s public.school_roster_student;
 l public.school_roster_link; ep public.pickup_episode; previous public.pickup_token; c public.pickup_command;
 zone text; finish timestamptz; day date; stamp timestamptz; eid uuid; result jsonb; tid uuid:=gen_random_uuid();
 hash text:=encode(sha256(convert_to(jsonb_build_object('action',action,'authorization',aid,'requested',requested,'source',source_episode)::text,'UTF8')),'hex');
BEGIN
 a:=public.e3_actor('PADRE');
 PERFORM pg_advisory_xact_lock(hashtextextended(correlation::text,30));
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

CREATE FUNCTION public.e3_resolve(token_hash text, origin_hash text, photo_only boolean DEFAULT false) RETURNS jsonb
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

CREATE FUNCTION public.e3_confirm(correlation uuid, token_hash text, checks jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.identity_account; t public.pickup_token; s public.school_roster_student; ep public.pickup_episode;
 c public.pickup_command; eid uuid; deadline timestamptz; hash text; accepted boolean;
BEGIN
 a:=public.e3_actor('GUARDIA');
 hash:=encode(sha256(convert_to(jsonb_build_object('action','CONFIRM','token_hash',token_hash,'checks',checks)::text,'UTF8')),'hex');
 PERFORM pg_advisory_xact_lock(hashtextextended(correlation::text,30));
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

CREATE FUNCTION public.e3_get_operation(oid uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.identity_account; s public.school_roster_student;
BEGIN
 a:=public.e3_actor('GUARDIA');
 SELECT st.* INTO s FROM public.school_roster_student st JOIN public.pickup_episode ep ON ep.student_id=st.id
  JOIN public.pickup_operation o ON o.episode_id=ep.id WHERE o.id=oid AND o.guard_id=a.id AND st.site_id=a.site_id AND st.school_id=a.school_id FOR UPDATE OF st;
 IF s.id IS NULL THEN RETURN jsonb_build_object('error','DENIED'); END IF;
 PERFORM public.e3_advance(oid);
 RETURN public.e3_operation_json(oid);
END $$;

CREATE FUNCTION public.e3_report(oid uuid, correlation uuid, delivered boolean, witnessed_at timestamptz, reason text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.identity_account; s public.school_roster_student; o public.pickup_operation; c public.pickup_command;
 hash text; eid uuid; late boolean; result jsonb;
BEGIN
 a:=public.e3_actor('GUARDIA');
 hash:=encode(sha256(convert_to(jsonb_build_object('action','REPORT','operation',oid,'delivered',delivered,'witnessed_at',witnessed_at,'reason',reason)::text,'UTF8')),'hex');
 PERFORM pg_advisory_xact_lock(hashtextextended(correlation::text,30));
 SELECT * INTO c FROM public.pickup_command WHERE id=correlation;
 IF FOUND THEN
  IF c.actor_id<>a.id OR c.digest<>hash THEN RETURN jsonb_build_object('error','CONFLICT'); END IF;
  RETURN c.result;
 END IF;
 SELECT st.* INTO s FROM public.school_roster_student st JOIN public.pickup_episode ep ON ep.student_id=st.id
  JOIN public.pickup_operation op ON op.episode_id=ep.id WHERE op.id=oid AND op.guard_id=a.id AND st.site_id=a.site_id AND st.school_id=a.school_id FOR UPDATE OF st;
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

-- Deadlines and expiry progress without a connected guard. Archiver has no free writes.
CREATE FUNCTION public.e3_sweep() RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE child record; op record;
BEGIN
 FOR child IN SELECT DISTINCT ep.student_id FROM public.pickup_episode ep JOIN public.pickup_operation o ON o.episode_id=ep.id
  WHERE o.state IN ('PENDIENTE_ARCHIVO','HABILITADA') ORDER BY ep.student_id LIMIT 100 LOOP
  PERFORM 1 FROM public.school_roster_student WHERE id=child.student_id FOR UPDATE;
  FOR op IN SELECT o.id FROM public.pickup_operation o JOIN public.pickup_episode ep ON ep.id=o.episode_id
    WHERE ep.student_id=child.student_id AND o.state IN ('PENDIENTE_ARCHIVO','HABILITADA') LOOP
   PERFORM public.e3_advance(op.id);
  END LOOP;
 END LOOP;
 RETURN (SELECT jsonb_build_object('pending_archive',count(*) FILTER(WHERE state='PENDIENTE_ARCHIVO'),
  'clock_trusted',public.e3_clock_ok(),'rate_limited',coalesce((SELECT sum(denied) FROM public.pickup_limit),0),'enabled',count(*) FILTER(WHERE state='HABILITADA'),'incidents',count(*) FILTER(WHERE state='INCIDENCIA'),
  'unprotected_reports',count(*) FILTER(WHERE report_event_id IS NOT NULL AND NOT EXISTS
   (SELECT 1 FROM public.evidence_receipt r WHERE r.event_id=report_event_id))) FROM public.pickup_operation);
END $$;

CREATE FUNCTION public.e3_clock_sample(external_at timestamptz, elapsed_ms integer) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE stamp timestamptz:=clock_timestamp(); acceptable boolean;
BEGIN
 acceptable:=external_at IS NOT NULL AND isfinite(external_at) AND elapsed_ms BETWEEN 0 AND 2000 AND abs(extract(epoch FROM stamp-external_at))<=2;
 UPDATE public.pickup_clock SET observed_at=stamp,external_at=e3_clock_sample.external_at,
  trusted_until=CASE WHEN acceptable THEN stamp+interval '10 seconds' ELSE stamp END WHERE id=1;
 RETURN acceptable;
END $$;

CREATE FUNCTION public.e3_receipt_transition() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE oid uuid; student uuid;
BEGIN
 SELECT o.id,ep.student_id INTO oid,student FROM public.pickup_operation o JOIN public.pickup_episode ep ON ep.id=o.episode_id WHERE o.event_id=NEW.event_id;
 IF oid IS NOT NULL THEN
  PERFORM 1 FROM public.school_roster_student WHERE id=student FOR UPDATE;
  PERFORM public.e3_advance(oid);
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER pickup_receipt AFTER INSERT ON public.evidence_receipt FOR EACH ROW EXECUTE FUNCTION public.e3_receipt_transition();

CREATE FUNCTION public.e3_authorization_changed() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE op record;
BEGIN
 IF NEW.version<>OLD.version OR NEW.revoked_at IS DISTINCT FROM OLD.revoked_at THEN
  FOR op IN SELECT o.id FROM public.pickup_operation o JOIN public.pickup_token t ON t.id=o.token_id
   WHERE t.authorization_id=NEW.id AND o.state IN ('PENDIENTE_ARCHIVO','HABILITADA') ORDER BY o.id LOOP
   PERFORM public.e3_incident(op.id,'AUTHORIZATION_CHANGED',(SELECT id FROM public.e1_current_account()));
  END LOOP;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER pickup_revocation AFTER UPDATE ON public.authorization_authorization FOR EACH ROW EXECUTE FUNCTION public.e3_authorization_changed();

CREATE FUNCTION public.e3_guard_changed() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE op record;
BEGIN
 IF OLD.role='GUARDIA' AND (NOT NEW.active OR NEW.version<>OLD.version OR NEW.site_id IS DISTINCT FROM OLD.site_id) THEN
  FOR op IN SELECT o.id,ep.student_id FROM public.pickup_operation o JOIN public.pickup_episode ep ON ep.id=o.episode_id
   WHERE o.guard_id=NEW.id AND o.state IN ('PENDIENTE_ARCHIVO','HABILITADA') ORDER BY ep.student_id,o.id LOOP
   PERFORM 1 FROM public.school_roster_student WHERE id=op.student_id FOR UPDATE;
   PERFORM public.e3_incident(op.id,'GUARD_REVOKED',NEW.id);
  END LOOP;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER pickup_guard_revocation AFTER UPDATE ON public.identity_account FOR EACH ROW EXECUTE FUNCTION public.e3_guard_changed();

DO $$ DECLARE fn record;
BEGIN
 FOR fn IN SELECT p.oid::regprocedure signature FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname LIKE 'e3_%' LOOP
  EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',fn.signature);
  EXECUTE format('ALTER FUNCTION %s OWNER TO retiro_evidence_writer',fn.signature);
 END LOOP;
END $$;
GRANT EXECUTE ON FUNCTION public.e3_issue(text,uuid,uuid,timestamptz,text,uuid,text),public.e3_resolve(text,text,boolean),
 public.e3_confirm(uuid,text,jsonb),public.e3_get_operation(uuid),public.e3_report(uuid,uuid,boolean,timestamptz,text) TO retiro_runtime;
GRANT EXECUTE ON FUNCTION public.e3_clock_sample(timestamptz,integer),public.e3_sweep() TO retiro_archiver;
