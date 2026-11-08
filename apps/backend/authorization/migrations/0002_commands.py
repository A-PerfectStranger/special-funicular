from pathlib import Path

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("authorization", "0001_initial"),
        ("identity", "0004_invitation"),
        ("school_roster", "0002_importbatch_enrollment"),
        ("evidence", "0014_fixture_account_audit"),
    ]
    operations = [migrations.RunSQL(Path(__file__).with_suffix(".sql").read_text())]
