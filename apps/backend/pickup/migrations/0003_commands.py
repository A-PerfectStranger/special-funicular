from pathlib import Path

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("pickup", "0002_limit"), ("authorization", "0005_bulk_family_lock")]
    operations = [migrations.RunSQL(Path(__file__).with_suffix(".sql").read_text())]
