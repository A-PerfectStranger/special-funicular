from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("evidence", "0009_access_date_filter")]
    operations = [
        migrations.RunSQL("""
CREATE OR REPLACE FUNCTION public.e1_claim_archive(batch integer, lease uuid)
RETURNS TABLE(event_id uuid, sequence bigint, canonical bytea, digest text,
  occurred_at timestamptz)
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
  ) SELECT e.id,e.sequence,e.canonical,e.digest::text,e.occurred_at
    FROM claimed c JOIN public.evidence_event e ON e.id=c.event_id ORDER BY e.sequence;
END $$;
CREATE OR REPLACE FUNCTION public.e1_archive_status() RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
  SELECT jsonb_build_object('pending',count(*) FILTER (WHERE j.completed_at IS NULL),
    'failed',count(*) FILTER (WHERE j.completed_at IS NULL AND j.attempts>0),
    'oldest_pending_seconds',coalesce(extract(epoch FROM clock_timestamp()-
      min(e.occurred_at) FILTER (WHERE j.completed_at IS NULL)),0))
  FROM public.evidence_archivejob j JOIN public.evidence_event e ON e.id=j.event_id;
$$;
""")
    ]
