"""Synthetic acceptance tests for the read-only Hermes schema-30 reader."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import sqlite3
import tempfile
import traceback
import unittest
from collections.abc import Callable
from unittest.mock import patch

from benchwarmer.adapters.hermes import HermesCapabilityError
from benchwarmer.adapters.hermes import reader
from benchwarmer.adapters.hermes.reader import (
    HermesReadError,
    HermesReadRequest,
    read_hermes_snapshot,
)

FIXTURE_DIRECTORY = Path(__file__).parents[2] / "fixtures" / "hermes" / "schema-30"
SCHEMA = (FIXTURE_DIRECTORY / "schema.sql").read_text()
EXPECTED = json.loads((FIXTURE_DIRECTORY / "expected.json").read_text())


def make_database(directory: Path, *, wal: bool = True) -> Path:
    path = directory / "state.db"
    connection = sqlite3.connect(path)
    try:
        connection.executescript(SCHEMA)
        if wal:
            connection.execute("PRAGMA journal_mode = WAL")
        connection.commit()
    finally:
        connection.close()
    return path


class HermesReaderTests(unittest.TestCase):
    def create_database(self, *, wal: bool = True) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return make_database(Path(directory.name), wal=wal)

    def read(self, path: Path):
        return read_hermes_snapshot(
            HermesReadRequest(path, EXPECTED["application_version"])
        )

    def mutate(
        self, path: Path, mutation: Callable[[sqlite3.Connection], object]
    ) -> None:
        connection = sqlite3.connect(path)
        try:
            mutation(connection)
            connection.commit()
        finally:
            connection.close()

    def assert_sanitized(self, error: BaseException, *private_values: str) -> None:
        rendered = "".join(traceback.format_exception(error))
        self.assertIsNone(error.__cause__)
        self.assertIsNone(error.__context__)
        self.assertNotIn("During handling of the above exception", rendered)
        for value in private_values:
            if value:
                self.assertNotIn(value, rendered)

    def test_reads_pinned_schema_with_deterministic_order_and_versions(self) -> None:
        result = self.read(self.create_database())

        self.assertEqual(result.schema_version, EXPECTED["schema_version"])
        self.assertEqual(result.application_version, EXPECTED["application_version"])
        self.assertEqual(result.adapter_version, EXPECTED["adapter_version"])
        self.assertEqual(
            result.capability_manifest_version,
            EXPECTED["capability_manifest_version"],
        )
        self.assertEqual(result.journal_mode, EXPECTED["journal_mode"])
        self.assertEqual(list(result.tables), EXPECTED["table_order"])
        self.assertEqual([row["id"] for row in result.tables["messages"]], [1, 2])
        self.assertEqual(
            [row["id"] for row in result.tables["sessions"]], ["session-a", "session-b"]
        )
        self.assertIsNone(result.tables["sessions"][1]["ended_at"])
        self.assertNotEqual(result.schema_version, result.capability_manifest_version)
        self.assertEqual(
            result.tables["sessions"][0]["fixture_extension"],
            EXPECTED["additive_value"],
        )
        unknown = {key for key, value in result.coverage.items() if value == "unknown"}
        self.assertEqual(unknown, {EXPECTED["additive_column"]})

    def test_schema_version_rejects_unsupported_and_invalid_rows(self) -> None:
        mutations = {
            "unsupported": lambda connection: connection.execute(
                "UPDATE schema_version SET version = 29"
            ),
            "zero": lambda connection: connection.execute("DELETE FROM schema_version"),
            "duplicate": lambda connection: connection.execute(
                "INSERT INTO schema_version VALUES (30)"
            ),
            "non-integer": lambda connection: connection.execute(
                "UPDATE schema_version SET version = 'bad'"
            ),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                path = self.create_database()
                self.mutate(path, mutation)
                with self.assertRaises(HermesCapabilityError) as raised:
                    self.read(path)
                if name == "unsupported":
                    self.assertEqual(
                        str(raised.exception), "unsupported Hermes schema version: 29"
                    )

    def test_schema_version_table_and_column_are_required(self) -> None:
        for name, mutation in {
            "table": lambda connection: connection.execute("DROP TABLE schema_version"),
            "column": lambda connection: connection.execute(
                "ALTER TABLE schema_version RENAME COLUMN version TO other"
            ),
        }.items():
            with self.subTest(name=name):
                path = self.create_database()
                self.mutate(path, mutation)
                with self.assertRaisesRegex(
                    HermesCapabilityError, "invalid Hermes schema version table"
                ):
                    self.read(path)

    def test_manifest_reports_each_intended_failure(self) -> None:
        mutations = {
            "table": (
                "DROP TABLE system_prompts",
                "missing required Hermes table: system_prompts",
            ),
            "column": (
                "ALTER TABLE messages DROP COLUMN content",
                "missing required Hermes column: messages.content",
            ),
            "primary-key": (
                "CREATE TABLE replacement AS SELECT * FROM session_model_usage; "
                "DROP TABLE session_model_usage; "
                "ALTER TABLE replacement RENAME TO session_model_usage",
                "incompatible Hermes primary key: session_model_usage",
            ),
        }
        for name, (sql, message) in mutations.items():
            with self.subTest(name=name):
                path = self.create_database()
                connection = sqlite3.connect(path)
                try:
                    connection.executescript(sql)
                    connection.commit()
                finally:
                    connection.close()
                with self.assertRaisesRegex(HermesCapabilityError, message):
                    self.read(path)

    def test_each_required_relationship_is_validated(self) -> None:
        relationships = (
            ("sessions", "parent_session_id", "sessions", "id"),
            ("sessions", "system_prompt_hash", "system_prompts", "hash"),
            ("messages", "session_id", "sessions", "id"),
            ("session_model_usage", "session_id", "sessions", "id"),
        )
        real_foreign_keys = reader._foreign_keys
        for table, column, target_table, target_column in relationships:
            with self.subTest(table=table, column=column):

                def without_relationship(connection, observed_table):
                    relationships = real_foreign_keys(connection, observed_table)
                    if observed_table == table:
                        relationships.discard((column, target_table, target_column))
                    return relationships

                with patch.object(
                    reader, "_foreign_keys", side_effect=without_relationship
                ):
                    with self.assertRaisesRegex(
                        HermesCapabilityError,
                        f"missing required Hermes relationship: {table}.{column}",
                    ):
                        self.read(self.create_database())

    def test_optional_columns_and_gateway_presence_have_explicit_coverage(self) -> None:
        path = self.create_database()
        self.mutate(
            path,
            lambda connection: connection.execute(
                "ALTER TABLE messages DROP COLUMN api_content"
            ),
        )
        result = self.read(path)
        self.assertEqual(result.coverage["column.messages.api_content"], "unavailable")
        self.assertEqual(
            {key for key, value in result.coverage.items() if value == "unknown"},
            {EXPECTED["additive_column"]},
        )

        missing_gateway = self.create_database()
        self.mutate(
            missing_gateway,
            lambda connection: connection.execute("DROP TABLE gateway_routing"),
        )
        self.assertEqual(
            self.read(missing_gateway).coverage["table.gateway_routing"], "unavailable"
        )

        invalid_gateway = self.create_database()
        connection = sqlite3.connect(invalid_gateway)
        try:
            connection.executescript(
                "CREATE TABLE replacement AS SELECT scope, session_key, updated_at FROM gateway_routing; "
                "DROP TABLE gateway_routing; "
                "ALTER TABLE replacement RENAME TO gateway_routing"
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaisesRegex(
            HermesCapabilityError,
            "missing required Hermes column: gateway_routing.entry_json",
        ):
            self.read(invalid_gateway)

    def test_hostile_additive_identifier_is_quoted_and_result_is_immutable(
        self,
    ) -> None:
        path = self.create_database()
        hostile = 'extra"; DROP TABLE sessions; --'
        self.mutate(
            path,
            lambda connection: connection.execute(
                'ALTER TABLE messages ADD COLUMN "extra""; DROP TABLE sessions; --" TEXT'
            ),
        )

        result = self.read(path)

        self.assertIn(hostile, result.tables["messages"][0])
        self.assertEqual(result.coverage[f"column.messages.{hostile}"], "unknown")
        self.assertIn("sessions", result.tables)
        with self.assertRaises(FrozenInstanceError):
            result.schema_version = 29  # type: ignore[misc]
        with self.assertRaises(TypeError):
            result.coverage["table.sessions"] = "unknown"  # type: ignore[index]
        with self.assertRaises(TypeError):
            result.tables["messages"] = ()  # type: ignore[index]
        with self.assertRaises(TypeError):
            result.tables["messages"][0]["content"] = "changed"  # type: ignore[index]

    def test_committed_wal_rows_are_visible_without_source_writes(self) -> None:
        path = self.create_database()
        writer = sqlite3.connect(path)
        try:
            writer.execute(
                "INSERT INTO messages (id, session_id, role, content, timestamp) "
                "VALUES (3, 'session-a', 'assistant', 'wal row', 3)"
            )
            writer.commit()
            wal = path.with_name(f"{path.name}-wal")
            shared_memory = path.with_name(f"{path.name}-shm")
            self.assertTrue(wal.is_file())
            self.assertTrue(shared_memory.is_file())
            main_before = path.read_bytes()
            wal_before = wal.read_bytes()
            # SQLite readers may update transient lock/index bytes in SHM. The
            # persisted database and WAL content must remain unchanged.
            result = self.read(path)
            self.assertEqual(path.read_bytes(), main_before)
            self.assertEqual(wal.read_bytes(), wal_before)
        finally:
            writer.close()
        self.assertEqual([row["id"] for row in result.tables["messages"]], [1, 2, 3])

    def test_snapshot_excludes_commit_after_transaction_starts(self) -> None:
        path = self.create_database()
        real_rows = reader._rows
        changed = False

        def rows_after_concurrent_commit(connection, capability):
            nonlocal changed
            if not changed:
                changed = True
                writer = sqlite3.connect(path)
                try:
                    writer.execute(
                        "UPDATE messages SET content = 'later private value'"
                    )
                    writer.commit()
                finally:
                    writer.close()
            return real_rows(connection, capability)

        with patch.object(reader, "_rows", side_effect=rows_after_concurrent_commit):
            result = self.read(path)
        self.assertTrue(changed)
        self.assertEqual(result.tables["messages"][0]["content"], "first message")

    def test_invalid_source_inputs_and_tracebacks_are_bounded(self) -> None:
        path = self.create_database()
        for value in (Path("relative.db"),):
            with self.subTest(value=value):
                with self.assertRaises(HermesReadError) as raised:
                    HermesReadRequest(value)
                self.assert_sanitized(raised.exception, str(value))
        for value in ("", "   "):
            with self.subTest(application_version=value):
                with self.assertRaises(HermesReadError) as raised:
                    HermesReadRequest(path, value)
                self.assert_sanitized(raised.exception, value)

        directory = path.parent / "directory"
        directory.mkdir()
        missing = path.parent / "private-missing.db"
        link = path.parent / "private-link.db"
        link.symlink_to(path)
        for invalid in (missing, directory, link):
            with self.subTest(path=invalid.name):
                with self.assertRaises(HermesReadError) as raised:
                    self.read(invalid)
                self.assert_sanitized(raised.exception, str(invalid), str(path))

        sentinel = "private-malformed-sentinel"
        malformed = path.parent / sentinel
        malformed.write_text(sentinel)
        with self.assertRaises(HermesReadError) as raised:
            self.read(malformed)
        self.assert_sanitized(
            raised.exception,
            str(malformed),
            sentinel,
            reader._source_uri(malformed),
        )

    def test_connections_close_after_success_and_capability_failure(self) -> None:
        path = self.create_database()
        self.read(path)
        self.mutate(
            path,
            lambda connection: connection.execute(
                "UPDATE sessions SET title = 'source remains writable'"
            ),
        )
        self.mutate(
            path,
            lambda connection: connection.execute(
                "ALTER TABLE messages DROP COLUMN content"
            ),
        )
        with self.assertRaises(HermesCapabilityError):
            self.read(path)
        self.mutate(
            path,
            lambda connection: connection.execute("UPDATE sessions SET pinned = 0"),
        )

    def test_requires_wal_before_private_rows_and_runtime_gate(self) -> None:
        with self.assertRaisesRegex(HermesCapabilityError, "WAL mode"):
            self.read(self.create_database(wal=False))
        path = self.create_database()
        with patch.object(
            reader,
            "require_wal_safe_sqlite",
            side_effect=RuntimeError("runtime sentinel"),
        ):
            with self.assertRaisesRegex(RuntimeError, "runtime sentinel"):
                self.read(path)


if __name__ == "__main__":
    unittest.main()
