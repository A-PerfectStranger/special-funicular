from unittest.mock import MagicMock, patch

import pytest
from core.management.commands.migrate_locked import LOCK_ID, Command
from django.core.management.base import CommandError


def test_runtime_cannot_enter_migration_command() -> None:
    cursor = MagicMock()
    cursor.fetchone.return_value = ("retiro_runtime",)
    with patch("core.management.commands.migrate_locked.connection") as connection:
        connection.cursor.return_value.__enter__.return_value = cursor
        with pytest.raises(CommandError, match="separate migration"):
            Command().handle()
    assert cursor.execute.call_count == 1


def test_failed_migration_releases_the_session_lock() -> None:
    cursor = MagicMock()
    cursor.fetchone.return_value = ("retiro_migrator",)
    cursor.fetchall.return_value = []
    with patch("core.management.commands.migrate_locked.connection") as connection:
        connection.cursor.return_value.__enter__.return_value = cursor
        with patch(
            "core.management.commands.migrate_locked.call_command",
            side_effect=RuntimeError("failed"),
        ):
            with pytest.raises(RuntimeError, match="failed"):
                Command().handle()
    assert cursor.execute.call_args.args == ("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))


def test_uncommissioned_identity_blocks_before_any_migration() -> None:
    cursor = MagicMock()
    cursor.fetchone.return_value = ("retiro_migrator",)
    cursor.fetchall.return_value = [("retiro_evidence_writer",)]
    with patch("core.management.commands.migrate_locked.connection") as connection:
        connection.cursor.return_value.__enter__.return_value = cursor
        with patch("core.management.commands.migrate_locked.call_command") as migrate:
            with pytest.raises(CommandError, match="commission safe E1"):
                Command().handle()
            migrate.assert_not_called()
