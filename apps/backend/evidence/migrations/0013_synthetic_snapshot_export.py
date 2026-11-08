from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("evidence", "0012_refresh_family")]
    operations = [
        migrations.RunSQL("""
CREATE FUNCTION public.e1_export_fixture_snapshot(correlation uuid)
RETURNS TABLE(sequence bigint, event_id uuid, canonical_base64 text, digest text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
  IF session_user<>'retiro_importer' THEN
    RAISE EXCEPTION 'fixture export denied' USING ERRCODE='42501';
  END IF;
  IF (SELECT count(*)>=5000 OR coalesce(sum(octet_length(e.canonical)),0)>8388608
      FROM public.evidence_event e) THEN
    RAISE EXCEPTION 'fixture snapshot limit' USING ERRCODE='54000';
  END IF;
  -- A technical read command, never a caller-selected event kind, actor or payload.
  PERFORM public.e1_append('SYNTHETIC_SNAPSHOT_READ',NULL,NULL,correlation,
    jsonb_build_object('dataset','E1_SYNTHETIC_ACCEPTANCE',
      'technical_credential',session_user,'result','READ'));
  RETURN QUERY SELECT e.sequence,e.id,
    replace(encode(e.canonical,'base64'),E'\n',''),e.digest::text
    FROM public.evidence_event e ORDER BY e.sequence;
END $$;
ALTER FUNCTION public.e1_export_fixture_snapshot(uuid) OWNER TO retiro_evidence_writer;
REVOKE ALL ON FUNCTION public.e1_export_fixture_snapshot(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.e1_export_fixture_snapshot(uuid) TO retiro_importer;
""")
    ]
