"""The JSON Schema and the Python validator agree on the fixture files.

``valid/`` files pass both. ``invalid/`` files fail both. ``invalid-semantic/``
files break a rule that relates parts of the file (parents before children,
context ids, tool linkage); the Python validator rejects them, and the schema
is allowed but not required to.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from benchwarmer.interchange import validate_conversation_file

_ROOT = Path(__file__).parents[2]
_SCHEMA = _ROOT / "docs/schemas/conversation-file.v1.schema.json"
_FIXTURES = _ROOT / "tests/fixtures/conversation-files"


def _files(folder: str) -> list[Path]:
    files = sorted((_FIXTURES / folder).glob("*.json"))
    assert files, folder
    return files


def _schema() -> Draft202012Validator:
    schema = json.loads(_SCHEMA.read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.mark.parametrize("path", _files("valid"), ids=lambda p: p.name)
def test_valid_fixtures_pass_both(path: Path) -> None:
    document = json.loads(path.read_text())
    assert validate_conversation_file(document) == []
    assert list(_schema().iter_errors(document)) == []


@pytest.mark.parametrize("path", _files("invalid"), ids=lambda p: p.name)
def test_invalid_fixtures_fail_both(path: Path) -> None:
    document = json.loads(path.read_text())
    issues = validate_conversation_file(document)
    assert issues, "python validator accepted an invalid fixture"
    assert all(issue.path.startswith("$") for issue in issues)
    assert list(_schema().iter_errors(document)), "schema accepted an invalid fixture"


@pytest.mark.parametrize("path", _files("invalid-semantic"), ids=lambda p: p.name)
def test_semantic_fixtures_fail_the_python_validator(path: Path) -> None:
    document = json.loads(path.read_text())
    assert validate_conversation_file(document)
