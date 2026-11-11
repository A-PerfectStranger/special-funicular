import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("pickup", "0007_session_recheck")]
    operations = [
        migrations.CreateModel(
            name="Correction",
            fields=[
                ("id", models.UUIDField(primary_key=True, serialize=False)),
                ("digest", models.CharField(max_length=64)),
                ("outcome", models.CharField(max_length=20)),
                (
                    "operation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="pickup.operation"
                    ),
                ),
                (
                    "event",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT, to="evidence.event"
                    ),
                ),
                (
                    "related_event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="pickup_corrections",
                        to="evidence.event",
                    ),
                ),
            ],
        ),
    ]
