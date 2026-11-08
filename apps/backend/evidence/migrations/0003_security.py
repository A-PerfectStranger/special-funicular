from pathlib import Path

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("evidence", "0002_initial"),
        ("identity", "0002_initial"),
        ("school_roster", "0001_initial"),
    ]

    # Evidence/schema rollback is deliberately unavailable; deploy compatible code instead.
    operations = [migrations.RunSQL(Path(__file__).with_suffix(".sql").read_text())]
