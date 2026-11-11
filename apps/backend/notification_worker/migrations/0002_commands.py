from pathlib import Path

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("notification_worker", "0001_initial"), ("pickup", "0009_school_records")]
    operations = [migrations.RunSQL(Path(__file__).with_suffix(".sql").read_text())]
