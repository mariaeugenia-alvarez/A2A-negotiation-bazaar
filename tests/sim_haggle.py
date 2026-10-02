import os
import sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import os, tempfile
import bz.log as L; L.LOG_DIR = tempfile.mkdtemp()
from bz.haggle import haggle

class FakeDealer:
    """Buy side: ask starts 30, secret floor 19; concedes half our last step; final after patience."""
    def __init__(s, side="buy", start=30, floor=19, patience=12):
        s.side, s.ask, s.floor, s.pat, s.msgs, s.status, s.offers, s.last_ours = side, start, floor, patience, 0, "open", [], None
        s._post(start)
    def _post(s, p, final=False):
        for o in s.offers: o["status"] = "withdrawn"
        leg = {"cash": p}
        s.offers.append({"id": len(s.offers)+1, "maker": "abuela", "status": "open", "final": final,
                         "want": leg if s.side == "buy" else {}, "give": leg if s.side == "sell" else {}})
    def wait_tick(s):
        if s.status == "accepting": s.status = "deal"
    def my_threads(s, status=None): return {"threads": []}
    def open_thread(s, w, topic=None): return {"id": 7}
    def thread(s, tid): return {"status": s.status, "standing_offers": s.offers}
    def close_thread(s, tid): s.status = "closed"
    def accept(s, oid): s.status = "accepting"
    def say(s, tid, text, price):
        s.msgs += 1
        buy = s.side == "buy"
        if (buy and price >= s.ask) or (not buy and price <= s.ask): s.status = "accepting"; return
        if s.last_ours is not None:
            step = abs(price - s.last_ours)
            s.ask = max(s.floor, s.ask - max(1, step // 2)) if buy else min(s.floor, s.ask + max(1, step // 2))
        s.last_ours = price
        s._post(s.ask, final=s.msgs >= s.pat)

for args in [dict(side="buy", start=30, floor=19), dict(side="buy", start=30, floor=25, patience=6),
             dict(side="sell", start=4, floor=8)]:
    d = FakeDealer(**args)
    lim = 23 if args["side"] == "buy" else 3
    op = 13 if args["side"] == "buy" else 12
    r = haggle(d, "abuela", {}, args["side"], op, lim)
    print(args, "->", r["status"], r["price"], r["reason"], "ours", r["ours"], "hers", r["theirs"], "msgs", d.msgs, "\n")

print("--- learned")
import bz.learn as LR; LR.THREAD_DIR=os.path.join(L.LOG_DIR, "threads")
for args, kw in [(dict(side="sell", start=12, floor=13, patience=5), dict(target=13, accept_at=13, patience=5)),
                 (dict(side="sell", start=12, floor=15, patience=8), dict(target=13, accept_at=13, patience=5)),
                 (dict(side="buy", start=30, floor=19), dict(target=21, accept_at=19, patience=6))]:
    d = FakeDealer(**args); d.thread_full = None
    lim = 23 if args["side"] == "buy" else 3
    op = 13 if args["side"] == "buy" else 30
    r = haggle(d, "abuela", {}, args["side"], op, lim, **kw)
    print(args, kw, "->", r["status"], r["price"], r["reason"], "ours", r["ours"], "hers", r["theirs"])
