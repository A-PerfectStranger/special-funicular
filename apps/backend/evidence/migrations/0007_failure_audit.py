import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("evidence", "0006_session_outcomes")]
    operations = [
        migrations.AlterField(
            model_name="event",
            name="actor",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT, to="identity.account"
            ),
        ),
        migrations.RunSQL("""
CREATE FUNCTION public.e1_login_failed(fingerprint text, correlation uuid) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
  IF fingerprint !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'invalid fingerprint' USING ERRCODE='22023';
  END IF;
  RETURN public.e1_append('UNVERIFIED_LOGIN_FAILED',NULL,NULL,correlation,
    jsonb_build_object('result','DENIED','entrypoint_origin_fingerprint',fingerprint));
END $$;
ALTER FUNCTION public.e1_login_failed(text,uuid) OWNER TO retiro_evidence_writer;
REVOKE ALL ON FUNCTION public.e1_login_failed(text,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.e1_login_failed(text,uuid) TO retiro_runtime;
"""),
    ]
