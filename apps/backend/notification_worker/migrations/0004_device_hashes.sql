-- Private targeted device enrolment; only hashes leave SQL, never push tokens.
CREATE FUNCTION public.e4_notification_device_hashes(account uuid, correlation uuid, operator text, approval text, reason text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE result jsonb; eid uuid;
BEGIN
 IF operator IS NULL OR length(btrim(operator)) NOT BETWEEN 1 AND 160
  OR approval IS NULL OR length(btrim(approval)) NOT BETWEEN 1 AND 160
  OR reason IS NULL OR length(btrim(reason)) NOT BETWEEN 1 AND 500
  OR NOT EXISTS(SELECT 1 FROM public.identity_account WHERE id=account AND active AND role='PADRE') THEN
  RAISE EXCEPTION 'invalid device enrolment' USING ERRCODE='22023';
 END IF;
 SELECT jsonb_agg(encode(sha256(convert_to(token,'UTF8')),'hex') ORDER BY id) INTO result
  FROM public.notification_worker_endpoint WHERE account_id=account AND active;
 IF result IS NULL THEN RAISE EXCEPTION 'no registered device' USING ERRCODE='22023'; END IF;
 eid:=public.e1_append('NOTIFICATION_DEVICE_HASHES_READ',NULL,NULL,gen_random_uuid(),jsonb_build_object('request_id',correlation,'account_id',account,'operator',operator,'approval',approval,'reason',reason,'credential',session_user));
 RETURN jsonb_build_object('hashes',result,'event_id',eid,'protected',EXISTS(SELECT 1 FROM public.evidence_receipt WHERE event_id=eid));
END $$;
REVOKE ALL ON FUNCTION public.e4_notification_device_hashes(uuid,uuid,text,text,text) FROM PUBLIC;
ALTER FUNCTION public.e4_notification_device_hashes(uuid,uuid,text,text,text) OWNER TO retiro_evidence_writer;
GRANT EXECUTE ON FUNCTION public.e4_notification_device_hashes(uuid,uuid,text,text,text) TO retiro_importer;
