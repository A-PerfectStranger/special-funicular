"""Immutable canonical bytes and separate operational archive state."""

import uuid

from django.db import models


class Head(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    sequence = models.PositiveBigIntegerField(default=0)
    digest = models.CharField(max_length=64, default="0" * 64)


class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sequence = models.PositiveBigIntegerField(unique=True)
    kind = models.CharField(max_length=64)
    actor = models.ForeignKey("identity.Account", null=True, on_delete=models.PROTECT)
    school = models.ForeignKey("school_roster.School", null=True, on_delete=models.PROTECT)
    occurred_at = models.DateTimeField()
    correlation_id = models.UUIDField()
    canonical = models.BinaryField()
    digest = models.CharField(max_length=64)
    previous_digest = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["kind", "correlation_id"], name="event_dedup")
        ]


class ArchiveJob(models.Model):
    event = models.OneToOneField(Event, primary_key=True, on_delete=models.PROTECT)
    attempts = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField()
    lease_until = models.DateTimeField(null=True)
    lease_id = models.UUIDField(null=True)
    last_error = models.CharField(max_length=40, default="")
    completed_at = models.DateTimeField(null=True)


class Receipt(models.Model):
    event = models.OneToOneField(Event, primary_key=True, on_delete=models.PROTECT)
    bucket = models.CharField(max_length=255)
    key = models.CharField(max_length=512)
    version_id = models.CharField(max_length=1024)
    digest = models.CharField(max_length=64)
    retained_until = models.DateTimeField()
    verified_at = models.DateTimeField()
    manifest_key = models.CharField(max_length=512)
    manifest_version = models.CharField(max_length=1024)
