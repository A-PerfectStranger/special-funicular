from pathlib import Path

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("authorization", "0003_exact_activation_contact")]
    operations = [migrations.RunSQL(Path(__file__).with_suffix(".sql").read_text())]
