ALTER TABLE public.pickup_trialhold ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pickup_trialhold FORCE ROW LEVEL SECURITY;
CREATE POLICY command_writer ON public.pickup_trialhold TO retiro_evidence_writer USING(true) WITH CHECK(true);
GRANT SELECT,INSERT ON public.pickup_trialhold TO retiro_evidence_writer;

-- No production endpoint or general-purpose archive switch. This bounded fault is
-- usable once, only for a student in an explicitly approved E3 synthetic batch.
CREATE FUNCTION public.e3_trial_hold(student uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE school uuid;
BEGIN
 IF session_user<>'retiro_importer' OR NOT EXISTS(SELECT 1 FROM public.school_roster_importbatch b,
  LATERAL jsonb_array_elements(b.payload::jsonb->'students') item WHERE b.operator='E3_SYNTHETIC_OPERATOR'
  AND b.approval='E3_SYNTHETIC_APPROVAL' AND b.promoted_at IS NOT NULL AND (item->>'id')::uuid=student) THEN
  RAISE EXCEPTION 'synthetic fixture required' USING ERRCODE='42501'; END IF;
 SELECT school_id INTO school FROM public.school_roster_student WHERE id=student FOR UPDATE;
 IF EXISTS(SELECT 1 FROM public.pickup_operation o JOIN public.pickup_episode ep ON ep.id=o.episode_id WHERE ep.student_id=student) THEN
  RAISE EXCEPTION 'unused synthetic episode required' USING ERRCODE='22023'; END IF;
 INSERT INTO public.pickup_trialhold(student_id,until) VALUES(student,clock_timestamp()+interval '5 minutes');
 PERFORM public.e1_append('SYNTHETIC_ARCHIVE_DELAY',NULL,school,student,
  jsonb_build_object('student_id',student,'duration_seconds',15,'credential',session_user));
END $$;
REVOKE ALL ON FUNCTION public.e3_trial_hold(uuid) FROM PUBLIC;
ALTER FUNCTION public.e3_trial_hold(uuid) OWNER TO retiro_evidence_writer;
GRANT EXECUTE ON FUNCTION public.e3_trial_hold(uuid) TO retiro_importer;

-- Time-critical decisions precede ordinary audit backlog. Every other event keeps
-- FIFO processing. No SQL lock spans the remote archive call.
CREATE OR REPLACE FUNCTION public.e1_claim_archive(batch integer, lease uuid)
RETURNS TABLE(event_id uuid, sequence bigint, canonical bytea, digest text, occurred_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 RETURN QUERY WITH chosen AS (
  SELECT j.event_id FROM public.evidence_archivejob j JOIN public.evidence_event e ON e.id=j.event_id
  WHERE j.completed_at IS NULL AND j.available_at<=clock_timestamp()
    AND (j.lease_until IS NULL OR j.lease_until<clock_timestamp())
    AND NOT (e.kind='SALIDA_CONFIRMADA' AND EXISTS(SELECT 1 FROM public.pickup_operation o
      JOIN public.pickup_episode ep ON ep.id=o.episode_id JOIN public.pickup_trialhold h ON h.student_id=ep.student_id
      WHERE o.event_id=e.id AND h.until>e.occurred_at AND e.occurred_at+interval '15 seconds'>clock_timestamp()))
  ORDER BY CASE WHEN (e.kind='SALIDA_CONFIRMADA' AND EXISTS(SELECT 1 FROM public.pickup_operation urgent WHERE urgent.event_id=e.id AND urgent.state='PENDIENTE_ARCHIVO' AND urgent.protection_deadline>clock_timestamp())) OR (e.kind='SCHOOL_LOGIN' AND EXISTS(SELECT 1 FROM public.identity_session login WHERE login.access_event_id=e.id AND login.enabled_at IS NULL AND login.revoked_at IS NULL AND login.protection_deadline>clock_timestamp())) THEN 0 WHEN e.kind IN ('ENTREGA_FISICA_REPORTADA','NO_ENTREGA_REPORTADA') THEN 1 ELSE 2 END,
    j.available_at,j.event_id LIMIT least(greatest(batch,1),100) FOR UPDATE OF j SKIP LOCKED
 ), claimed AS (
  UPDATE public.evidence_archivejob j SET lease_id=lease,lease_until=clock_timestamp()+interval '30 seconds',attempts=attempts+1
    FROM chosen c WHERE j.event_id=c.event_id RETURNING j.event_id
 ) SELECT e.id,e.sequence,e.canonical,e.digest::text,e.occurred_at FROM claimed c JOIN public.evidence_event e ON e.id=c.event_id ORDER BY e.sequence;
END $$;
