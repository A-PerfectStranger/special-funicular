"""Synthetic E1 fixtures using the same restricted credentials as runtime."""

import hashlib
import secrets
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
from psycopg import Connection


@contextmanager
def connect(role: str = "runtime") -> Iterator[Connection[Any]]:
    passwords = {
        "runtime": "synthetic-runtime-only",
        "importer": "synthetic-importer-only",
        "archiver": "synthetic-archiver-only",
        "school_read": "synthetic-school-read-only",
        "system_read": "synthetic-system-read-only",
        "notifier": "synthetic-notifier-only",
    }
    with psycopg.connect(user=f"retiro_{role}", password=passwords[role], autocommit=True) as conn:
        yield conn


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def roster() -> dict[str, Any]:
    ids = {key: uuid.uuid4() for key in ["school", "site", "student", "parent", "secondary"]}
    ids["accounts"] = {
        role: uuid.uuid4() for role in ["PADRE", "GUARDIA", "ADMIN_ESCUELA", "ADMIN_SISTEMA"]
    }
    ids["other_parent"] = uuid.uuid4()
    with connect("importer") as db, db.transaction():
        db.execute(
            "INSERT INTO school_roster_school(id,name,active) VALUES(%s,'Synthetic school',true)",
            (ids["school"],),
        )
        db.execute(
            "INSERT INTO school_roster_site(id,school_id,name,timezone) "
            "VALUES(%s,%s,'Synthetic site','America/Bogota')",
            (ids["site"], ids["school"]),
        )
        for role, aid in {**ids["accounts"], "other_parent": ids["other_parent"]}.items():
            actual_role = "PADRE" if role == "other_parent" else role
            school = ids["school"] if actual_role in {"GUARDIA", "ADMIN_ESCUELA"} else None
            site = ids["site"] if actual_role == "GUARDIA" else None
            db.execute(
                "INSERT INTO identity_account"
                "(id,issuer,subject,role,school_id,site_id,active,version) "
                "VALUES(%s,'https://idp.example',%s,%s,%s,%s,true,1)",
                (aid, str(aid), actual_role, school, site),
            )
        for parent, aid in [
            ("parent", ids["accounts"]["PADRE"]),
            ("secondary", ids["other_parent"]),
        ]:
            db.execute(
                "INSERT INTO school_roster_parent(id,account_id) VALUES(%s,%s)", (ids[parent], aid)
            )
        db.execute(
            "INSERT INTO school_roster_student(id,school_id,site_id,display_name,active) "
            "VALUES(%s,%s,%s,'Synthetic student',true)",
            (ids["student"], ids["school"], ids["site"]),
        )
        for parent in ["parent", "secondary"]:
            db.execute(
                "INSERT INTO school_roster_link"
                "(id,school_id,student_id,parent_id,active,principal,version) "
                "VALUES(%s,%s,%s,%s,true,%s,1)",
                (uuid.uuid4(), ids["school"], ids["student"], ids[parent], parent == "parent"),
            )
    return ids


def login(aid: uuid.UUID, channel: str = "mobile") -> tuple[str, str, dict[str, Any]]:
    access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with connect() as db:
        lid = uuid.uuid4()
        now = datetime.now(UTC)
        db.execute(
            "INSERT INTO identity_loginrequest(id,state_hash,binding_hash,nonce,challenge,channel,"
            "purpose,expires_at,consumed_at) VALUES(%s,%s,%s,'nonce','challenge',%s,'login',%s,%s)",
            (
                lid,
                secrets.token_hex(32),
                secrets.token_hex(32),
                channel,
                now + timedelta(minutes=5),
                now,
            ),
        )
        row = db.execute(
            "SELECT e1_open_session(%s,'https://idp.example',%s,%s,%s,%s)",
            (lid, str(aid), digest(access), digest(refresh), now),
        ).fetchone()
        assert row is not None
        return access, refresh, row[0]
