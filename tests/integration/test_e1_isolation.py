"""AT02/AT04/AT05: real PostgreSQL roles, not the migration connection."""

import secrets
import uuid

import psycopg
import pytest

from tests.integration.e1_support import connect, digest, login, roster

pytestmark = pytest.mark.integration


def test_at02_families_schools_and_reused_connection() -> None:
    first, second = roster(), roster()
    token, _, _ = login(first["accounts"]["PADRE"])
    token2, _, _ = login(second["accounts"]["PADRE"])
    with connect() as db:
        for secret, expected in [(token, first["student"]), (token2, second["student"])]:
            assert db.execute("SELECT id FROM school_roster_student").fetchall() == []
            with db.transaction():
                db.execute("SELECT set_config('app.session_hash',%s,true)", (digest(secret),))
                assert db.execute("SELECT id FROM school_roster_student").fetchall() == [
                    (expected,)
                ]
                assert db.execute("SELECT count(*) FROM school_roster_link").fetchone() == (1,)
            assert db.execute("SELECT id FROM school_roster_student").fetchall() == []
        # Choosing an actor/school without its authenticated session is ineffective.
        with db.transaction():
            db.execute("SELECT set_config('app.school_id',%s,true)", (str(first["school"]),))
            db.execute(
                "SELECT set_config('app.actor_id',%s,true)", (str(first["accounts"]["PADRE"]),)
            )
            assert db.execute("SELECT id FROM school_roster_student").fetchall() == []


def test_at02_staff_cannot_enumerate_students_and_system_reader_has_no_table_access() -> None:
    data = roster()
    for role in ["GUARDIA", "ADMIN_ESCUELA", "ADMIN_SISTEMA"]:
        token, _, _ = login(data["accounts"][role], "mobile" if role == "GUARDIA" else "web")
        with connect() as db, db.transaction():
            db.execute("SELECT set_config('app.session_hash',%s,true)", (digest(token),))
            assert db.execute("SELECT id FROM school_roster_student").fetchall() == []
    with connect("system_read") as db:
        for table in [
            "school_roster_student",
            "school_roster_parent",
            "identity_account",
            "evidence_event",
        ]:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                db.execute(f"SELECT * FROM {table}")


def test_principal_required_unique_and_cross_school_references() -> None:
    first, second = roster(), roster()
    with connect("importer") as db:
        with pytest.raises(psycopg.errors.CheckViolation), db.transaction():
            db.execute(
                "UPDATE school_roster_link SET active=false WHERE student_id=%s",
                (first["student"],),
            )
        with pytest.raises(psycopg.errors.UniqueViolation):
            db.execute(
                "UPDATE school_roster_link SET principal=true WHERE parent_id=%s",
                (first["secondary"],),
            )
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            db.execute(
                "UPDATE school_roster_student SET site_id=%s WHERE id=%s",
                (second["site"], first["student"]),
            )
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            db.execute(
                "INSERT INTO school_roster_link"
                "(id,school_id,student_id,parent_id,active,principal,version) "
                "VALUES(%s,%s,%s,%s,true,false,1)",
                (uuid.uuid4(), second["school"], first["student"], second["parent"]),
            )


def test_at04_online_revocation_and_rotating_refresh() -> None:
    data = roster()
    access, refresh, _ = login(data["accounts"]["PADRE"])
    next_access, next_refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with connect() as db:
        assert (
            db.execute("SELECT e1_authenticate(%s,true)", (digest(access),)).fetchone()[0]["role"]
            == "PADRE"
        )
        assert db.execute(
            "SELECT e1_refresh(%s,%s,%s)",
            (digest(refresh), digest(next_access), digest(next_refresh)),
        ).fetchone() == (True,)
        assert db.execute("SELECT e1_authenticate(%s,true)", (digest(access),)).fetchone() == (
            None,
        )
        assert db.execute(
            "SELECT e1_refresh(%s,%s,%s)", (digest(refresh), digest("replay"), digest("replay2"))
        ).fetchone() == (False,)
        with connect("importer") as operator:
            operator.execute(
                "UPDATE identity_account SET active=false WHERE id=%s", (data["accounts"]["PADRE"],)
            )
        assert db.execute("SELECT e1_authenticate(%s,true)", (digest(next_access),)).fetchone() == (
            None,
        )
        assert db.execute(
            "SELECT e1_refresh(%s,%s,%s)",
            (digest(next_refresh), digest("never"), digest("never2")),
        ).fetchone() == (False,)


def test_at05_every_runtime_identity_denied_free_event_mutation() -> None:
    roster_data = roster()
    login(roster_data["accounts"]["PADRE"])
    for role in ["runtime", "system_read", "school_read", "archiver", "importer", "notifier"]:
        with connect(role) as db:
            assert db.execute(
                "SELECT rolsuper,rolbypassrls,rolcreatedb,rolcreaterole "
                "FROM pg_roles WHERE rolname=current_user"
            ).fetchone() == (False, False, False, False)
            for statement in [
                "INSERT INTO evidence_event(id) VALUES(gen_random_uuid())",
                "UPDATE evidence_event SET digest='bad'",
                "DELETE FROM evidence_event",
                "TRUNCATE evidence_event",
                "ALTER TABLE evidence_event DISABLE ROW LEVEL SECURITY",
                "SELECT e1_append('FORGED',NULL,NULL,gen_random_uuid(),'{}')",
                "CREATE TABLE public.forbidden_e1(id integer)",
            ]:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    db.execute(statement)
