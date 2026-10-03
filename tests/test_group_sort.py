"""Regression: group_by_user tolerates mixed create_date types. Run: python3 tests/test_group_sort.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cheers_by_user import cluster_by_date, group_by_user

cheers = [
    {"from_user": "alice", "id": 1, "create_date": 1791000000},
    {"from_user": "alice", "id": 2, "create_date": "not-a-timestamp"},
    {"from_user": "alice", "id": 3},
    {"from_user": "alice", "id": 4, "create_date": None},
]


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print(f"ok - {msg}")


grouped = group_by_user(cheers)  # must not raise TypeError
check(len(grouped["alice"]) == 4, "all 4 cheers grouped")
check(grouped["alice"][0]["id"] == 1, "numeric timestamp sorts first")
check(
    {c["id"] for c in grouped["alice"][1:]} == {2, 3, 4},
    "non-numeric/missing/None dates sort last",
)

clusters = cluster_by_date(grouped["alice"])
check(clusters[-1][0].startswith("Unknown date"), "bad timestamps land in trailing Unknown-date cluster")
check(len(clusters[-1][1]) == 3, "unknown cluster has 3 cheers")

recency = group_by_user(
    [
        {"from_user": "old_money", "id": 10, "create_date": 1790000000},
        {"from_user": "old_money", "id": 11, "create_date": 1790000100},
        {"from_user": "old_money", "id": 12, "create_date": 1790000200},
        {"from_user": "newbie", "id": 20, "create_date": 1791000000},
        {"from_user": "mystery", "id": 30, "create_date": "not-a-timestamp"},
    ]
)
check(
    list(recency) == ["newbie", "old_money", "mystery"],
    "givers ordered by most recent cheer, undated last",
)

print("all group sort tests passed")
