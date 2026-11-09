from pathlib import Path

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("pickup", "0004_trialhold")]
    operations = [migrations.RunSQL(Path(__file__).with_suffix(".sql").read_text())]
