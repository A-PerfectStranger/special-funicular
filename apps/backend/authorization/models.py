"""Mutable family projections; immutable facts are written through evidence commands."""

import uuid

from django.db import models


class Policy(models.Model):
    student = models.OneToOneField(
        "school_roster.Student", primary_key=True, on_delete=models.PROTECT
    )
    # ISO weekday, local start/end, inclusive date bounds; no overnight windows.
    windows = models.JSONField()
    blocked = models.BooleanField(default=False)
    version = models.PositiveBigIntegerField(default=1)


class Caregiver(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    student = models.ForeignKey("school_roster.Student", on_delete=models.PROTECT)
    created_by = models.ForeignKey("identity.Account", on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    document = models.CharField(max_length=40)
    photo = models.BinaryField()
    version = models.PositiveBigIntegerField(default=1)
    active = models.BooleanField(default=True)


class Authorization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    student = models.ForeignKey("school_roster.Student", on_delete=models.PROTECT)
    caregiver = models.ForeignKey(Caregiver, on_delete=models.PROTECT)
    created_by = models.ForeignKey("identity.Account", on_delete=models.PROTECT)
    caregiver_version = models.PositiveBigIntegerField()
    link_version = models.PositiveBigIntegerField()
    policy_version = models.PositiveBigIntegerField()
    schedule = models.JSONField()
    version = models.PositiveBigIntegerField(default=1)
    revoked_at = models.DateTimeField(null=True)


class Command(models.Model):
    id = models.UUIDField(primary_key=True)
    actor = models.ForeignKey("identity.Account", on_delete=models.PROTECT)
    digest = models.CharField(max_length=64)
    result = models.JSONField()
