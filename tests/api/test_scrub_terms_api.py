"""Named, versioned scrub term lists over invented terms."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

from fastapi.testclient import TestClient
import pytest

from benchwarmer.api.app import create_app
from benchwarmer.config import BenchwarmerSettings

_REPOSITORY_ROOT = Path(__file__).parents[2]


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    root = tmp_path / "private"
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=_REPOSITORY_ROOT,
        env=os.environ | {"BENCHWARMER_DATA_ROOT": str(root)},
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return TestClient(create_app(settings=BenchwarmerSettings(data_root=root)))


def test_lists_version_on_change_and_summaries_carry_no_terms(
    client: TestClient,
) -> None:
    assert client.get("/api/v1/scrub-terms").json() == {"items": []}
    missing = client.get("/api/v1/scrub-terms/program-a")
    assert missing.status_code == 404

    created = client.put(
        "/api/v1/scrub-terms/program-a",
        json={"terms": [" Wexley ", "wexley", "", "Orrin Vale"], "notes": "  "},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["name"] == "program-a" and body["version"] == 1
    assert body["terms"] == ["Wexley", "Orrin Vale"]
    assert body["term_count"] == 2 and body["notes"] is None
    assert body["retired_at"] is None

    # An unchanged save writes nothing.
    same = client.put(
        "/api/v1/scrub-terms/program-a", json={"terms": ["Wexley", "Orrin Vale"]}
    )
    assert same.json()["version"] == 1

    changed = client.put(
        "/api/v1/scrub-terms/program-a",
        json={"terms": ["Wexley", "Orrin Vale", "Marlow"], "notes": "Added one host"},
    )
    assert changed.json()["version"] == 2 and changed.json()["term_count"] == 3

    # The first version is immutable and still readable by number.
    first = client.get("/api/v1/scrub-terms/program-a", params={"version": 1})
    assert first.json()["terms"] == ["Wexley", "Orrin Vale"]
    latest = client.get("/api/v1/scrub-terms/program-a")
    assert latest.json()["version"] == 2
    assert (
        client.get("/api/v1/scrub-terms/program-a", params={"version": 9}).status_code
        == 404
    )

    client.put("/api/v1/scrub-terms/program-b", json={"terms": ["Quenby"]})
    listing = client.get("/api/v1/scrub-terms")
    items = listing.json()["items"]
    assert [(i["name"], i["version"], i["term_count"]) for i in items] == [
        ("program-a", 2, 3),
        ("program-b", 1, 1),
    ]
    for term in ("Wexley", "Orrin", "Marlow", "Quenby"):
        assert term not in listing.text


def test_retired_lists_hide_by_default_and_refuse_saves(client: TestClient) -> None:
    client.put("/api/v1/scrub-terms/old", json={"terms": ["Tallis"]})
    client.put("/api/v1/scrub-terms/old", json={"terms": ["Tallis", "Brae"]})

    retired = client.post("/api/v1/scrub-terms/old/retire")
    assert retired.status_code == 200
    assert retired.json()["version"] == 2 and retired.json()["retired_at"]
    assert "Tallis" not in retired.text

    assert client.get("/api/v1/scrub-terms").json()["items"] == []
    shown = client.get("/api/v1/scrub-terms", params={"include_retired": "true"})
    assert [i["name"] for i in shown.json()["items"]] == ["old"]
    # Both versions are marked, and a pinned read still works.
    first = client.get("/api/v1/scrub-terms/old", params={"version": 1}).json()
    assert first["retired_at"] is not None and first["terms"] == ["Tallis"]

    refused = client.put("/api/v1/scrub-terms/old", json={"terms": ["Tallis"]})
    assert refused.status_code == 409
    assert client.post("/api/v1/scrub-terms/none/retire").status_code == 404


def test_saves_are_validated_without_echoing_terms(client: TestClient) -> None:
    bad_name = client.put("/api/v1/scrub-terms/has space", json={"terms": ["x"]})
    assert bad_name.status_code == 422

    empty = client.put("/api/v1/scrub-terms/empty", json={"terms": ["", "  "]})
    assert empty.status_code == 422
    assert empty.json()["message"] == "a term list needs at least one term"

    too_many = client.put(
        "/api/v1/scrub-terms/big", json={"terms": [f"term-{i}" for i in range(201)]}
    )
    assert too_many.status_code == 422
    assert "term-" not in too_many.json().get("message", "")

    stray = client.put(
        "/api/v1/scrub-terms/shape", json={"terms": ["x"], "extra": True}
    )
    assert stray.status_code == 422
