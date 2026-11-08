"""Roster is provisioned privately. Applications have no roster write API."""

import uuid

from django.db import models


class School(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    active = models.BooleanField(default=True)


class Site(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT)
    name = models.CharField(max_length=160)
    timezone = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["id", "school"], name="site_school_pair")]


class Student(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT)
    site = models.ForeignKey(Site, on_delete=models.PROTECT)
    display_name = models.CharField(max_length=160)
    active = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["id", "school"], name="student_school_pair")]


class Parent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.OneToOneField("identity.Account", null=True, on_delete=models.PROTECT)


class Link(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.PROTECT)
    student = models.ForeignKey(Student, on_delete=models.PROTECT)
    parent = models.ForeignKey(Parent, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)
    principal = models.BooleanField(default=False)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["student", "parent"], name="student_parent_unique"),
            models.UniqueConstraint(
                fields=["student"],
                condition=models.Q(active=True, principal=True),
                name="one_active_principal",
            ),
        ]


class ImportBatch(models.Model):
    id = models.UUIDField(primary_key=True)
    school = models.ForeignKey(School, on_delete=models.PROTECT)
    payload = models.TextField()
    digest = models.CharField(max_length=64)
    operator = models.CharField(max_length=160)
    approval = models.CharField(max_length=160, default="")
    staged_at = models.DateTimeField()
    approved_at = models.DateTimeField(null=True)
    promoted_at = models.DateTimeField(null=True)


class Enrollment(models.Model):
    parent = models.OneToOneField(Parent, primary_key=True, on_delete=models.PROTECT)
    school = models.ForeignKey(School, on_delete=models.PROTECT)
    contact = models.EmailField(max_length=254)
    approval = models.CharField(max_length=160)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["contact"], name="enrollment_contact_unique")
        ]
