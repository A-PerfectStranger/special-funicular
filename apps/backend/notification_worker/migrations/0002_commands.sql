-- RF11/12, RFS18; separate notificador and no public table access.
DO $$ DECLARE tab text;
BEGIN
 FOREACH tab IN ARRAY ARRAY['notification_worker_endpoint','notification_worker_delivery','notification_worker_attempt'] LOOP
  EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',tab);
  EXECUTE format('CREATE POLICY notification_writer ON public.%I TO retiro_evidence_writer USING(true) WITH CHECK(true)',tab);
  EXECUTE format('GRANT SELECT,INSERT,UPDATE ON public.%I TO retiro_evidence_writer',tab);
 END LOOP;
END $$;
ALTER TABLE public.notification_worker_delivery ADD CONSTRAINT notification_state CHECK(state IN ('PENDING','PENDING_DEVICE','PENDING_REVIEW','PROVIDER_ACCEPTED','PROVIDER_RECEIPT','SUPPRESSED'));
ALTER TABLE public.notification_worker_attempt ADD CONSTRAINT notification_attempt_state CHECK(state IN ('SENDING','UNKNOWN','FAILED','PROVIDER_ACCEPTED','PROVIDER_RECEIPT','RECEIPT_ERROR'));
CREATE INDEX notification_due ON public.notification_worker_delivery(available_at) WHERE state IN ('PENDING','PENDING_DEVICE');
CREATE INDEX notification_receipt_due ON public.notification_worker_attempt(receipt_available_at) WHERE state='PROVIDER_ACCEPTED';

CREATE FUNCTION public.e4_endpoint(token text, enabled boolean) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.identity_account; eid uuid;
BEGIN
 a:=public.e3_actor('PADRE');
 IF token IS NULL OR length(token)>255 OR token!~'^(ExponentPushToken|ExpoPushToken)\[[A-Za-z0-9_-]{10,200}\]$' OR enabled IS NULL THEN
  RAISE EXCEPTION 'invalid endpoint' USING ERRCODE='22023';
 END IF;
 IF NOT public.e3_limit('notification-endpoint:'||a.id::text) THEN RETURN jsonb_build_object('error','RATE_LIMITED'); END IF;
 IF enabled THEN
  INSERT INTO public.notification_worker_endpoint(id,account_id,token,active,updated_at)
   VALUES(gen_random_uuid(),a.id,token,true,clock_timestamp())
   ON CONFLICT ON CONSTRAINT notification_worker_endpoint_token_key DO UPDATE SET account_id=a.id,active=true,updated_at=clock_timestamp()
   RETURNING id INTO eid;
 ELSE
  UPDATE public.notification_worker_endpoint SET active=false,updated_at=clock_timestamp() WHERE account_id=a.id AND notification_worker_endpoint.token=e4_endpoint.token RETURNING id INTO eid;
 END IF;
 PERFORM public.e1_append('NOTIFICATION_ENDPOINT_CHANGED',a.id,NULL,gen_random_uuid(),jsonb_build_object('enabled',enabled));
 RETURN jsonb_build_object('registered',enabled);
END $$;

CREATE FUNCTION public.e4_enqueue_notification() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 IF NEW.report_result='DELIVERED' AND NEW.report_event_id IS NOT NULL AND OLD.report_event_id IS NULL THEN
  INSERT INTO public.notification_worker_delivery(id,event_id,operation_id,recipient_id,state,created_at,available_at,attempts,last_error)
  SELECT gen_random_uuid(),NEW.report_event_id,NEW.id,a.id,'PENDING',clock_timestamp(),clock_timestamp(),0,''
   FROM public.pickup_episode ep JOIN public.school_roster_link l ON l.student_id=ep.student_id AND l.active
   JOIN public.school_roster_parent p ON p.id=l.parent_id JOIN public.identity_account a ON a.id=p.account_id AND a.active AND a.role='PADRE'
   WHERE ep.id=NEW.episode_id ON CONFLICT(event_id,recipient_id) DO NOTHING;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER notification_report AFTER UPDATE OF report_event_id ON public.pickup_operation FOR EACH ROW EXECUTE FUNCTION public.e4_enqueue_notification();

CREATE FUNCTION public.e4_recipient_enabled(did uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM public.notification_worker_delivery d
  JOIN public.identity_account a ON a.id=d.recipient_id AND a.active AND a.role='PADRE'
  JOIN public.school_roster_parent p ON p.account_id=a.id
  JOIN public.pickup_operation o ON o.id=d.operation_id AND o.report_event_id=d.event_id AND o.report_result='DELIVERED'
  JOIN public.pickup_episode ep ON ep.id=o.episode_id
  JOIN public.school_roster_link l ON l.parent_id=p.id AND l.student_id=ep.student_id AND l.active
  JOIN public.school_roster_school sch ON sch.id=l.school_id AND sch.active WHERE d.id=did);
$$;

CREATE FUNCTION public.e4_claim_notifications(maximum integer, lease uuid)
RETURNS TABLE(attempt_id uuid, notification_id uuid, token text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE d public.notification_worker_delivery; ep public.notification_worker_endpoint; aid uuid; delay interval;
BEGIN
 IF maximum IS NULL OR maximum NOT BETWEEN 1 AND 100 OR lease IS NULL THEN RAISE EXCEPTION 'invalid lease' USING ERRCODE='22023'; END IF;
 FOR d IN SELECT nd.* FROM public.notification_worker_delivery nd JOIN public.evidence_receipt r ON r.event_id=nd.event_id
  JOIN public.evidence_event e ON e.id=r.event_id AND e.digest=r.digest
  WHERE nd.state IN ('PENDING','PENDING_DEVICE') AND nd.available_at<=clock_timestamp()
   AND (nd.lease_until IS NULL OR nd.lease_until<=clock_timestamp())
   AND r.retained_until>clock_timestamp() AND r.version_id<>'' AND r.manifest_version<>''
  ORDER BY nd.available_at,nd.id LIMIT maximum FOR UPDATE OF nd SKIP LOCKED LOOP
  IF NOT public.e4_recipient_enabled(d.id) THEN
   UPDATE public.notification_worker_delivery SET state='SUPPRESSED',lease_id=NULL,lease_until=NULL,last_error='RECIPIENT_DISABLED' WHERE id=d.id;
   PERFORM public.e1_append('NOTIFICATION_SUPPRESSED',NULL,e.school_id, d.id,jsonb_build_object('notification_id',d.id,'reason','RECIPIENT_DISABLED')) FROM public.evidence_event e WHERE e.id=d.event_id;
   CONTINUE;
  END IF;
  IF d.attempts>=5 THEN
   UPDATE public.notification_worker_delivery SET state='PENDING_REVIEW',escalated_at=coalesce(escalated_at,clock_timestamp()),lease_id=NULL,lease_until=NULL,last_error='RETRIES_EXHAUSTED' WHERE id=d.id;
   PERFORM public.e1_append('NOTIFICATION_EXHAUSTED',NULL,e.school_id,d.id,jsonb_build_object('notification_id',d.id)) FROM public.evidence_event e WHERE e.id=d.event_id;
   CONTINUE;
  END IF;
  SELECT * INTO ep FROM public.notification_worker_endpoint ne WHERE ne.account_id=d.recipient_id AND ne.active ORDER BY ne.updated_at DESC,ne.id LIMIT 1;
  IF ep.id IS NULL THEN
   UPDATE public.notification_worker_delivery SET state='PENDING_DEVICE',available_at=clock_timestamp()+interval '30 seconds',lease_id=NULL,lease_until=NULL,last_error='NO_DEVICE',
    escalated_at=CASE WHEN created_at<clock_timestamp()-interval '15 minutes' THEN coalesce(escalated_at,clock_timestamp()) ELSE escalated_at END WHERE id=d.id;
   CONTINUE;
  END IF;
  UPDATE public.notification_worker_attempt SET state='UNKNOWN',error='WORKER_INTERRUPTED' WHERE delivery_id=d.id AND state='SENDING';
  aid:=gen_random_uuid();
  INSERT INTO public.notification_worker_attempt(id,delivery_id,endpoint_id,created_at,state,error)
   VALUES(aid,d.id,ep.id,clock_timestamp(),'SENDING','');
  delay:=(ARRAY[interval '30 seconds',interval '2 minutes',interval '5 minutes',interval '15 minutes',interval '15 minutes'])[d.attempts+1];
  UPDATE public.notification_worker_delivery SET state='PENDING',attempts=attempts+1,lease_id=lease,lease_until=clock_timestamp()+interval '60 seconds',available_at=clock_timestamp()+delay WHERE id=d.id;
  PERFORM public.e1_append('NOTIFICATION_ATTEMPT',NULL,e.school_id,aid,jsonb_build_object('notification_id',d.id,'attempt',d.attempts+1)) FROM public.evidence_event e WHERE e.id=d.event_id;
  attempt_id:=aid; notification_id:=d.id; token:=ep.token; RETURN NEXT;
 END LOOP;
END $$;

CREATE FUNCTION public.e4_notification_result(aid uuid, lease uuid, ticket text, failure text, retry_after integer DEFAULT 0) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.notification_worker_attempt; d public.notification_worker_delivery; delay interval; stamp timestamptz:=clock_timestamp();
BEGIN
 SELECT * INTO a FROM public.notification_worker_attempt WHERE id=aid;
 IF a.id IS NULL THEN RETURN false; END IF;
 SELECT * INTO d FROM public.notification_worker_delivery WHERE id=a.delivery_id FOR UPDATE;
 SELECT * INTO a FROM public.notification_worker_attempt WHERE id=aid FOR UPDATE;
 IF a.state<>'SENDING' OR d.lease_id IS DISTINCT FROM lease OR d.lease_until<=stamp THEN RETURN false; END IF;
 IF ticket IS NOT NULL AND (length(ticket) NOT BETWEEN 1 AND 255 OR failure<>'') THEN RAISE EXCEPTION 'invalid ticket' USING ERRCODE='22023'; END IF;
 IF retry_after IS NULL OR retry_after<0 THEN RAISE EXCEPTION 'invalid retry interval' USING ERRCODE='22023'; END IF;
 IF failure IS NULL OR failure NOT IN ('','PROVIDER_UNAVAILABLE','DEVICE_NOT_REGISTERED','PROVIDER_REJECTED','INVALID_RESPONSE') OR (ticket IS NULL AND failure='') THEN RAISE EXCEPTION 'invalid result' USING ERRCODE='22023'; END IF;
 IF ticket IS NOT NULL THEN
  UPDATE public.notification_worker_attempt SET state='PROVIDER_ACCEPTED',ticket=e4_notification_result.ticket,receipt_available_at=stamp+interval '15 minutes' WHERE id=aid;
  UPDATE public.notification_worker_delivery SET state='PROVIDER_ACCEPTED',lease_id=NULL,lease_until=NULL,last_error='' WHERE id=d.id;
 ELSE
  delay:=(ARRAY[interval '30 seconds',interval '2 minutes',interval '5 minutes',interval '15 minutes',interval '15 minutes'])[d.attempts];
  UPDATE public.notification_worker_attempt SET state='FAILED',error=failure WHERE id=aid;
  UPDATE public.notification_worker_delivery SET state=CASE WHEN attempts>=5 THEN 'PENDING_REVIEW' ELSE 'PENDING' END,
   available_at=stamp+greatest(delay,make_interval(secs=>retry_after)),lease_id=NULL,lease_until=NULL,last_error=failure,
   escalated_at=CASE WHEN attempts>=5 THEN stamp ELSE escalated_at END WHERE id=d.id;
  IF failure='DEVICE_NOT_REGISTERED' THEN UPDATE public.notification_worker_endpoint SET active=false WHERE id=a.endpoint_id; END IF;
 END IF;
 PERFORM public.e1_append(CASE WHEN ticket IS NOT NULL THEN 'NOTIFICATION_ACCEPTED' WHEN d.attempts>=5 THEN 'NOTIFICATION_EXHAUSTED' ELSE 'NOTIFICATION_RETRY' END,
  NULL,e.school_id,aid,jsonb_build_object('notification_id',d.id,'status',CASE WHEN ticket IS NOT NULL THEN 'PROVIDER_ACCEPTED' ELSE failure END)) FROM public.evidence_event e WHERE e.id=d.event_id;
 RETURN true;
END $$;

CREATE FUNCTION public.e4_claim_receipts(maximum integer, lease uuid)
RETURNS TABLE(attempt_id uuid, ticket text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
 IF maximum IS NULL OR maximum NOT BETWEEN 1 AND 100 OR lease IS NULL THEN RAISE EXCEPTION 'invalid lease' USING ERRCODE='22023'; END IF;
 RETURN QUERY WITH due AS (
  SELECT a.id FROM public.notification_worker_attempt a WHERE a.state='PROVIDER_ACCEPTED'
   AND a.receipt_available_at<=clock_timestamp() AND (a.receipt_lease_until IS NULL OR a.receipt_lease_until<=clock_timestamp())
   ORDER BY a.receipt_available_at,a.id LIMIT maximum FOR UPDATE SKIP LOCKED
 ), claimed AS (
  UPDATE public.notification_worker_attempt a SET receipt_lease_id=lease,receipt_lease_until=clock_timestamp()+interval '60 seconds' FROM due WHERE a.id=due.id RETURNING a.id,a.ticket
 ) SELECT claimed.id,claimed.ticket::text FROM claimed;
END $$;

CREATE FUNCTION public.e4_notification_receipt(aid uuid, lease uuid, result text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.notification_worker_attempt; d public.notification_worker_delivery; stamp timestamptz:=clock_timestamp();
BEGIN
 IF result IS NULL OR result NOT IN ('OK','PENDING','PROVIDER_UNAVAILABLE','DEVICE_NOT_REGISTERED','PROVIDER_REJECTED') THEN RAISE EXCEPTION 'invalid receipt' USING ERRCODE='22023'; END IF;
 SELECT * INTO a FROM public.notification_worker_attempt WHERE id=aid;
 IF a.id IS NULL THEN RETURN false; END IF;
 SELECT * INTO d FROM public.notification_worker_delivery WHERE id=a.delivery_id FOR UPDATE;
 SELECT * INTO a FROM public.notification_worker_attempt WHERE id=aid FOR UPDATE;
 IF a.state<>'PROVIDER_ACCEPTED' OR a.receipt_lease_id IS DISTINCT FROM lease OR a.receipt_lease_until<=stamp THEN RETURN false; END IF;
 IF result='OK' THEN
  UPDATE public.notification_worker_attempt SET state='PROVIDER_RECEIPT',receipt_lease_id=NULL,receipt_lease_until=NULL WHERE id=aid;
  UPDATE public.notification_worker_delivery SET state='PROVIDER_RECEIPT',last_error='' WHERE id=d.id;
 ELSIF result IN ('PENDING','PROVIDER_UNAVAILABLE') AND a.created_at>stamp-interval '23 hours' THEN
  UPDATE public.notification_worker_attempt SET receipt_available_at=stamp+interval '1 minute',receipt_lease_id=NULL,receipt_lease_until=NULL WHERE id=aid;
  UPDATE public.notification_worker_delivery SET escalated_at=coalesce(escalated_at,stamp),last_error='RECEIPT_PENDING' WHERE id=d.id;
  RETURN true;
 ELSE
  UPDATE public.notification_worker_attempt SET state='RECEIPT_ERROR',error=result,receipt_lease_id=NULL,receipt_lease_until=NULL WHERE id=aid;
  UPDATE public.notification_worker_delivery SET state=CASE WHEN result IN ('PENDING','PROVIDER_UNAVAILABLE') OR attempts>=5 THEN 'PENDING_REVIEW' ELSE 'PENDING' END,
   available_at=stamp+(ARRAY[interval '30 seconds',interval '2 minutes',interval '5 minutes',interval '15 minutes',interval '15 minutes'])[d.attempts],
   last_error=result,escalated_at=coalesce(escalated_at,stamp) WHERE id=d.id;
  IF result='DEVICE_NOT_REGISTERED' THEN UPDATE public.notification_worker_endpoint SET active=false WHERE id=a.endpoint_id; END IF;
 END IF;
 PERFORM public.e1_append('NOTIFICATION_RECEIPT',NULL,e.school_id,aid,jsonb_build_object('notification_id',d.id,'status',result)) FROM public.evidence_event e WHERE e.id=d.event_id;
 RETURN true;
END $$;

CREATE FUNCTION public.e4_notification_status() RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
 SELECT jsonb_build_object('pending',count(*) FILTER(WHERE state IN ('PENDING','PENDING_DEVICE','PENDING_REVIEW')),
  'provider_accepted',count(*) FILTER(WHERE state='PROVIDER_ACCEPTED'),'provider_receipt',count(*) FILTER(WHERE state='PROVIDER_RECEIPT'),
  'escalated',count(*) FILTER(WHERE escalated_at IS NOT NULL AND state NOT IN ('PROVIDER_RECEIPT','SUPPRESSED')),
  'send_p95_seconds',(SELECT percentile_cont(0.95) WITHIN GROUP(ORDER BY extract(epoch FROM first_sent.at-physical.occurred_at)) FROM public.notification_worker_delivery nd JOIN public.evidence_event physical ON physical.id=nd.event_id JOIN LATERAL (SELECT min(ev.occurred_at) AS at FROM public.notification_worker_attempt a JOIN public.evidence_event ev ON ev.correlation_id=a.id AND ev.kind='NOTIFICATION_ACCEPTED' WHERE a.delivery_id=nd.id) first_sent ON first_sent.at IS NOT NULL),
  'oldest_pending_seconds',coalesce(max(extract(epoch FROM clock_timestamp()-created_at)) FILTER(WHERE state IN ('PENDING','PENDING_DEVICE','PENDING_REVIEW')),0))
 FROM public.notification_worker_delivery;
$$;

CREATE FUNCTION public.e4_retry_notification(did uuid, correlation uuid, operator text, approval text, reason text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE d public.notification_worker_delivery; original jsonb; requested jsonb; eid uuid;
BEGIN
 IF operator IS NULL OR length(btrim(operator)) NOT BETWEEN 1 AND 160
  OR approval IS NULL OR length(btrim(approval)) NOT BETWEEN 1 AND 160
  OR reason IS NULL OR length(btrim(reason)) NOT BETWEEN 1 AND 500 THEN
  RAISE EXCEPTION 'invalid reconciliation' USING ERRCODE='22023';
 END IF;
 requested:=jsonb_build_object('notification_id',did,'operator',operator,'approval',approval,'reason',reason,'credential',session_user);
 PERFORM pg_advisory_xact_lock(hashtextextended(correlation::text,41));
 SELECT id,convert_from(canonical,'UTF8')::jsonb->'snapshot' INTO eid,original
  FROM public.evidence_event WHERE kind='NOTIFICATION_RECONCILED' AND correlation_id=correlation;
 IF FOUND THEN
  IF original<>requested THEN RAISE EXCEPTION 'reconciliation conflict' USING ERRCODE='23505'; END IF;
  RETURN eid;
 END IF;
 SELECT * INTO d FROM public.notification_worker_delivery WHERE id=did FOR UPDATE;
 IF d.id IS NULL OR d.state<>'PENDING_REVIEW' OR NOT public.e4_recipient_enabled(did) THEN
  RAISE EXCEPTION 'reconciliation not permitted' USING ERRCODE='22023';
 END IF;
 -- Previous attempt rows and evidence remain intact. This starts another bounded
 -- retry cycle of the SAME logical notice, never another physical departure.
 UPDATE public.notification_worker_delivery SET state='PENDING',attempts=0,available_at=clock_timestamp(),lease_id=NULL,lease_until=NULL,last_error='',escalated_at=NULL WHERE id=did;
 SELECT public.e1_append('NOTIFICATION_RECONCILED',NULL,e.school_id,correlation,requested) INTO eid FROM public.evidence_event e WHERE e.id=d.event_id;
 RETURN eid;
END $$;

-- No provider callbacks are exposed: Expo receipts are pulled over authenticated
-- HTTPS and correlated to stored tickets. Runtime cannot fabricate provider state.
DO $$ DECLARE fn record;
BEGIN
 FOR fn IN SELECT oid::regprocedure AS signature FROM pg_proc WHERE pronamespace='public'::regnamespace AND proname LIKE 'e4_%' LOOP
  EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',fn.signature);
  EXECUTE format('ALTER FUNCTION %s OWNER TO retiro_evidence_writer',fn.signature);
 END LOOP;
END $$;
GRANT EXECUTE ON FUNCTION public.e4_endpoint(text,boolean) TO retiro_runtime;
GRANT EXECUTE ON FUNCTION public.e4_retry_notification(uuid,uuid,text,text,text) TO retiro_importer;
GRANT EXECUTE ON FUNCTION public.e4_claim_notifications(integer,uuid),public.e4_notification_result(uuid,uuid,text,text,integer),
 public.e4_claim_receipts(integer,uuid),public.e4_notification_receipt(uuid,uuid,text),public.e4_notification_status() TO retiro_notifier;
