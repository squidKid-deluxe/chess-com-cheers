"""Render check: dark cards, clusters, no broken images. Run: python3 tests/test_render.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cheers_by_user import write_html

grouped = {
    "B giver": [
        {"id": 2, "create_date": 1791000000, "trophy": "Pizza Order",
         "description": "yum", "custom_image_url": "",
         "from_user_avatar": ""},
        {"id": 1, "create_date": 1791000000 - 30 * 86400, "trophy": "Taco",
         "description": "", "custom_image_url": "https://img/x.png",
         "from_user_avatar": "https://img/a.png"},
        {"id": 3, "create_date": 1791000000 - 30 * 86400 - 3600, "trophy": "Taco",
         "description": "", "custom_image_url": "https://img/x.png",
         "from_user_avatar": "https://img/a.png"},
        # three extra distinct cheers in the newest cluster -> folds after 3
        {"id": 4, "create_date": 1791000000 - 100, "trophy": "Holler",
         "description": "", "custom_image_url": "",
         "from_user_avatar": ""},
        {"id": 5, "create_date": 1791000000 - 200, "trophy": "Flower",
         "description": "", "custom_image_url": "",
         "from_user_avatar": ""},
        {"id": 6, "create_date": 1791000000 - 300, "trophy": "Bacon",
         "description": "", "custom_image_url": "",
         "from_user_avatar": ""},
    ],
}


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print(f"ok - {msg}")


out = "/tmp/render-check.html"
write_html(out, "SomeUser", grouped)
doc = open(out).read()
check("background" in doc and "#121212" in doc, "forced dark background present")
check("<script" not in doc.lower(), "zero JS in output")
check(doc.count("<details") == 3, "two clusters plus one nested Show-all")
check("<details open>" in doc, "newest cluster open")
check("to" in doc or "— 1 cheer" in doc, "cluster label with range/count")
check("https://img/x.png" in doc and "https://img/a.png" in doc, "images kept when present")
check(doc.count("<img") == 2, f"no img tags for empty urls (found {doc.count('<img')})")
check('id="giver-b-giver"' in doc, "card anchor id present")
check("<nav>" not in doc, "redundant leaderboard removed")
check('class="grid"' in doc, "responsive card grid present")
check("×2" in doc, "repeated cheers in one cluster collapse to xN")
check(doc.count(">Taco<") == 1, "collapsed repeat renders a single row")
check("Show all 1" in doc, "clusters fold cheer rows after 3 (hidden count)")

write_html("/tmp/render-empty.html", "Nobody", {})
empty = open("/tmp/render-empty.html").read()
check("No cheers found" in empty, "empty state message")

print("all render checks passed")
