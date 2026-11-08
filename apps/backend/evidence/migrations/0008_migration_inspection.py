from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("evidence", "0007_failure_audit")]
    operations = [migrations.RunSQL("GRANT SELECT ON public.django_migrations TO retiro_runtime")]
