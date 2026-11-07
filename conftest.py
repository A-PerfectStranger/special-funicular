import os
from collections.abc import Iterator

import pytest
from django.conf import settings
from django.db import connections
from django.test.utils import setup_databases, teardown_databases


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker: object) -> Iterator[None]:
    # Construir esquema con migrador; ejecutar tests con runtime real sin DDL.
    # pytest-django exige un blocker con contexto unblock.
    from pytest_django.plugin import DjangoDbBlocker

    assert isinstance(django_db_blocker, DjangoDbBlocker)
    runtime = settings.DATABASES["default"].copy()
    migration = runtime.copy()
    migration.update(
        USER="app_migrator", PASSWORD=os.environ.get("MIGRATION_DB_PASSWORD", "synthetic-migrator")
    )
    settings.DATABASES["default"] = migration
    connections["default"].close()
    connections["default"].settings_dict = migration
    with django_db_blocker.unblock():
        old_config = setup_databases(verbosity=0, interactive=False, keepdb=True)
    test_runtime = runtime.copy()
    test_runtime["NAME"] = migration["NAME"]
    connections["default"].close()
    settings.DATABASES["default"] = test_runtime
    connections["default"].settings_dict = test_runtime
    yield
    connections.close_all()
    settings.DATABASES["default"] = migration
    connections["default"].settings_dict = migration
    with django_db_blocker.unblock():
        teardown_databases(old_config, verbosity=0, keepdb=True)
    settings.DATABASES["default"] = runtime
