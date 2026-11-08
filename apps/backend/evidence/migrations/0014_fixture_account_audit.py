from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("evidence", "0013_synthetic_snapshot_export")]
    operations = [
        migrations.RunSQL("""
CREATE FUNCTION public.e1_audit_fixture_account(correlation uuid, target uuid, operation text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE account public.identity_account;
BEGIN
  IF session_user<>'retiro_importer' OR operation NOT IN ('REVOKE','RESET') THEN
    RAISE EXCEPTION 'fixture account command denied' USING ERRCODE='42501';
  END IF;
  SELECT * INTO account FROM public.identity_account WHERE id=target;
  IF NOT FOUND THEN RAISE EXCEPTION 'fixture account absent' USING ERRCODE='28000'; END IF;
  RETURN public.e1_append('SYNTHETIC_FIXTURE_ACCOUNT_'||operation,NULL,
    account.school_id,correlation,
    jsonb_build_object('dataset','E1_SYNTHETIC_ACCEPTANCE','technical_credential',session_user,
      'target_account_id',account.id,'active',account.active,'account_version',account.version,
      'role',account.role,'result','APPLIED'));
END $$;
ALTER FUNCTION public.e1_audit_fixture_account(uuid,uuid,text) OWNER TO retiro_evidence_writer;
REVOKE ALL ON FUNCTION public.e1_audit_fixture_account(uuid,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.e1_audit_fixture_account(uuid,uuid,text) TO retiro_importer;
""")
    ]
