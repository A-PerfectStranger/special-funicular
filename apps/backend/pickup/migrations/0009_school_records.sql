-- RF03/13/18; CA-F03/13/18, CA-S02/11/12/14/21/22/23.
ALTER TABLE public.pickup_correction ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pickup_correction FORCE ROW LEVEL SECURITY;
CREATE POLICY correction_writer ON public.pickup_correction TO retiro_evidence_writer USING(true) WITH CHECK(true);
GRANT SELECT,INSERT ON public.pickup_correction TO retiro_evidence_writer;
ALTER TABLE public.pickup_correction ADD CONSTRAINT correction_outcome CHECK(outcome IN ('DELIVERED','NOT_DELIVERED','UNRESOLVED'));

CREATE FUNCTION public.e4_correct(oid uuid, correlation uuid, operator text, approval text, reason text, outcome text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE o public.pickup_operation; c public.pickup_correction; school uuid; related uuid; eid uuid; hash text;
BEGIN
 IF operator IS NULL OR length(btrim(operator)) NOT BETWEEN 1 AND 160
   OR approval IS NULL OR length(btrim(approval)) NOT BETWEEN 1 AND 160
   OR reason IS NULL OR length(btrim(reason)) NOT BETWEEN 1 AND 500
   OR outcome IS NULL OR outcome NOT IN ('DELIVERED','NOT_DELIVERED','UNRESOLVED') THEN
  RAISE EXCEPTION 'invalid correction' USING ERRCODE='22023';
 END IF;
 hash:=encode(sha256(convert_to(jsonb_build_object('operation',oid,'operator',operator,'approval',approval,'reason',reason,'outcome',outcome)::text,'UTF8')),'hex');
 PERFORM pg_advisory_xact_lock(hashtextextended(correlation::text,40));
 SELECT * INTO c FROM public.pickup_correction WHERE id=correlation;
 IF FOUND THEN
  IF c.digest<>hash THEN RAISE EXCEPTION 'correction conflict' USING ERRCODE='23505'; END IF;
  RETURN jsonb_build_object('event_id',c.event_id,'operation_id',c.operation_id,'protected',EXISTS(SELECT 1 FROM public.evidence_receipt WHERE event_id=c.event_id));
 END IF;
 SELECT * INTO o FROM public.pickup_operation WHERE id=oid FOR UPDATE;
 IF o.id IS NULL OR (o.report_event_id IS NULL AND o.state<>'INCIDENCIA') THEN
  RAISE EXCEPTION 'correction requires historical fact or incident' USING ERRCODE='22023';
 END IF;
 SELECT s.school_id INTO school FROM public.school_roster_student s JOIN public.pickup_episode ep ON ep.student_id=s.id WHERE ep.id=o.episode_id;
 SELECT event_id INTO related FROM public.pickup_correction pc JOIN public.evidence_event e ON e.id=pc.event_id
   WHERE pc.operation_id=oid ORDER BY e.sequence DESC LIMIT 1;
 related:=coalesce(related,o.report_event_id,o.event_id);
 eid:=public.e1_append('PICKUP_CORRECTION',NULL,school,correlation,jsonb_build_object('operation_id',oid,
   'related_event_id',related,'original_event_id',coalesce(o.report_event_id,o.event_id),'operator',operator,
   'approval',approval,'reason',reason,'outcome',outcome,'credential',session_user));
 INSERT INTO public.pickup_correction(id,operation_id,event_id,related_event_id,digest,outcome)
   VALUES(correlation,oid,eid,related,hash,outcome);
 RETURN jsonb_build_object('event_id',eid,'operation_id',oid,'protected',false);
END $$;

-- Private projection helper; callers enforce distinct actor and SQL identities.
CREATE FUNCTION public.e4_records(maximum integer, before_sequence bigint, student uuid, since date, until_date date, school uuid, parent uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE result jsonb;
BEGIN
 IF maximum IS NULL OR maximum NOT BETWEEN 1 AND 100 OR (before_sequence IS NOT NULL AND before_sequence<1)
  OR (since IS NOT NULL AND until_date IS NOT NULL AND since>until_date) THEN
  RAISE EXCEPTION 'invalid pagination' USING ERRCODE='22023';
 END IF;
 SELECT coalesce(jsonb_agg(row.data ORDER BY row.sequence DESC),'[]'::jsonb) INTO result FROM (
 SELECT e.sequence,jsonb_build_object('sequence',e.sequence,'operation_id',o.id,'student_id',s.id,
   'student_name',s.display_name,'local_date',ep.local_date,'timezone',site.timezone,
   'decision_at',e.occurred_at,'state',o.state,'incident_reason',o.incident_reason,
   'report_result',o.report_result,'report_at',re.occurred_at,
   'report_protected',EXISTS(SELECT 1 FROM public.evidence_receipt r WHERE r.event_id=o.report_event_id),
   'correction_count',(SELECT count(*) FROM public.pickup_correction c WHERE c.operation_id=o.id),
   'corrections',coalesce((SELECT jsonb_agg(jsonb_build_object('event_id',ce.id,'related_event_id',c.related_event_id,
     'occurred_at',ce.occurred_at,'outcome',c.outcome,'protected',EXISTS(SELECT 1 FROM public.evidence_receipt r WHERE r.event_id=ce.id)) ORDER BY ce.sequence)
     FROM (SELECT pc.* FROM public.pickup_correction pc JOIN public.evidence_event ec ON ec.id=pc.event_id WHERE pc.operation_id=o.id ORDER BY ec.sequence DESC LIMIT 25) c JOIN public.evidence_event ce ON ce.id=c.event_id),'[]'::jsonb)) AS data
 FROM public.pickup_operation o JOIN public.pickup_episode ep ON ep.id=o.episode_id
 JOIN public.school_roster_student s ON s.id=ep.student_id
 JOIN public.school_roster_site site ON site.id=s.site_id
 JOIN public.evidence_event e ON e.id=o.event_id
 LEFT JOIN public.evidence_event re ON re.id=o.report_event_id
 WHERE (school IS NULL OR s.school_id=school)
  AND (parent IS NULL OR EXISTS(SELECT 1 FROM public.school_roster_link l JOIN public.school_roster_parent p ON p.id=l.parent_id
       JOIN public.school_roster_school sch ON sch.id=l.school_id AND sch.active
       WHERE p.account_id=parent AND l.student_id=s.id AND l.active))
  AND (student IS NULL OR s.id=student) AND (before_sequence IS NULL OR e.sequence<before_sequence)
  AND (since IS NULL OR ep.local_date>=since) AND (until_date IS NULL OR ep.local_date<=until_date)
 ORDER BY e.sequence DESC LIMIT maximum
 ) row;
 RETURN jsonb_build_object('records',result,'next_cursor',CASE WHEN jsonb_array_length(result)=maximum THEN result->-1->'sequence' ELSE NULL END);
END $$;

CREATE FUNCTION public.e4_school_records(maximum integer, before_sequence bigint, student uuid, since date, until_date date)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.identity_account;
BEGIN
 SELECT ac.* INTO a FROM public.e1_current_account() ac JOIN public.identity_session se ON se.account_id=ac.id
  AND se.access_hash=current_setting('app.session_hash',true) AND se.channel='web' WHERE ac.role='ADMIN_ESCUELA';
 IF a.id IS NULL OR a.school_id IS NULL THEN RAISE EXCEPTION 'school access denied' USING ERRCODE='42501'; END IF;
 PERFORM public.e1_append('SCHOOL_PICKUP_READ',a.id,a.school_id,gen_random_uuid(),jsonb_build_object('student_filter',student,'since',since,'until',until_date,'limit',maximum));
 RETURN public.e4_records(maximum,before_sequence,student,since,until_date,a.school_id,NULL);
END $$;

CREATE FUNCTION public.e4_parent_records(maximum integer, before_sequence bigint, student uuid, since date, until_date date)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.identity_account;
BEGIN
 a:=public.e3_actor('PADRE');
 PERFORM public.e1_append('FAMILY_PICKUP_READ',a.id,NULL,gen_random_uuid(),jsonb_build_object('student_filter',student,'since',since,'until',until_date,'limit',maximum));
 RETURN public.e4_records(maximum,before_sequence,student,since,until_date,NULL,a.id);
END $$;

DO $$ DECLARE fn record;
BEGIN
 FOR fn IN SELECT oid::regprocedure AS signature FROM pg_proc WHERE pronamespace='public'::regnamespace AND proname LIKE 'e4_%' LOOP
  EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',fn.signature);
  EXECUTE format('ALTER FUNCTION %s OWNER TO retiro_evidence_writer',fn.signature);
 END LOOP;
END $$;
GRANT EXECUTE ON FUNCTION public.e4_correct(uuid,uuid,text,text,text,text) TO retiro_importer;
GRANT EXECUTE ON FUNCTION public.e4_parent_records(integer,bigint,uuid,date,date) TO retiro_runtime;
GRANT EXECUTE ON FUNCTION public.e4_school_records(integer,bigint,uuid,date,date) TO retiro_school_read;
