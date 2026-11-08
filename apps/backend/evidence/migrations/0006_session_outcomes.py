from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("evidence", "0005_web_sessions")]
    operations = [
        migrations.RunSQL("""
CREATE OR REPLACE FUNCTION public.e1_logout(token_hash text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE s public.identity_session;
BEGIN
  SELECT * INTO s FROM public.identity_session
    WHERE access_hash=token_hash OR refresh_hash=token_hash FOR UPDATE;
  IF FOUND AND s.revoked_at IS NULL THEN
    UPDATE public.identity_session SET revoked_at=clock_timestamp() WHERE id=s.id;
    PERFORM public.e1_append('SESSION_CLOSED',s.account_id,
      (SELECT school_id FROM public.identity_account WHERE id=s.account_id),s.id,
      jsonb_build_object('result','REVOKED'));
  END IF;
END $$;

CREATE OR REPLACE FUNCTION public.e1_access_records(
  maximum integer, before_sequence bigint, school uuid)
RETURNS TABLE(sequence bigint, event_id uuid, actor_id uuid, school_id uuid,
  occurred_at timestamptz, result text) LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog AS $$
  SELECT e.sequence,e.id,e.actor_id,e.school_id,e.occurred_at,
    CASE WHEN s.enabled_at IS NOT NULL THEN 'OPENED'
         WHEN s.revoked_at IS NOT NULL OR s.protection_deadline<=statement_timestamp() THEN 'DENIED'
         ELSE 'PENDING_PROTECTION' END
  FROM public.evidence_event e LEFT JOIN public.identity_session s ON s.access_event_id=e.id
  WHERE EXISTS (SELECT 1 FROM public.e1_current_account() WHERE role='ADMIN_SISTEMA')
    AND e.kind='SCHOOL_LOGIN' AND (before_sequence IS NULL OR e.sequence<before_sequence)
    AND (school IS NULL OR e.school_id=school)
  ORDER BY e.sequence DESC LIMIT least(greatest(maximum,1),100);
$$;

-- A retry after downtime verifies the original seven-day object policy, not a
-- rolling seven-day extension. The adapter checks LastModified + policy days.
CREATE OR REPLACE FUNCTION public.e1_archive_completed(eid uuid, lease uuid, bucket text,
  object_key text, version text, hash text, retained_until timestamptz,
  manifest_key text, manifest_version text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
  PERFORM 1 FROM public.evidence_archivejob WHERE event_id=eid AND lease_id=lease
    AND lease_until>clock_timestamp() AND completed_at IS NULL FOR UPDATE;
  IF NOT FOUND OR retained_until<=clock_timestamp() OR NOT EXISTS
    (SELECT 1 FROM public.evidence_event WHERE id=eid AND digest=hash) OR
    version='' OR manifest_version='' THEN RETURN false; END IF;
  INSERT INTO public.evidence_receipt(event_id,bucket,key,version_id,digest,retained_until,
    verified_at,manifest_key,manifest_version)
    VALUES(eid,bucket,object_key,version,hash,retained_until,clock_timestamp(),manifest_key,manifest_version);
  UPDATE public.evidence_archivejob SET completed_at=clock_timestamp(),lease_until=NULL,
    lease_id=NULL,last_error='' WHERE event_id=eid;
  RETURN true;
END $$;
""")
    ]
