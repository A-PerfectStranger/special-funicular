"""Local authorization is independent of IdP claims. No Django superusers."""

import uuid

from django.db import models


class Role(models.TextChoices):
    PADRE = "PADRE"
    GUARDIA = "GUARDIA"
    ADMIN_ESCUELA = "ADMIN_ESCUELA"
    ADMIN_SISTEMA = "ADMIN_SISTEMA"


class Account(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issuer = models.CharField(max_length=512)
    subject = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=Role.choices)
    school = models.ForeignKey("school_roster.School", null=True, on_delete=models.PROTECT)
    site = models.ForeignKey("school_roster.Site", null=True, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["issuer", "subject"], name="account_oidc_unique"),
            models.CheckConstraint(
                condition=models.Q(role__in=Role.values), name="account_exact_role"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(role="GUARDIA", school__isnull=False, site__isnull=False)
                    | models.Q(role="ADMIN_ESCUELA", school__isnull=False, site__isnull=True)
                    | models.Q(
                        role__in=["PADRE", "ADMIN_SISTEMA"],
                        school__isnull=True,
                        site__isnull=True,
                    )
                ),
                name="account_role_scope",
            ),
        ]


class LoginRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    state_hash = models.CharField(max_length=64, unique=True)
    binding_hash = models.CharField(max_length=64)
    nonce = models.CharField(max_length=128)
    challenge = models.CharField(max_length=128)
    channel = models.CharField(max_length=6, choices=[("web", "web"), ("mobile", "mobile")])
    purpose = models.CharField(max_length=8, default="login")
    session_id = models.UUIDField(null=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)


class Session(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    account_version = models.PositiveBigIntegerField()
    login = models.OneToOneField(LoginRequest, on_delete=models.PROTECT)
    channel = models.CharField(max_length=6)
    access_hash = models.CharField(max_length=64, unique=True)
    refresh_hash = models.CharField(max_length=64, unique=True)
    access_expires_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()
    authenticated_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True)
    access_event_id = models.UUIDField(null=True)
    protection_deadline = models.DateTimeField(null=True)
    enabled_at = models.DateTimeField(null=True)


class EntryLimit(models.Model):
    """HMAC keyed account/origin/entrypoint buckets; no raw usernames/IP addresses."""

    key = models.CharField(primary_key=True, max_length=64)
    failures = models.PositiveIntegerField(default=0)
    window_started_at = models.DateTimeField()
    blocked_until = models.DateTimeField(null=True)


class RetiredRefresh(models.Model):
    """Revocation capability after rotation; never usable to authenticate again."""

    token_hash = models.CharField(primary_key=True, max_length=64)
    session = models.ForeignKey(Session, on_delete=models.PROTECT)
    retired_at = models.DateTimeField()


class Invitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    parent = models.ForeignKey("school_roster.Parent", on_delete=models.PROTECT)
    token_hash = models.CharField(max_length=64, unique=True)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True)
    revoked_at = models.DateTimeField(null=True)
