from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("evidence", "0003_security")]
    # PostgreSQL requires UPDATE on a column to acquire an account row lock.
    # The no-login definer exposes no account mutation function.
    operations = [
        migrations.RunSQL(
            "GRANT UPDATE(version) ON public.identity_account TO retiro_evidence_writer"
        )
    ]
