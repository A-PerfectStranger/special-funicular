from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("evidence", "0004_account_lock"), ("sessions", "0001_initial")]
    operations = [
        migrations.RunSQL("""
            ALTER TABLE public.django_session ENABLE ROW LEVEL SECURITY;
            ALTER TABLE public.django_session FORCE ROW LEVEL SECURITY;
            GRANT SELECT,INSERT,UPDATE,DELETE ON public.django_session TO retiro_runtime;
            CREATE POLICY web_session_storage ON public.django_session
                TO retiro_runtime USING (true) WITH CHECK (true);
        """)
    ]
