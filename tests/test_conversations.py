"""Synthetic contract tests for normalized conversation v1."""

from __future__ import annotations

import copy
import json
import unittest
from importlib import import_module
from pathlib import Path
from typing import Any

_conversations = import_module("benchwarmer.conversations")
ConversationValidationError = _conversations.ConversationValidationError
dump_conversation_json = _conversations.dump_conversation_json
load_conversation_json = _conversations.load_conversation_json
validate_conversation = _conversations.validate_conversation


FIXTURES = Path(__file__).parent / "fixtures" / "conversations"


def fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


class ConversationFixturesTests(unittest.TestCase):
    def test_all_fixtures_validate_and_strictly_round_trip(self) -> None:
        for name in ("pi-branch.json", "hermes-continuation.json", "codex-tools.json"):
            with self.subTest(name=name):
                document = fixture(name)
                validate_conversation(document)
                encoded = dump_conversation_json(document)
                self.assertEqual(load_conversation_json(encoded), document)
                self.assertEqual(dump_conversation_json(load_conversation_json(encoded)), encoded)

    def test_validation_and_serialization_do_not_mutate_input(self) -> None:
        document = fixture("pi-branch.json")
        original = copy.deepcopy(document)
        validate_conversation(document)
        dump_conversation_json(document)
        self.assertEqual(document, original)

    def test_source_identity_remains_scoped(self) -> None:
        pi = fixture("pi-branch.json")
        hermes = fixture("hermes-continuation.json")
        self.assertEqual(pi["source"]["native_id"], hermes["source"]["native_id"])
        self.assertNotEqual(pi["source"]["scope_id"], hermes["source"]["scope_id"])
        validate_conversation(pi)
        validate_conversation(hermes)

    def test_relationship_retains_complete_source_scoped_target(self) -> None:
        document = fixture("hermes-continuation.json")
        relationship = document["relationships"][0]
        self.assertEqual(
            set(relationship),
            {"kind", "target_source_kind", "target_source_scope_id", "target_native_id", "extensions"},
        )
        del relationship["target_source_kind"]
        with self.assertRaises(ConversationValidationError):
            validate_conversation(document)

    def test_extensions_and_metadata_origins_are_preserved(self) -> None:
        document = fixture("codex-tools.json")
        document["metadata"] = [
            {
                "name": origin,
                "value": {"origin": origin},
                "origin": origin,
                "producer": "synthetic-test",
                "producer_version": None,
                "input_revision": "revision-codex-1",
                "extensions": {},
            }
            for origin in ("imported", "calculated", "generated", "human")
        ]
        restored = load_conversation_json(dump_conversation_json(document))
        self.assertEqual(restored["extensions"], document["extensions"])
        self.assertEqual(restored["metadata"], document["metadata"])

    def test_branch_local_call_reuse_is_valid_but_same_path_reuse_is_not(self) -> None:
        valid = fixture("pi-branch.json")
        validate_conversation(valid)
        invalid = copy.deepcopy(valid)
        invalid["events"][2]["content"].append(
            {
                "id": "same-path-call",
                "kind": "tool_call",
                "text": None,
                "tool_call_id": "native-call-1",
                "artifact_id": None,
                "extensions": {},
            }
        )
        with self.assertRaises(ConversationValidationError):
            validate_conversation(invalid)

    def test_partial_coverage_permits_missing_tool_call_but_available_does_not(self) -> None:
        document = fixture("codex-tools.json")
        validate_conversation(document)
        document["coverage"]["tool_calls"] = "available"
        with self.assertRaises(ConversationValidationError):
            validate_conversation(document)


class ConversationValidationTests(unittest.TestCase):
    def assert_invalid(self, document: object) -> None:
        with self.assertRaises(ConversationValidationError):
            validate_conversation(document)

    def test_rejects_unknown_structural_keys_references_and_unordered_events(self) -> None:
        document = fixture("pi-branch.json")
        document["unrecognized"] = None
        self.assert_invalid(document)

        document = fixture("pi-branch.json")
        document["events"][1]["parent_id"] = "not-an-event"
        self.assert_invalid(document)

        document = fixture("pi-branch.json")
        document["events"][2]["ordinal"] = 0
        self.assert_invalid(document)

        document = fixture("pi-branch.json")
        document["events"][0]["parent_id"] = "event-left"
        self.assert_invalid(document)

    def test_rejects_unhashable_event_kind_and_role_with_bounded_errors(self) -> None:
        for field, value in (("kind", []), ("role", {})):
            with self.subTest(field=field):
                document = fixture("pi-branch.json")
                document["events"][0][field] = value
                with self.assertRaisesRegex(
                    ConversationValidationError, rf"events\[0\]\.{field}$"
                ):
                    validate_conversation(document)

    def test_rejects_invalid_attachment_and_missing_coverage(self) -> None:
        document = fixture("codex-tools.json")
        document["events"][1]["content"][1]["artifact_id"] = "not-an-artifact"
        self.assert_invalid(document)

        document = fixture("codex-tools.json")
        del document["coverage"]["tool_calls"]
        with self.assertRaises(ConversationValidationError):
            validate_conversation(document)

        document = fixture("codex-tools.json")
        document["coverage"][1] = "available"
        self.assert_invalid(document)

    def test_rejects_malformed_json_and_duplicate_keys(self) -> None:
        for text in ('{"id":', '{"id":"one","id":"two"}'):
            with self.subTest(text=text):
                with self.assertRaises(ConversationValidationError):
                    load_conversation_json(text)

    def test_rejects_recursive_programmatic_json_with_bounded_errors(self) -> None:
        document = fixture("pi-branch.json")
        cycle: dict[str, Any] = {}
        cycle["self"] = cycle
        document["extensions"] = {"cycle": cycle}
        for function in (validate_conversation, dump_conversation_json):
            with self.subTest(function=function.__name__):
                with self.assertRaisesRegex(
                    ConversationValidationError, r"invalid field: extensions"
                ):
                    function(document)

    def test_errors_do_not_echo_private_sentinel_values_from_any_public_function(self) -> None:
        sentinel = "PRIVATE-SENTINEL-DO-NOT-ECHO"
        invalid = fixture("pi-branch.json")
        invalid["id"] = sentinel
        invalid["schema_version"] = 2
        invalid_extension = fixture("pi-branch.json")
        invalid_extension["extensions"] = {sentinel: object()}
        for function, argument in (
            (validate_conversation, invalid),
            (dump_conversation_json, invalid),
            (validate_conversation, invalid_extension),
            (dump_conversation_json, invalid_extension),
            (load_conversation_json, '{"id":"' + sentinel + '","id":"duplicate"}'),
            (load_conversation_json, '{"id":"' + sentinel),
        ):
            with self.subTest(function=function.__name__):
                with self.assertRaises(ConversationValidationError) as caught:
                    function(argument)
                self.assertNotIn(sentinel, str(caught.exception))

    def test_rejects_nonfinite_extension_values_and_bool_versions(self) -> None:
        document = fixture("pi-branch.json")
        document["extensions"] = {"number": float("nan")}
        self.assert_invalid(document)
        document = fixture("pi-branch.json")
        document["schema_version"] = True
        self.assert_invalid(document)


if __name__ == "__main__":
    unittest.main()
