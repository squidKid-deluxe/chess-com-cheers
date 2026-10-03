"""Stdlib-only tests for cluster_by_date(). Run: python3 tests/test_cluster.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cheers_by_user import cluster_by_date

DAY = 86400
BASE = 1791000000  # fixed reference timestamp, no wall-clock dependence

# Two bursts 7 days apart must stay separate (the 23-vs-30-days-ago case).
cheers = [
    {"id": 1, "create_date": BASE},
    {"id": 2, "create_date": BASE - 100},
    {"id": 3, "create_date": BASE - 7 * DAY},
    {"id": 4, "create_date": BASE - 7 * DAY - 200},
    {"id": 5, "create_date": "not-a-timestamp"},
    {"id": 6},
]


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print(f"ok - {msg}")


clusters = cluster_by_date(cheers)
check(len(clusters) == 3, f"3 clusters, got {len(clusters)}")
check(len(clusters[0][1]) == 2, "newest burst has 2 cheers")
check(len(clusters[1][1]) == 2, "older burst has 2 cheers")
check(clusters[2][0].startswith("Unknown date"), "bad timestamps grouped as Unknown date")
check(len(clusters[2][1]) == 2, "unknown cluster has 2 cheers")
check(" to " not in clusters[0][0], f"same-day label has no range: {clusters[0][0]!r}")
check("2 cheers" in clusters[0][0], f"count in label: {clusters[0][0]!r}")

single = cluster_by_date([{"id": 9, "create_date": BASE}])
check(single[0][0].endswith("1 cheer"), f"singular label: {single[0][0]!r}")

print("all cluster tests passed")
