"""Operational push state; canonical facts remain in the immutable event stream."""

import uuid

from django.db import models


class Endpoint(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    account = models.ForeignKey("identity.Account", on_delete=models.PROTECT)
    token = models.CharField(max_length=255, unique=True)
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField()


class Delivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    event = models.ForeignKey("evidence.Event", on_delete=models.PROTECT)
    operation = models.ForeignKey("pickup.Operation", on_delete=models.PROTECT)
    recipient = models.ForeignKey("identity.Account", on_delete=models.PROTECT)
    state = models.CharField(max_length=32, default="PENDING")
    created_at = models.DateTimeField()
    available_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)
    lease_id = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    escalated_at = models.DateTimeField(null=True)
    last_error = models.CharField(max_length=40, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["event", "recipient"], name="notification_logical")
        ]


class Attempt(models.Model):
    id = models.UUIDField(primary_key=True)
    delivery = models.ForeignKey(Delivery, on_delete=models.PROTECT)
    endpoint = models.ForeignKey(Endpoint, null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField()
    state = models.CharField(max_length=32, default="SENDING")
    ticket = models.CharField(max_length=255, null=True, unique=True)
    receipt_available_at = models.DateTimeField(null=True)
    receipt_lease_id = models.UUIDField(null=True)
    receipt_lease_until = models.DateTimeField(null=True)
    error = models.CharField(max_length=40, default="")
