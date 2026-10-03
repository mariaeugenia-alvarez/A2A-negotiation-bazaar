"""haggle() driven by bz/predict.advisor against fake dealers that follow the fitted models, through the same API
shapes the server uses (messages with offers). No network, no primas. python3 tests/test_haggle_model.py"""
import contextlib
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bz.log as L  # noqa: E402
L.LOG_DIR = tempfile.mkdtemp()
from bz.haggle import haggle  # noqa: E402
from bz.predict import abuela_next, advisor, chato_allowance  # noqa: E402


class FakeDealer:
    """rule(ask, k, step) -> her next price. side is OUR side. She answers each of our prices once, on the next tick."""

    def __init__(self, name, side, opening, limit, patience, rule):
        self.name, self.side, self.limit, self.pat, self.rule = name, side, limit, patience, rule
        self.ask, self.k, self.last, self.pending = opening, 0, None, None
        self.status, self.msgs, self.offers, self.deal = "open", [], [], None
        self._post(opening)

    def _post(self, p, final=False):
        for o in self.offers:
            o["status"] = "cancelled"
        leg = {"cash": p}
        o = {"id": len(self.offers) + 1, "maker": self.name, "status": "open", "final": final,
             "want": leg if self.side == "buy" else {}, "give": leg if self.side == "sell" else {}}
        self.offers.append(o)
        self.msgs.append({"id": len(self.msgs) + 1, "sender": self.name, "text": "", "offer": o})

    def _ours(self, p):
        leg = {"cash": p}
        self.msgs.append({"id": len(self.msgs) + 1, "sender": "t09", "text": "", "offer": {
            "give": leg if self.side == "buy" else {}, "want": leg if self.side == "sell" else {}}})

    def wait_tick(self):
        if self.status == "accepting":
            self.status = "deal"
            return
        if self.pending is None or self.status != "open":
            return
        price, self.pending = self.pending, None
        buy = self.side == "buy"
        if self.offers[-1]["final"]:  # we did not take her last word
            self.status = "closed"
            return
        step = None if self.last is None else max(0, (price - self.last) if buy else (self.last - price))
        self.last = price
        self.k += 1
        nxt = self.rule(self.ask, self.k, step)
        if (price >= nxt and price >= self.limit) if buy else (price <= nxt and price <= self.limit):
            self.status, self.deal = "deal", price  # she takes our offer (it settles on this tick)
            return
        self.ask = nxt
        self._post(nxt, final=self.k >= self.pat or nxt == self.limit)

    def my_threads(self, status=None): return {"threads": []}
    def open_thread(self, who, topic=None): return {"id": 7}
    def close_thread(self, tid): self.status = "closed"
    def accept(self, oid): self.status, self.deal = "accepting", self.ask
    def thread(self, tid): return {"id": 7, "status": self.status, "closed_reason": None,
                                   "standing_offers": [o for o in self.offers if o["status"] == "open"],
                                   "messages": list(self.msgs)}

    def say(self, tid, text, price):
        self._ours(price)
        self.pending = price


def abuela(limit, patience, opening=30, side="buy"):
    first = [True]

    def rule(ask, k, step):
        if step == 0:
            return ask
        p = abuela_next(ask, limit, side, first=first[0])
        first[0] = False
        return p
    return FakeDealer("abuela", side, opening, limit, patience, rule)


def chato(limit, patience, a=0.48, b=0.5, opening=97):
    state = {"conceded": 0}

    def rule(ask, k, step):
        room = chato_allowance(k, a, b) - state["conceded"]
        give = max(0, room if step is None else min(step, room))
        nxt = max(limit, ask - give)
        state["conceded"] += ask - nxt
        return nxt
    return FakeDealer("chato", "buy", opening, limit, patience, rule)


def run(d, kind, opening, our_limit, model=True, **kw):
    adv = advisor(d.name, d.side, kind, our_limit, threads=[]) if model else None
    with contextlib.redirect_stdout(io.StringIO()):
        r = haggle(d, d.name, {}, d.side, opening, our_limit, advise=adv, **kw)
    assert len(set(r["ours"])) == len(r["ours"]), ("a price was repeated", r["ours"])
    return r


checks = 0
# 1. Abuela, packs: every limit 19-24 and patience 4-7. The model never pays more than the old pacing, and with
#    patience 7 it lands within 1 P of her limit.
worse = better = 0
for limit in range(19, 25):
    for pat in range(4, 8):
        m = run(abuela(limit, pat), "buy:pack:sobre_barrio", 15, 28)
        o = run(abuela(limit, pat), "buy:pack:sobre_barrio", 15, 28, model=False, patience=6)
        assert m["status"] == "deal" and limit <= m["price"], (limit, pat, m)
        if pat == 7:
            assert m["price"] <= limit + 1, (limit, pat, m)
        worse += o["status"] == "deal" and m["price"] > o["price"]
        better += o["status"] != "deal" or m["price"] < o["price"]
assert worse == 0 and better > 0, (worse, better); checks += 1

# 2. Abuela buys our uncommon (opening bid 12, limit 14-17): the model sells at her limit or within 1 P.
for limit in range(14, 18):
    m = run(abuela(limit, 7, opening=12, side="sell"), "sell:uncommon", 25, 13)
    assert m["status"] == "deal" and limit - 1 <= m["price"] <= limit, (limit, m)
checks += 1

# 3. El Chato, a rare: his limit 74-86, patience 5-9. Never worse than "open 60, steps of 4" (thread 526).
worse = 0
total_m = total_o = 0
for limit in (74, 78, 82, 86):
    for pat in (5, 7, 9):
        m = run(chato(limit, pat), "buy:rare", 60, 93)
        o = run(chato(limit, pat), "buy:rare", 60, 93, model=False, patience=8)
        assert m["status"] == "deal", (limit, pat, m)
        total_m += m["price"]
        total_o += o["price"] if o["status"] == "deal" else 93
        worse += o["status"] == "deal" and m["price"] > o["price"] + 1
assert worse == 0 and total_m <= total_o, (worse, total_m, total_o); checks += 1

# 4. Pilar (linear): bid 16, 1 P per move after her first answer, final after 6 answers. The model gets her final
#    (21) where big steps of 7 P stop early at 17-18 (t13's threads 666 and 701).
def pilar(patience, opening=16, limit=30):
    def rule(ask, k, step):
        return ask if k == 1 or not step else min(limit, ask + 1)
    return FakeDealer("pilar", "sell", opening, limit, patience, rule)


m = run(pilar(6), "sell:uncommon", 30, 15)
big = run(pilar(6), "sell:uncommon", 49, 15, model=False, step_frac=0.4)
assert m["status"] == "deal" and m["price"] == 21 and (big["price"] or 0) < 21, (m, big); checks += 1

# 5. A dealer with no model and no data: advisor() says so, and haggle() keeps its own pacing.
assert advisor("nuevo", "sell", "sell:uncommon", 13, threads=[]) is None; checks += 1

print(f"ok: {checks} checks (Chato rare: model {total_m / 12:.1f} avg vs {total_o / 12:.1f} with the old pacing)")
