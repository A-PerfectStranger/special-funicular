"""Operational pickup projections; the immutable facts remain in evidence.Event."""

import uuid

from django.db import models


class Episode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    student = models.ForeignKey("school_roster.Student", on_delete=models.PROTECT)
    local_date = models.DateField()
    closed_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["student", "local_date"], name="pickup_day")]


class Token(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    episode = models.ForeignKey(Episode, on_delete=models.PROTECT)
    authorization = models.ForeignKey("authorization.Authorization", on_delete=models.PROTECT)
    authorization_version = models.PositiveBigIntegerField()
    token_hash = models.CharField(max_length=64, unique=True)
    issued_at = models.DateTimeField()
    valid_from = models.DateTimeField()
    expires_at = models.DateTimeField()
    invalidated_at = models.DateTimeField(null=True)
    consumed_at = models.DateTimeField(null=True)


class Operation(models.Model):
    id = models.UUIDField(primary_key=True)
    episode = models.OneToOneField(Episode, on_delete=models.PROTECT)
    token = models.OneToOneField(Token, on_delete=models.PROTECT)
    guard = models.ForeignKey("identity.Account", on_delete=models.PROTECT)
    event = models.OneToOneField("evidence.Event", on_delete=models.PROTECT)
    state = models.CharField(max_length=32)
    protection_deadline = models.DateTimeField()
    enabled_at = models.DateTimeField(null=True)
    permission_expires_at = models.DateTimeField(null=True)
    incident_reason = models.CharField(max_length=48, default="")
    report_event = models.OneToOneField(
        "evidence.Event", null=True, related_name="physical_report", on_delete=models.PROTECT
    )
    report_result = models.CharField(max_length=20, default="")


class Command(models.Model):
    id = models.UUIDField(primary_key=True)
    actor = models.ForeignKey(
        "identity.Account", related_name="pickup_commands", on_delete=models.PROTECT
    )
    digest = models.CharField(max_length=64)
    result = models.JSONField()


class Clock(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    observed_at = models.DateTimeField()
    trusted_until = models.DateTimeField()
    external_at = models.DateTimeField(null=True)


class Limit(models.Model):
    key = models.CharField(primary_key=True, max_length=160)
    available = models.DecimalField(max_digits=12, decimal_places=6)
    denied = models.PositiveBigIntegerField(default=0)
    observed_at = models.DateTimeField()


class TrialHold(models.Model):
    """Private, bounded fault injection only for explicitly imported E3 synthetic fixtures."""

    student = models.OneToOneField(
        "school_roster.Student", primary_key=True, on_delete=models.PROTECT
    )
    until = models.DateTimeField()
