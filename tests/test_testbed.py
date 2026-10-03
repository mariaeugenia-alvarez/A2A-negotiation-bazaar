"""bz/testbed.py: the scores mean what they say, and a run never writes into logs/.

Run: python3 tests/test_testbed.py
"""
import os
import sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tempfile

from bz import learn, log, testbed

checks = 0


def check(cond, what):
    global checks
    assert cond, what
    checks += 1


# the simulated dealers keep to their own rules
d = testbed.Midpoint("abuela", "buy", 100, 70, 6, "buy:testbed")
d.say(1, "", 50)
check(d.price == 85, f"midpoint: half the way to 70 on the first answer, got {d.price}")
d = testbed.Boulware("chato", "buy", 100, 70, 8, "buy:testbed")
d.say(1, "", 50); d.say(1, "", 60)
check(d.price >= 70 and d.conceded <= 10, "boulware: never past his limit nor more than our step")
d = testbed.Immobile("pilar", "sell", 40, 40, 4, "sell:testbed")
d.say(1, "", 60)
check(d.price == 40, "immobile: never moves")

# one game: a deal inside the ZOPA scores (R - price) / (R - L)
def footprint():
    """What haggle() would leave in logs/: the haggles log and the transcripts."""
    h = os.path.join(log.LOG_DIR, "haggles.jsonl")
    return (os.path.getsize(h) if os.path.exists(h) else 0,
            sorted(os.listdir(learn.THREAD_DIR)) if os.path.isdir(learn.THREAD_DIR) else [])


before = footprint()
with testbed._sandbox():  # play() alone is not sandboxed: run() and cached() are
    g = testbed.play(testbed.CONFIGS[0], "midpoint", ("buy", 100, 76, 6, 90))
    g2 = testbed.play(testbed.CONFIGS[0], "midpoint", ("buy", 100, 94, 6, 80))
check(g["zopa"] and g["deal"] and abs(g["se"] - (90 - g["price"]) / 14) < 1e-9, f"SE+ of one game: {g}")
check(not g2["zopa"] and g2["se"] is None and not g2["deal"], f"no ZOPA, no deal: {g2}")

# the whole run, written somewhere else than logs/
saved = log.LOG_DIR, learn.THREAD_DIR
path = os.path.join(tempfile.mkdtemp(), "testbed.json")
data = testbed.cached(path)
check((log.LOG_DIR, learn.THREAD_DIR) == saved, "the sandbox puts the log folders back")
check(footprint() == before, "no haggle or transcript written under logs/")
check(testbed.cached(path) == data, "a second call reads the cache")
for r in data["configs"]:
    for scope, m in [("all", r["all"]), *r["by_family"].items()]:
        check(m["viol"]["v"] == 0, f"{r['label']} / {scope}: a deal past our reserve")
        check(m["fagr"] is None or m["fagr"]["v"] == 0, f"{r['label']} / {scope}: a deal without a ZOPA")
        se, agr, cse = m["se"], m["agr"], m["cse"]
        check(se["lo"] <= se["v"] <= se["hi"], f"{r['label']} / {scope}: SE+ outside its own interval")
        check(abs(se["v"] - agr["v"] * (cse["v"] if cse else 0)) < 1e-3, f"{r['label']} / {scope}: SE+ != AGR+ x CSE+")
check(sum(r["floor"] for r in data["configs"]) == 1, "exactly one floor (fixed 30 %)")
print(f"test_testbed: {checks} checks passed")
