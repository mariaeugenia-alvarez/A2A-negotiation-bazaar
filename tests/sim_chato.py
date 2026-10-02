"""Free simulation of a strict, impatient dealer like El Chato (no primas, no network).

What we know about him: patience 0.35 (Abuela 0.85), strictness 0.85, memory 0.9; silver pack list 150, opening ask 188.
What we assume, because we have no conversation with him yet: he moves `give` times each of our steps (Abuela moved about 1.5 P per 1 P we conceded, threads 66 and 108), an insulting
price costs him a unit of patience, a repeated price ends the thread, and he names his final offer after `patience`
of our messages. Change the grid below when real threads disagree.

The dealer-ladder score is the share of his range we capture: (ask - price) / (ask - his secret limit).
Run: python3 tests/sim_chato.py
"""
import contextlib
import io
import itertools
import os
import sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tempfile

import bz.log as L; L.LOG_DIR = tempfile.mkdtemp()
from bz.haggle import haggle

START, LEAVING_PRICE, VALUE_TO_US = 188, 122, 135.9  # his opening ask, our leaving price, what the pack is worth to us


class SimChato:
    def __init__(self, floor, patience, give, insult=0.6):
        self.floor, self.pat, self.give, self.insult = floor, patience, give, insult
        self.ask, self.msgs, self.status, self.reason, self.offers, self.last = START, 0, "open", None, [], None
        self._post(START)

    def _post(self, p, final=False):
        for o in self.offers:
            o["status"] = "withdrawn"
        self.offers.append({"id": len(self.offers) + 1, "maker": "chato", "status": "open", "final": final,
                            "want": {"cash": p}, "give": {}})

    def wait_tick(self):
        if self.status == "accepting":
            self.status = "deal"

    def my_threads(self, status=None): return {"threads": []}
    def open_thread(self, who, topic=None): return {"id": 7}
    def thread(self, tid): return {"id": 7, "status": self.status, "closed_reason": self.reason, "standing_offers": self.offers, "messages": []}
    def close_thread(self, tid): self.status = "closed"
    def accept(self, oid): self.status = "accepting"

    def say(self, tid, text, price):
        if self.status != "open":
            return
        self.msgs += 1
        if price == self.last:  # the same price again is spam: he stops talking to us
            self.status, self.reason = "closed", "cooloff"
            return
        if price >= self.ask:
            self.status = "accepting"
            return
        if self.offers[-1]["final"]:  # we did not take his last word: he walks
            self.status, self.reason = "closed", "walked"
            return
        if price < self.insult * self.ask:
            self.pat -= 1
        if self.last is not None and price > self.last:
            self.ask = max(self.floor, self.ask - max(1, round(self.give * (price - self.last))))
        self.last = price
        self._post(self.ask, final=self.msgs >= self.pat)


STRATEGIES = {  # name -> (opening, haggle keyword arguments)
    "today: open 75, 15% steps": (75, dict(step_frac=0.15)),
    "open 75, pace over 3": (75, dict(patience=3)),
    "open 95, pace over 3": (95, dict(patience=3)),
    "open 110, pace over 3": (110, dict(patience=3)),
    "open 95, pace over 4": (95, dict(patience=4)),
    "open 75, pace over 2": (75, dict(patience=2)),
    "open 95, pace over 2": (95, dict(patience=2)),
}
# His limit: Abuela's best price was 73-81 % of her list price (19-21 of 26), so for his 150 we try 110-120,
# plus two limits above our leaving price. Patience: 2 to 6 of our messages.
WORLDS = list(itertools.product((105, 110, 115, 120, 130, 150), (2, 3, 4, 6), (1.0, 1.5, 2.5)))  # floor, patience, give


def play(opening, kw, world):
    floor, patience, give = world
    d = SimChato(floor, patience, give)
    with contextlib.redirect_stdout(io.StringIO()):
        r = haggle(d, "chato", {}, "buy", opening, LEAVING_PRICE, **kw)
    assert len(set(r["ours"])) == len(r["ours"]), "a price was repeated"
    assert r["price"] is None or r["price"] <= LEAVING_PRICE, "paid above the leaving price"
    return r


if __name__ == "__main__":
    reachable = [w for w in WORLDS if w[0] <= LEAVING_PRICE]
    print(f"{len(WORLDS)} worlds, {len(reachable)} where his limit is within our leaving price {LEAVING_PRICE}\n")
    print(f"{'strategy':28} {'deals':>9} {'avg price':>10} {'range share':>12} {'our gain':>9}")
    for name, (opening, kw) in STRATEGIES.items():
        deals, shares = [], []
        for w in reachable:
            r = play(opening, kw, w)
            if r["status"] == "deal":
                deals.append(r["price"])
                shares.append((START - r["price"]) / (START - w[0]))
        n = len(deals)
        if not n:
            print(f"{name:28} {n:>4}/{len(reachable):<4} {'-':>10} {'-':>12} {'-':>9}")
            continue
        print(f"{name:28} {n:>4}/{len(reachable):<4} {sum(deals) / n:>10.1f} {sum(shares) / n:>12.2f} "
              f"{VALUE_TO_US - sum(deals) / n:>9.1f}")
