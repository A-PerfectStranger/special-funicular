-- E1: constraints are enforced independently of application validation.
ALTER TABLE public.school_roster_student ADD CONSTRAINT student_site_school_fk
  FOREIGN KEY (site_id, school_id) REFERENCES public.school_roster_site(id, school_id);
ALTER TABLE public.identity_account ADD CONSTRAINT account_site_school_fk
  FOREIGN KEY (site_id, school_id) REFERENCES public.school_roster_site(id, school_id);
ALTER TABLE public.school_roster_link ADD CONSTRAINT link_student_school_fk
  FOREIGN KEY (student_id, school_id) REFERENCES public.school_roster_student(id, school_id);

-- Lock the student before changing its links, including concurrent principal changes.
CREATE FUNCTION public.e1_lock_link_student() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
  IF TG_OP = 'UPDATE' AND (NEW.student_id <> OLD.student_id OR NEW.school_id <> OLD.school_id) THEN
    RAISE EXCEPTION 'link identity is immutable' USING ERRCODE='23514';
  END IF;
  PERFORM 1 FROM public.school_roster_student
    WHERE id = COALESCE(NEW.student_id, OLD.student_id) FOR UPDATE;
  RETURN COALESCE(NEW, OLD);
END $$;
CREATE TRIGGER link_student_lock BEFORE INSERT OR UPDATE OR DELETE
  ON public.school_roster_link FOR EACH ROW EXECUTE FUNCTION public.e1_lock_link_student();

CREATE FUNCTION public.e1_principal_required() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE student uuid;
BEGIN
  IF TG_TABLE_NAME = 'school_roster_student' THEN student := NEW.id;
  ELSE student := COALESCE(NEW.student_id, OLD.student_id); END IF;
  IF EXISTS (SELECT 1 FROM public.school_roster_student WHERE id=student AND active)
     AND (SELECT count(*) FROM public.school_roster_link
          WHERE student_id=student AND active AND principal) <> 1 THEN
    RAISE EXCEPTION 'active student requires one principal' USING ERRCODE='23514';
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER student_principal_required AFTER INSERT OR UPDATE
  ON public.school_roster_student DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION public.e1_principal_required();
CREATE CONSTRAINT TRIGGER link_principal_required AFTER INSERT OR UPDATE OR DELETE
  ON public.school_roster_link DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION public.e1_principal_required();

CREATE FUNCTION public.e1_parent_role() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
  IF NEW.account_id IS NOT NULL AND NOT EXISTS
    (SELECT 1 FROM public.identity_account WHERE id=NEW.account_id AND role='PADRE') THEN
    RAISE EXCEPTION 'parent account must have PADRE role' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER parent_role BEFORE INSERT OR UPDATE ON public.school_roster_parent
  FOR EACH ROW EXECUTE FUNCTION public.e1_parent_role();

-- Changing a locally provisioned identity invalidates every old session online.
CREATE FUNCTION public.e1_account_version() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
  IF NEW.issuer <> OLD.issuer OR NEW.subject <> OLD.subject OR
     (NEW.role <> OLD.role AND EXISTS
       (SELECT 1 FROM public.school_roster_parent WHERE account_id=OLD.id)) THEN
    RAISE EXCEPTION 'provision a separate identity' USING ERRCODE='23514';
  END IF;
  NEW.version := OLD.version + 1;
  RETURN NEW;
END $$;
CREATE TRIGGER account_version BEFORE UPDATE ON public.identity_account
  FOR EACH ROW EXECUTE FUNCTION public.e1_account_version();

INSERT INTO public.evidence_head(id, sequence, digest) VALUES (1, 0, repeat('0',64));

-- Dedicated no-login definer has explicit RLS policies and the minimum grants.
DO $$ DECLARE tab text;
BEGIN
  FOREACH tab IN ARRAY ARRAY[
    'identity_account','identity_session','identity_loginrequest','identity_entrylimit',
    'school_roster_school','school_roster_site','school_roster_student',
    'school_roster_parent','school_roster_link',
    'evidence_head','evidence_event','evidence_archivejob','evidence_receipt'] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',tab);
    EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',tab);
    EXECUTE format('CREATE POLICY internal_writer ON public.%I TO retiro_evidence_writer USING (true) WITH CHECK (true)',tab);
  END LOOP;
END $$;
GRANT SELECT ON public.identity_account, public.identity_session, public.identity_loginrequest,
  public.school_roster_school, public.school_roster_site, public.school_roster_student,
  public.school_roster_parent, public.school_roster_link, public.evidence_event,
  public.evidence_receipt, public.evidence_archivejob, public.evidence_head
  TO retiro_evidence_writer;
GRANT INSERT ON public.identity_session, public.evidence_event, public.evidence_archivejob,
  public.evidence_receipt TO retiro_evidence_writer;
GRANT UPDATE ON public.identity_session, public.evidence_head, public.evidence_archivejob
  TO retiro_evidence_writer;

CREATE FUNCTION public.e1_current_account() RETURNS SETOF public.identity_account
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
  SELECT a.* FROM public.identity_account a JOIN public.identity_session s ON s.account_id=a.id
  WHERE s.access_hash=current_setting('app.session_hash',true)
    AND a.active AND a.version=s.account_version AND s.revoked_at IS NULL
    AND s.enabled_at IS NOT NULL AND s.expires_at>statement_timestamp()
    AND (s.channel='web' OR s.access_expires_at>statement_timestamp())
    AND s.last_seen_at > statement_timestamp() -
        CASE WHEN a.role='GUARDIA' THEN interval '5 minutes' ELSE interval '15 minutes' END
    AND (a.school_id IS NULL OR EXISTS
      (SELECT 1 FROM public.school_roster_school sch WHERE sch.id=a.school_id AND sch.active));
$$;

CREATE FUNCTION public.e1_can_read_student(student uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog AS $$
  SELECT EXISTS (SELECT 1 FROM public.e1_current_account() a
    JOIN public.school_roster_parent p ON p.account_id=a.id
    JOIN public.school_roster_link l ON l.parent_id=p.id
    JOIN public.school_roster_school sch ON sch.id=l.school_id AND sch.active
    WHERE a.role='PADRE' AND l.student_id=student AND l.active);
$$;

GRANT SELECT ON public.school_roster_student, public.school_roster_link,
  public.school_roster_parent TO retiro_runtime;
CREATE POLICY family_student ON public.school_roster_student TO retiro_runtime
  USING (public.e1_can_read_student(id));
CREATE POLICY family_link ON public.school_roster_link TO retiro_runtime
  USING (active AND parent_id IN (SELECT id FROM public.school_roster_parent));
CREATE POLICY family_parent ON public.school_roster_parent TO retiro_runtime
  USING (account_id IN (SELECT id FROM public.e1_current_account() WHERE role='PADRE'));

-- No application can enumerate local identities, insert evidence, or issue arbitrary sessions.
GRANT SELECT, INSERT, UPDATE ON public.identity_loginrequest, public.identity_entrylimit
  TO retiro_runtime;
CREATE POLICY login_requests ON public.identity_loginrequest TO retiro_runtime USING (true) WITH CHECK (true);
CREATE POLICY entry_limits ON public.identity_entrylimit TO retiro_runtime USING (true) WITH CHECK (true);

-- Import is a separate private credential, never present in API/reader/worker processes.
DO $$ DECLARE tab text;
BEGIN
  FOREACH tab IN ARRAY ARRAY['identity_account','school_roster_school','school_roster_site',
    'school_roster_student','school_roster_parent','school_roster_link'] LOOP
    EXECUTE format('GRANT SELECT,INSERT,UPDATE ON public.%I TO retiro_importer',tab);
    EXECUTE format('CREATE POLICY technical_import ON public.%I TO retiro_importer USING (true) WITH CHECK (true)',tab);
  END LOOP;
END $$;

-- Canonical format is versioned, byte-preserving PostgreSQL jsonb UTF-8 (no floats).
-- This generic helper is private; only narrow command functions below are callable.
CREATE FUNCTION public.e1_append(kind text, actor uuid, school uuid, correlation uuid,
  snapshot jsonb) RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE eid uuid := gen_random_uuid(); seq bigint; prev text; stamp timestamptz := clock_timestamp();
  body bytea; hash text;
BEGIN
  SELECT e.id INTO eid FROM public.evidence_event e WHERE e.kind=e1_append.kind
    AND e.correlation_id=correlation;
  IF FOUND THEN RETURN eid; END IF;
  eid := gen_random_uuid();
  SELECT sequence+1, digest INTO seq,prev FROM public.evidence_head WHERE id=1 FOR UPDATE;
  body := convert_to(jsonb_build_object('id',eid,'sequence',seq,'kind',kind,
    'schema_version',1,'canonical_format','pg-jsonb-utf8-v1','actor_id',actor,
    'school_id',school,'occurred_at',to_char(stamp AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
    'correlation_id',correlation,'previous_digest',prev,'snapshot',snapshot)::text,'UTF8');
  hash := encode(sha256(body),'hex');
  INSERT INTO public.evidence_event(id,sequence,kind,actor_id,school_id,occurred_at,
    correlation_id,canonical,digest,previous_digest)
    VALUES(eid,seq,kind,actor,school,stamp,correlation,body,hash,prev);
  INSERT INTO public.evidence_archivejob(event_id,attempts,available_at,last_error)
    VALUES(eid,0,stamp,'');
  UPDATE public.evidence_head SET sequence=seq,digest=hash WHERE id=1;
  RETURN eid;
END $$;

CREATE FUNCTION public.e1_open_session(login_id uuid, issuer text, subject text,
  access_hash text, refresh_hash text, authenticated_at timestamptz)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.identity_account; l public.identity_loginrequest; sid uuid := gen_random_uuid();
  stamp timestamptz := clock_timestamp(); eid uuid; deadline timestamptz;
BEGIN
  SELECT * INTO l FROM public.identity_loginrequest WHERE id=login_id AND consumed_at IS NOT NULL
    AND expires_at>stamp AND purpose='login';
  IF NOT FOUND THEN RAISE EXCEPTION 'login rejected' USING ERRCODE='28000'; END IF;
  SELECT * INTO a FROM public.identity_account WHERE identity_account.issuer=e1_open_session.issuer
    AND identity_account.subject=e1_open_session.subject AND active FOR SHARE;
  IF NOT FOUND OR (a.school_id IS NOT NULL AND NOT EXISTS
    (SELECT 1 FROM public.school_roster_school WHERE id=a.school_id AND active))
    OR (l.channel='web' AND a.role NOT IN ('ADMIN_ESCUELA','ADMIN_SISTEMA'))
    OR (l.channel='mobile' AND a.role NOT IN ('PADRE','GUARDIA'))
    OR authenticated_at>stamp+interval '30 seconds'
    OR authenticated_at<stamp-interval '5 minutes' THEN
    RAISE EXCEPTION 'login rejected' USING ERRCODE='28000';
  END IF;
  IF a.role='ADMIN_ESCUELA' THEN
    eid := public.e1_append('SCHOOL_LOGIN',a.id,a.school_id,login_id,
      jsonb_build_object('role',a.role,'result','PENDING_PROTECTION'));
    deadline := stamp+interval '5 seconds';
  ELSE
    PERFORM public.e1_append('SESSION_OPENED',a.id,a.school_id,login_id,
      jsonb_build_object('role',a.role,'result','VERIFIED'));
  END IF;
  INSERT INTO public.identity_session(id,account_id,account_version,login_id,channel,
    access_hash,refresh_hash,access_expires_at,expires_at,last_seen_at,authenticated_at,
    access_event_id,protection_deadline,enabled_at)
    VALUES(sid,a.id,a.version,login_id,l.channel,access_hash,refresh_hash,stamp+interval '5 minutes',
      stamp+CASE WHEN l.channel='web' THEN interval '12 hours' ELSE interval '7 days' END,
      stamp,authenticated_at,eid,deadline,CASE WHEN eid IS NULL THEN stamp END);
  RETURN jsonb_build_object('session_id',sid,'account_id',a.id,'role',a.role,
    'school_id',a.school_id,'site_id',a.site_id,'event_id',eid,'deadline',deadline);
END $$;

CREATE FUNCTION public.e1_enable_school_session(token_hash text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE s public.identity_session; stamp timestamptz:=clock_timestamp();
BEGIN
  SELECT * INTO s FROM public.identity_session WHERE access_hash=token_hash FOR UPDATE;
  IF NOT FOUND OR s.revoked_at IS NOT NULL THEN RETURN false; END IF;
  IF s.enabled_at IS NOT NULL THEN RETURN true; END IF;
  IF s.protection_deadline>stamp AND EXISTS
    (SELECT 1 FROM public.evidence_receipt r WHERE r.event_id=s.access_event_id
     AND r.verified_at<=s.protection_deadline AND r.retained_until>stamp
     AND r.digest=(SELECT digest FROM public.evidence_event WHERE id=s.access_event_id)) THEN
    UPDATE public.identity_session SET enabled_at=stamp WHERE id=s.id;
    RETURN true;
  END IF;
  IF s.protection_deadline<=stamp THEN
    UPDATE public.identity_session SET revoked_at=stamp WHERE id=s.id;
    PERFORM public.e1_append('SCHOOL_LOGIN_EVIDENCE_FAILED',s.account_id,
      (SELECT school_id FROM public.identity_account WHERE id=s.account_id),s.login_id,
      jsonb_build_object('result','DENIED'));
  END IF;
  RETURN false;
END $$;

CREATE FUNCTION public.e1_authenticate(token_hash text, touch boolean) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.identity_account; s public.identity_session;
BEGIN
  PERFORM set_config('app.session_hash',token_hash,true);
  SELECT * INTO s FROM public.identity_session WHERE access_hash=token_hash FOR UPDATE;
  SELECT * INTO a FROM public.e1_current_account();
  IF NOT FOUND THEN RETURN NULL; END IF;
  IF touch THEN UPDATE public.identity_session SET last_seen_at=clock_timestamp() WHERE id=s.id; END IF;
  RETURN jsonb_build_object('account_id',a.id,'role',a.role,'school_id',a.school_id,
    'site_id',a.site_id,'session_id',s.id,'authenticated_at',s.authenticated_at,'channel',s.channel);
END $$;

CREATE FUNCTION public.e1_refresh(old_refresh text, new_access text, new_refresh text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE s public.identity_session; a public.identity_account; stamp timestamptz:=clock_timestamp();
BEGIN
  SELECT * INTO s FROM public.identity_session WHERE refresh_hash=old_refresh FOR UPDATE;
  IF NOT FOUND THEN RETURN false; END IF;
  SELECT * INTO a FROM public.identity_account WHERE id=s.account_id FOR SHARE;
  IF s.channel<>'mobile' OR s.revoked_at IS NOT NULL OR NOT a.active OR
    a.version<>s.account_version OR s.expires_at<=stamp OR s.enabled_at IS NULL OR
    s.last_seen_at<=stamp-(CASE WHEN a.role='GUARDIA' THEN interval '5 minutes' ELSE interval '15 minutes' END)
    OR (a.school_id IS NOT NULL AND NOT EXISTS
      (SELECT 1 FROM public.school_roster_school WHERE id=a.school_id AND active)) THEN RETURN false; END IF;
  UPDATE public.identity_session SET access_hash=new_access,refresh_hash=new_refresh,
    access_expires_at=stamp+interval '5 minutes',last_seen_at=stamp WHERE id=s.id;
  RETURN true;
END $$;

CREATE FUNCTION public.e1_logout(token_hash text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE s public.identity_session;
BEGIN
  SELECT * INTO s FROM public.identity_session WHERE access_hash=token_hash FOR UPDATE;
  IF FOUND AND s.revoked_at IS NULL THEN
    UPDATE public.identity_session SET revoked_at=clock_timestamp() WHERE id=s.id;
    PERFORM public.e1_append('SESSION_CLOSED',s.account_id,
      (SELECT school_id FROM public.identity_account WHERE id=s.account_id),s.id,
      jsonb_build_object('result','REVOKED'));
  END IF;
END $$;

CREATE FUNCTION public.e1_reauthenticate(login_id uuid, issuer text, subject text,
  authenticated_at timestamptz) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE l public.identity_loginrequest; s public.identity_session; a public.identity_account;
BEGIN
  SELECT * INTO l FROM public.identity_loginrequest WHERE id=login_id AND purpose='reauth'
    AND consumed_at IS NOT NULL AND expires_at>clock_timestamp();
  IF NOT FOUND THEN RETURN false; END IF;
  SELECT * INTO s FROM public.identity_session WHERE id=l.session_id FOR UPDATE;
  SELECT * INTO a FROM public.identity_account WHERE id=s.account_id;
  IF a.issuer<>e1_reauthenticate.issuer OR a.subject<>e1_reauthenticate.subject OR
    NOT a.active OR a.version<>s.account_version OR s.revoked_at IS NOT NULL OR
    s.expires_at<=clock_timestamp() OR authenticated_at<clock_timestamp()-interval '5 minutes'
    OR authenticated_at>clock_timestamp()+interval '30 seconds' THEN RETURN false; END IF;
  UPDATE public.identity_session SET authenticated_at=e1_reauthenticate.authenticated_at,
    last_seen_at=clock_timestamp() WHERE id=s.id;
  PERFORM public.e1_append('SESSION_REAUTHENTICATED',a.id,a.school_id,login_id,
    jsonb_build_object('result','VERIFIED'));
  RETURN true;
END $$;

-- Only a local system-admin session, supplied to the isolated reader, can read this DTO.
CREATE FUNCTION public.e1_access_records(maximum integer, before_sequence bigint, school uuid)
RETURNS TABLE(sequence bigint, event_id uuid, actor_id uuid, school_id uuid,
  occurred_at timestamptz, result text) LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog AS $$
  SELECT e.sequence,e.id,e.actor_id,e.school_id,e.occurred_at,
    CASE WHEN r.event_id IS NOT NULL THEN 'PROTECTED' ELSE 'PENDING_PROTECTION' END
  FROM public.evidence_event e LEFT JOIN public.evidence_receipt r ON r.event_id=e.id
  WHERE EXISTS (SELECT 1 FROM public.e1_current_account() WHERE role='ADMIN_SISTEMA')
    AND e.kind='SCHOOL_LOGIN' AND (before_sequence IS NULL OR e.sequence<before_sequence)
    AND (school IS NULL OR e.school_id=school)
  ORDER BY e.sequence DESC LIMIT least(greatest(maximum,1),100);
$$;

CREATE FUNCTION public.e1_audit_access_read(correlation uuid) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a public.identity_account;
BEGIN
  SELECT * INTO a FROM public.e1_current_account() WHERE role='ADMIN_SISTEMA';
  IF NOT FOUND THEN RAISE EXCEPTION 'permission denied' USING ERRCODE='42501'; END IF;
  RETURN public.e1_append('SCHOOL_ACCESSES_READ',a.id,NULL,correlation,
    jsonb_build_object('result','READ','role',a.role));
END $$;

-- Archive workers claim leases; network calls happen after this transaction commits.
CREATE FUNCTION public.e1_claim_archive(batch integer, lease uuid)
RETURNS TABLE(event_id uuid, sequence bigint, canonical bytea, digest text, occurred_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
  RETURN QUERY WITH chosen AS (
    SELECT j.event_id FROM public.evidence_archivejob j
    WHERE j.completed_at IS NULL AND j.available_at<=clock_timestamp()
      AND (j.lease_until IS NULL OR j.lease_until<clock_timestamp())
    ORDER BY j.available_at,j.event_id LIMIT least(greatest(batch,1),100)
    FOR UPDATE SKIP LOCKED
  ), claimed AS (
    UPDATE public.evidence_archivejob j SET lease_id=lease,
      lease_until=clock_timestamp()+interval '30 seconds',attempts=attempts+1
    FROM chosen c WHERE j.event_id=c.event_id RETURNING j.event_id
  ) SELECT e.id,e.sequence,e.canonical,e.digest,e.occurred_at
    FROM claimed c JOIN public.evidence_event e ON e.id=c.event_id ORDER BY e.sequence;
END $$;

CREATE FUNCTION public.e1_archive_failed(eid uuid, lease uuid, error_code text) RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog AS $$
  UPDATE public.evidence_archivejob SET lease_until=NULL,lease_id=NULL,
    available_at=clock_timestamp()+least(attempts*attempts,900)*interval '1 second',
    last_error=CASE WHEN error_code IN ('ARCHIVE_UNAVAILABLE','INTEGRITY_FAILURE')
      THEN error_code ELSE 'ARCHIVE_UNAVAILABLE' END
  WHERE event_id=eid AND lease_id=lease AND completed_at IS NULL;
$$;

CREATE FUNCTION public.e1_archive_completed(eid uuid, lease uuid, bucket text, object_key text,
  version text, hash text, retained_until timestamptz, manifest_key text, manifest_version text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
  PERFORM 1 FROM public.evidence_archivejob WHERE event_id=eid AND lease_id=lease
    AND lease_until>clock_timestamp() AND completed_at IS NULL FOR UPDATE;
  IF NOT FOUND OR retained_until<clock_timestamp()+interval '6 days' OR NOT EXISTS
    (SELECT 1 FROM public.evidence_event WHERE id=eid AND digest=hash) OR
    version='' OR manifest_version='' THEN RETURN false; END IF;
  INSERT INTO public.evidence_receipt(event_id,bucket,key,version_id,digest,retained_until,
    verified_at,manifest_key,manifest_version)
    VALUES(eid,bucket,object_key,version,hash,retained_until,clock_timestamp(),manifest_key,manifest_version);
  UPDATE public.evidence_archivejob SET completed_at=clock_timestamp(),lease_until=NULL,
    lease_id=NULL,last_error='' WHERE event_id=eid;
  RETURN true;
END $$;

CREATE FUNCTION public.e1_archive_status() RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
  SELECT jsonb_build_object('pending',count(*) FILTER (WHERE completed_at IS NULL),
    'failed',count(*) FILTER (WHERE completed_at IS NULL AND attempts>0),
    'oldest_pending_seconds',coalesce(extract(epoch FROM
      clock_timestamp()-min(available_at) FILTER (WHERE completed_at IS NULL)),0))
  FROM public.evidence_archivejob;
$$;

-- No PUBLIC execute, including internal helpers and trigger functions.
DO $$ DECLARE fn record;
BEGIN
  FOR fn IN SELECT p.oid::regprocedure AS signature FROM pg_proc p
    JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname LIKE 'e1_%'
  LOOP
    EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC',fn.signature);
    EXECUTE format('ALTER FUNCTION %s OWNER TO retiro_evidence_writer',fn.signature);
  END LOOP;
END $$;
GRANT EXECUTE ON FUNCTION public.e1_current_account(),public.e1_can_read_student(uuid),
  public.e1_authenticate(text,boolean), public.e1_open_session(uuid,text,text,text,text,timestamptz),
  public.e1_enable_school_session(text), public.e1_refresh(text,text,text),public.e1_logout(text),
  public.e1_reauthenticate(uuid,text,text,timestamptz) TO retiro_runtime;
GRANT EXECUTE ON FUNCTION public.e1_access_records(integer,bigint,uuid),
  public.e1_audit_access_read(uuid) TO retiro_system_read;
GRANT EXECUTE ON FUNCTION public.e1_claim_archive(integer,uuid),
  public.e1_archive_failed(uuid,uuid,text),
  public.e1_archive_completed(uuid,uuid,text,text,text,text,timestamptz,text,text),
  public.e1_archive_status() TO retiro_archiver;
