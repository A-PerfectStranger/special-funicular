"""E0 infrastructure regressions, not acceptance of future domain RLS policies."""

import os

import psycopg
import pytest
from django.test import Client

pytestmark = pytest.mark.integration


def test_real_runtime_readiness(django_db_blocker: object) -> None:
    # No test DB or superuser fallback; connect to the configured runtime database.
    with django_db_blocker.unblock():  # type: ignore[attr-defined]
        assert Client().get("/health/ready").json() == {"status": "ready"}


def test_runtime_privileges_and_forced_rls() -> None:
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"], autocommit=True) as owner:
        owner.execute("DROP TABLE IF EXISTS public.e0_isolation_probe")
        owner.execute("CREATE TABLE public.e0_isolation_probe (school text NOT NULL)")
        try:
            owner.execute("INSERT INTO public.e0_isolation_probe VALUES ('school-a'), ('school-b')")
            owner.execute("ALTER TABLE public.e0_isolation_probe ENABLE ROW LEVEL SECURITY")
            owner.execute("ALTER TABLE public.e0_isolation_probe FORCE ROW LEVEL SECURITY")
            owner.execute("""CREATE POLICY tenant ON public.e0_isolation_probe USING
                (school = current_setting('app.school_id', true))""")
            owner.execute("GRANT SELECT ON public.e0_isolation_probe TO retiro_runtime")
            with psycopg.connect(autocommit=True) as runtime:
                privileges = runtime.execute("""SELECT rolsuper, rolbypassrls, rolcreatedb,
                    rolcreaterole FROM pg_roles WHERE rolname=current_user""").fetchone()
                assert privileges == (False, False, False, False)
                assert runtime.execute("SELECT * FROM public.e0_isolation_probe").fetchall() == []
                for school in ["school-a", "school-b"]:
                    with runtime.transaction():
                        runtime.execute("SELECT set_config('app.school_id', %s, true)", (school,))
                        assert runtime.execute(
                            "SELECT * FROM public.e0_isolation_probe"
                        ).fetchall() == [(school,)]
                    assert (
                        runtime.execute("SELECT * FROM public.e0_isolation_probe").fetchall() == []
                    )
                for statement in [
                    "UPDATE public.e0_isolation_probe SET school='other'",
                    "DELETE FROM public.e0_isolation_probe",
                    "TRUNCATE public.e0_isolation_probe",
                    "CREATE TABLE public.forbidden (id int)",
                    "ALTER TABLE public.e0_isolation_probe DISABLE ROW LEVEL SECURITY",
                ]:
                    with pytest.raises(psycopg.errors.InsufficientPrivilege):
                        runtime.execute(statement)
        finally:
            owner.execute("DROP TABLE public.e0_isolation_probe")
