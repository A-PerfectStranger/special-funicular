from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("evidence", "0008_migration_inspection")]
    operations = [
        migrations.RunSQL("""
CREATE FUNCTION public.e1_access_records(maximum integer, before_sequence bigint, school uuid,
  since_at timestamptz, until_at timestamptz)
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
    AND (since_at IS NULL OR e.occurred_at>=since_at)
    AND (until_at IS NULL OR e.occurred_at<until_at)
  ORDER BY e.sequence DESC LIMIT least(greatest(maximum,1),100);
$$;
ALTER FUNCTION public.e1_access_records(integer,bigint,uuid,timestamptz,timestamptz)
  OWNER TO retiro_evidence_writer;
REVOKE ALL ON FUNCTION public.e1_access_records(integer,bigint,uuid,timestamptz,timestamptz)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.e1_access_records(integer,bigint,uuid,timestamptz,timestamptz)
  TO retiro_system_read;
""")
    ]
