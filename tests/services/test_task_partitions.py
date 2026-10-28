"""Partition assignment is a deterministic function of family and seed."""

from __future__ import annotations

from collections import Counter

import pytest

from benchwarmer.services.task_partitions import (
    DEFAULT_SPLIT,
    PartitionSplitInvalid,
    family_point,
    partition_for,
    validate_split,
)
from benchwarmer.tasks import PARTITIONS


def test_the_same_seed_and_family_always_land_on_the_same_side() -> None:
    split = validate_split(dict(DEFAULT_SPLIT))
    first = {
        f"family-{n}": partition_for("seed-a", f"family-{n}", split) for n in range(200)
    }
    again = {
        f"family-{n}": partition_for("seed-a", f"family-{n}", split) for n in range(200)
    }
    assert first == again
    assert set(first.values()) == set(PARTITIONS)
    # The hash is over the family, so another family set cannot move a family.
    assert partition_for("seed-a", "family-7", split) == first["family-7"]


def test_another_seed_gives_a_different_split_of_the_same_families() -> None:
    split = validate_split(dict(DEFAULT_SPLIT))
    families = [f"family-{n}" for n in range(200)]
    a = [partition_for("seed-a", family, split) for family in families]
    b = [partition_for("seed-b", family, split) for family in families]
    assert a != b
    assert 0.0 <= family_point("seed-a", "family-1") < 1.0


def test_the_split_fractions_are_honored_in_proportion() -> None:
    split = validate_split({"development": 0.5, "calibration": 0.25, "holdout": 0.25})
    counts = Counter(partition_for("seed", f"family-{n}", split) for n in range(4000))
    assert abs(counts["development"] / 4000 - 0.5) < 0.05
    assert abs(counts["calibration"] / 4000 - 0.25) < 0.05
    assert abs(counts["holdout"] / 4000 - 0.25) < 0.05

    everything = validate_split(
        {"development": 1.0, "calibration": 0.0, "holdout": 0.0}
    )
    assert {partition_for("seed", f"family-{n}", everything) for n in range(50)} == {
        "development"
    }


def test_a_split_must_name_each_partition_and_sum_to_one() -> None:
    with pytest.raises(PartitionSplitInvalid, match="sum to 1"):
        validate_split({"development": 0.6, "calibration": 0.3, "holdout": 0.3})
    with pytest.raises(PartitionSplitInvalid, match="negative"):
        validate_split({"development": 1.2, "calibration": -0.2, "holdout": 0.0})
    with pytest.raises(PartitionSplitInvalid, match="once each"):
        validate_split({"development": 1.0})
    assert sum(validate_split(dict(DEFAULT_SPLIT)).values()) == pytest.approx(1.0)
