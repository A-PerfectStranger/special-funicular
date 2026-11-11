CREATE OR REPLACE FUNCTION public.e4_records(maximum integer, before_sequence bigint, student uuid, since date, until_date date, school uuid, parent uuid)
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
   'notification_states',(SELECT coalesce(jsonb_agg(jsonb_build_object('state',n.state,'count',n.total)),'[]'::jsonb) FROM (SELECT d.state,count(*) AS total FROM public.notification_worker_delivery d WHERE d.operation_id=o.id AND (parent IS NULL OR d.recipient_id=parent) GROUP BY d.state ORDER BY d.state) n),
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
