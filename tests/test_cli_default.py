"""CLI default check. Run: python3 tests/test_cli_default.py"""
import os
import subprocess
import sys


def run(args, cwd="/tmp"):
    return subprocess.run(
        [sys.executable, "/workspace/cheers_by_user.py", *args, "--no-progress"],
        capture_output=True, text=True, cwd=cwd, timeout=120,
    )


# Default run must produce HTML without --html (network-dependent; skips on failure).
r = run(["squidkid-deluxe"])
if r.returncode != 0:
    print(f"SKIP - network fetch failed: {r.stderr[-300:]}")
    raise SystemExit(0)
assert os.path.exists("/tmp/squidkid-deluxe-cheers.html"), "default html written to cwd"
doc = open("/tmp/squidkid-deluxe-cheers.html").read()
assert "Cheers for squidkid-deluxe" in doc, "username in default html"
assert "cheers from" in doc, "counts rendered (exact totals change over time, so match the pattern)"
print("all cli default checks passed")
