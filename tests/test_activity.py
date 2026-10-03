"""bz/activity on real log shapes, in a temporary logs folder. python3 tests/test_activity.py"""
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bz import activity  # noqa: E402
import trader_notify  # noqa: E402

d = tempfile.mkdtemp()
T = time.time() - 600


def w(name, *rows):
    with open(os.path.join(d, f"{name}.jsonl"), "a") as f:
        for i, r in enumerate(rows):
            f.write(json.dumps({"ts": T + i, **r}) + "\n")


checks = 0
assert activity.timeline(d) == [] and activity.health(d)["alive"] is False; checks += 1   # empty folder: nothing, no heartbeat
# the real accept of t1230 and its settlement; an accept that never settled
w("trader_accept", {"tick": 1230, "offer": 18156, "maker": "t12", "source": "to_us", "surplus": 7.0, "cash_out": 70, "fee": 0, "gives": []},
  {"tick": 1300, "offer": 99, "maker": "mf1", "source": "board", "surplus": 3.0, "cash_out": 10, "fee": 2, "gives": []})
w("trader_settlement", {"tick": 1232, "offer": 18156, "found": True, "price": 70, "fee": 0, "realized_gain": 5.0},
  {"tick": 1302, "offer": 99, "found": False})
# counters: one accepted, one expired, one refused
w("trader_counter", {"tick": 1132, "incoming": 1, "counter": 16980, "maker": "t12", "price": 10, "their": 15, "clearing": 10, "body": {"give": {"cash": 10}}},
  {"tick": 1203, "incoming": 2, "counter": 17813, "maker": "t12", "price": 161, "their": 20, "clearing": 161, "body": {"give": {"assets": [1]}}})
w("trader_outcome", {"tick": 1133, "incoming": 1, "counter": 16980, "maker": "t12", "price": 10, "outcome": "accepted", "settled_price": 10},
  {"tick": 1214, "incoming": 2, "counter": 17813, "maker": "t12", "price": 161, "outcome": "expired"})
w("quotes", {"tick": 1229, "event": "posted", "offer": 18144, "side": "bid", "ref": "MAL-06", "price": 20, "value": 22.5},
  {"tick": 1230, "event": "filled", "offer": 18144, "side": "bid", "ref": "MAL-06", "price": 20, "settled": 20},
  {"tick": 1262, "event": "closed", "offer": 17776, "side": "bid", "ref": "MAL-09", "price": 56},
  {"tick": 1263, "event": "cancelled", "offer": 18510, "ref": "SAL-10", "why": "not wanted"},
  {"tick": 1263, "event": "plan", "want": []})
w("trader_blocked", {"tick": 1250, "offer": 5, "maker": "mf2", "reason": "budget", "surplus": 4.0})
w("trader_error", {"tick": 1251, "op": "post bid SAL-06 at 24", "error": "rate_limited"})
w("alerts", {"level": "FOREIGN", "text": "x"}, {"level": "STOP", "text": "loss"}, {"level": "PAGE", "text": "RET one card"}, {"level": "LEAD", "text": "y"})
items = activity.timeline(d)
st = {}
for i in items:
    st[i["status"]] = st.get(i["status"], 0) + 1
# ok: settlement 18156, counter accepted, quote filled · fail: not settled, error, STOP · blocked 1 · expired: counter, quote
assert st == {"info": 6, "ok": 3, "fail": 3, "blocked": 1, "expired": 2, "alert": 1}, st; checks += 1
assert not any("FOREIGN" in i["es"] or i["es"].startswith("LEAD") for i in items); checks += 1      # noise left out
assert any(i["status"] == "fail" and "NO aparece" in i["es"] for i in items); checks += 1
assert any(i["status"] == "ok" and "ganancia real +5.0" in i["es"] for i in items); checks += 1
assert any("vender por 161 P" in i["es"] for i in items) and any("comprar por 10 P" in i["es"] for i in items); checks += 1
assert [i["ts"] for i in items] == sorted(i["ts"] for i in items); checks += 1                     # oldest first
assert len({i["key"] for i in items}) == len(items); checks += 1                                    # one key each: the notifier needs it
assert activity.timeline(d, since_ts=time.time()) == []; checks += 1
v = activity.view(d, hours=1)
assert v["items"][0]["ts"] >= v["items"][-1]["ts"] and len(v["failures"]) == 4 and v["counts"]["ok"] == 3; checks += 1
# heartbeat: alive under 120 s, dead after
json.dump({"tick": 1445, "ts": time.time() - 30, "live": True, "acting": True, "cash": 351, "stopped": False}, open(os.path.join(d, "trader.heartbeat"), "w"))
h = activity.health(d)
assert h["alive"] and h["cash"] == 351 and not h["paused"]; checks += 1
assert activity.health(d, now=time.time() + 200)["alive"] is False; checks += 1
open(os.path.join(d, "trader.pause"), "w").close()
assert activity.health(d)["paused"] is True; checks += 1
# a broken line never breaks the timeline
with open(os.path.join(d, "quotes.jsonl"), "a") as f:
    f.write("{not json\n")
assert len(activity.timeline(d)) == len(items); checks += 1
# the digest text
txt = trader_notify.digest_text(items, {"alive": True, "cash": 351}, 15)
assert txt == "Last 15 min: 6 actions, 3 trades, 2 expired, 4 failures · cash 351 P · trader alive", txt
assert "NO HEARTBEAT (300 s)" in trader_notify.digest_text([], {"alive": False, "age": 300}, 15); checks += 2
# a hands-off card on a board under our value: one alert per offer, the rest of the signals stay out
w("signals", {"id": 18586, "ref": "RET-09", "price": 84, "venue": "rastro", "tick": 1272, "clears": True, "value": 177.1},
  {"id": 18586, "ref": "RET-09", "price": 84, "venue": "rastro", "tick": 1293, "clears": True, "value": 177.1},
  {"id": 18600, "ref": "SAL-06", "price": 18, "venue": "rastro", "tick": 1293, "clears": True, "value": 27.5},
  {"id": 18601, "ref": "RET-09", "price": 200, "venue": "rastro", "tick": 1293, "clears": False, "value": 177.1})
ho = [i for i in activity.timeline(d) if i["kind"] == "handsoff"]
assert len(ho) == 1 and ho[0]["status"] == "alert" and "84 P" in ho[0]["en"] and "Maru" in ho[0]["es"], ho; checks += 1
print(f"test_activity: {checks} checks passed")
