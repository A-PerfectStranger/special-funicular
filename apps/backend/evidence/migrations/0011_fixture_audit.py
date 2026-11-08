from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("evidence", "0010_archive_result_type")]
    operations = [
        migrations.RunSQL("""
CREATE FUNCTION public.e1_audit_fixture_command(correlation uuid, operation text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
  IF session_user<>'retiro_importer' OR operation NOT IN ('PROVISION','REVOKE','RESET') THEN
    RAISE EXCEPTION 'fixture command denied' USING ERRCODE='42501';
  END IF;
  RETURN public.e1_append('SYNTHETIC_FIXTURE_'||operation,NULL,NULL,correlation,
    jsonb_build_object('result','APPLIED','technical_credential',session_user,
      'dataset','E1_SYNTHETIC_ACCEPTANCE'));
END $$;
ALTER FUNCTION public.e1_audit_fixture_command(uuid,text) OWNER TO retiro_evidence_writer;
REVOKE ALL ON FUNCTION public.e1_audit_fixture_command(uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.e1_audit_fixture_command(uuid,text) TO retiro_importer;
""")
    ]
