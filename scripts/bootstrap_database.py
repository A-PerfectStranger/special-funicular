"""Private synthetic E0 SQL bootstrap; invoked only by the operator ECS task."""

import json
import os
import subprocess
import sys

import psycopg
from psycopg import sql


def main() -> None:
    with psycopg.connect(autocommit=True) as root:
        for role, variable in [
            ("retiro_runtime", "RUNTIME_PASSWORD"),
            ("retiro_migrator", "MIGRATOR_PASSWORD"),
        ]:
            if not root.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
                root.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"
                    ).format(sql.Identifier(role))
                )
            root.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(os.environ[variable])
                )
            )
        root.execute("REVOKE ALL ON DATABASE retiro FROM PUBLIC")
        root.execute("GRANT CONNECT ON DATABASE retiro TO retiro_runtime, retiro_migrator")
        root.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        root.execute("GRANT USAGE, CREATE ON SCHEMA public TO retiro_migrator")
        root.execute("GRANT USAGE ON SCHEMA public TO retiro_runtime")
    with psycopg.connect(
        user="retiro_migrator", password=os.environ["MIGRATOR_PASSWORD"], autocommit=True
    ) as owner:
        owner.execute("CREATE TABLE public.e0_isolation_probe (school text NOT NULL)")
        try:
            owner.execute("INSERT INTO public.e0_isolation_probe VALUES ('school-a'), ('school-b')")
            owner.execute("ALTER TABLE public.e0_isolation_probe ENABLE ROW LEVEL SECURITY")
            owner.execute("ALTER TABLE public.e0_isolation_probe FORCE ROW LEVEL SECURITY")
            owner.execute(
                """CREATE POLICY tenant ON public.e0_isolation_probe USING
                (school=current_setting('app.school_id',true))"""
            )
            owner.execute("GRANT SELECT ON public.e0_isolation_probe TO retiro_runtime")
            with psycopg.connect(
                user="retiro_runtime", password=os.environ["RUNTIME_PASSWORD"], autocommit=True
            ) as runtime:
                assert runtime.execute(
                    "SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()"
                ).fetchone() == (True,)
                assert runtime.execute(
                    """SELECT rolsuper,rolbypassrls,rolcreatedb,rolcreaterole
                    FROM pg_roles WHERE rolname=current_user"""
                ).fetchone() == (False, False, False, False)
                assert runtime.execute("SELECT * FROM public.e0_isolation_probe").fetchall() == []
                for school in ["school-a", "school-b"]:
                    with runtime.transaction():
                        runtime.execute("SELECT set_config('app.school_id',%s,true)", (school,))
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
                    "CREATE TABLE public.forbidden(id int)",
                    "ALTER TABLE public.e0_isolation_probe DISABLE ROW LEVEL SECURITY",
                ]:
                    try:
                        runtime.execute(statement)
                    except psycopg.errors.InsufficientPrivilege:
                        pass
                    else:
                        raise RuntimeError("runtime privilege boundary failed")
        finally:
            owner.execute("DROP TABLE public.e0_isolation_probe")
    env = os.environ.copy()
    env.update(PGUSER="retiro_migrator", PGPASSWORD=os.environ["MIGRATOR_PASSWORD"])
    for key in ["MIGRATOR_PASSWORD", "RUNTIME_PASSWORD"]:
        env.pop(key, None)
    subprocess.run(
        [sys.executable, "manage.py", "migrate_locked", "--noinput"], env=env, check=True
    )
    env.update(PGUSER="retiro_runtime", PGPASSWORD=os.environ["RUNTIME_PASSWORD"])
    subprocess.run([sys.executable, "manage.py", "runworker", "--check"], env=env, check=True)
    print(
        json.dumps({"e0_database_tls_rls_privileges_migrations": "PASS", "business_enabled": False})
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("BLOCKED: database bootstrap failed (" + type(exc).__name__ + ")", file=sys.stderr)
        raise SystemExit(2) from None
