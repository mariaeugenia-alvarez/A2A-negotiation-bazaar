"""Free simulation of a strict, impatient dealer like El Chato (no primas, no network).

What we know about him: patience 0.35 (Abuela 0.85), strictness 0.85, memory 0.9. Silver pack list 150, opening ask 188.
He buys uncommons and rares; his list price for an uncommon is 26.
What we assume, because we have no conversation with him yet:
  - he moves `give` times each of our steps (Abuela moved about 1.5 P per 1 P we conceded, threads 66 and 108)
  - he names his final offer after `patience` of our messages
  - an insulting price costs him one unit of patience (buying: we offer under 60 % of his ask,
    selling: we ask over twice his bid)
  - a repeated price ends the thread
  - his secret limit: for the pack, 73-81 % of list (Abuela's pattern), so about 110-120 of 150.
    For an uncommon bid, a ceiling of 12-20 (thread 294: he bid 13 and did not move for our 22, 18, 14).
    For an uncommon he sells (list 26): an ask of 30-33 and a limit of 17-24, from Abuela's pack pattern.
  - with `final_in_text` his last word comes only in words ("Lo tomas o te lo quedas"), as in thread 294

The dealer-ladder score is the share of his range we capture:
  buying  (ask - price) / (ask - his limit)        selling  (price - bid) / (his limit - bid)

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


class SimChato:
    """side is OUR side. buy: his price is an ask that falls to `limit`. sell: his price is a bid that rises to `limit`."""

    def __init__(self, side, start, limit, patience, give, final_in_text=False):
        self.side, self.start, self.limit, self.pat, self.give = side, start, limit, patience, give
        self.final_in_text, self.words = final_in_text, ""
        self.price, self.msgs, self.status, self.reason, self.offers, self.last = start, 0, "open", None, [], None
        self._post(start)

    def _post(self, p, final=False):
        for o in self.offers:
            o["status"] = "withdrawn"
        leg = {"cash": p}
        self.words = "Lo tomas o te lo quedas." if final and self.final_in_text else ""
        final = final and not self.final_in_text
        self.offers.append({"id": len(self.offers) + 1, "maker": "chato", "status": "open", "final": final,
                            "want": leg if self.side == "buy" else {}, "give": leg if self.side == "sell" else {}})

    def wait_tick(self):
        if self.status == "accepting":
            self.status = "deal"

    def my_threads(self, status=None): return {"threads": []}
    def open_thread(self, who, topic=None): return {"id": 7}
    def thread(self, tid): return {"id": 7, "status": self.status, "closed_reason": self.reason, "standing_offers": self.offers,
                                  "messages": [{"sender": "chato", "text": self.words}]}
    def close_thread(self, tid): self.status = "closed"
    def accept(self, oid): self.status = "accepting"

    def say(self, tid, text, price):
        if self.status != "open":
            return
        buy = self.side == "buy"
        self.msgs += 1
        if price == self.last:  # the same price again is spam: he stops talking to us
            self.status, self.reason = "closed", "cooloff"
            return
        if (price >= self.price) if buy else (price <= self.price):
            self.status = "accepting"
            return
        if self.offers[-1]["final"] or self.words:  # we did not take his last word: he walks
            self.status, self.reason = "closed", "walked"
            return
        if (price < 0.6 * self.price) if buy else (price > 2.0 * self.price):
            self.pat -= 1
        moved = self.last is not None and ((price > self.last) if buy else (price < self.last))
        if moved:
            move = max(1, round(self.give * abs(price - self.last)))
            self.price = max(self.limit, self.price - move) if buy else min(self.limit, self.price + move)
        self.last = price
        self._post(self.price, final=self.msgs >= self.pat)


GIVES, PATIENCES = (1.0, 1.5, 2.5), (2, 3, 4, 6)
SCENARIOS = {
    "buy the silver pack": dict(
        side="buy", start=188, leaving_price=122, value=135.9, baseline=None,
        # his limit, patience, give. Two limits sit above our leaving price: no deal is possible there.
        worlds=list(itertools.product((105, 110, 115, 120, 130, 150), PATIENCES, GIVES)),
        strategies={"today: open 75, 15% steps": (75, dict(step_frac=0.15)),
                    "open 75, pace over 3": (75, dict(patience=3)),
                    "open 95, pace over 3": (95, dict(patience=3)),
                    "open 75, pace over 2": (75, dict(patience=2))}),
    "buy an uncommon (LAV-08, worth 40 to us, Abuela sells it at list 25)": dict(
        side="buy", start=None, leaving_price=26, value=40.0, baseline=25,  # we never pay above his list price 26
        # his limit, patience, give, opening ask. A limit of 28 is above our leaving price.
        worlds=[(lim, pat, g, ask) for lim in (17, 19, 21, 24, 28) for pat in PATIENCES for g in GIVES for ask in (30, 33)],
        strategies={"today: open 13, 15% steps": (13, dict(step_frac=0.15)),
                    "open 13, pace over 3": (13, dict(patience=3)),
                    "open 17, pace over 3": (17, dict(patience=3)),
                    "open 20, pace over 3": (20, dict(patience=3)),
                    "open 20, pace over 2": (20, dict(patience=2))}),
    "sell a spare uncommon": dict(
        side="sell", start=None, leaving_price=13, value=5.6, baseline=13,  # our floor is Abuela's bid
        # his limit, patience, give, opening bid. A limit of 12 cannot beat Abuela's 13.
        worlds=[(lim, pat, g, bid) for lim in (12, 14, 16, 20) for pat in PATIENCES for g in GIVES for bid in (9, 12)],
        strategies={"today: open 31, 15% steps": (31, dict(step_frac=0.15)),
                    "open 31, pace over 2": (31, dict(patience=2)),
                    "open 22, pace over 2": (22, dict(patience=2)),
                    "open 18, pace over 2": (18, dict(patience=2)),
                    "open 18, pace over 3": (18, dict(patience=3))}),
}


def play(sc, opening, kw, world, final_in_text=False):
    if sc["side"] == "buy":
        limit, patience, give, *start = world  # a world may carry its own opening ask
        d = SimChato("buy", start[0] if start else sc["start"], limit, patience, give, final_in_text)
    else:
        limit, patience, give, bid = world
        d = SimChato("sell", bid, limit, patience, give, final_in_text)
    with contextlib.redirect_stdout(io.StringIO()):
        r = haggle(d, "chato", {}, sc["side"], opening, sc["leaving_price"], **kw)
    assert len(set(r["ours"])) == len(r["ours"]), "a price was repeated"
    p = r["price"]
    assert p is None or (p <= sc["leaving_price"] if sc["side"] == "buy" else p >= sc["leaving_price"]), "crossed the leaving price"
    return r, d


def share(sc, d, price):
    if sc["side"] == "buy":
        return (d.start - price) / (d.start - d.limit)
    return (price - d.start) / (d.limit - d.start)


if __name__ == "__main__":
    for title, sc in SCENARIOS.items():
        buy = sc["side"] == "buy"
        reachable = [w for w in sc["worlds"] if (w[0] <= sc["leaving_price"] if buy else w[0] > sc["leaving_price"])]
        print(f"== {title}: {len(sc['worlds'])} worlds, {len(reachable)} where a deal can beat our leaving price {sc['leaving_price']}")
        print(f"{'strategy':28} {'deals':>9} {'avg price':>10} {'range share':>12} {'gain':>8} {'vs fallback':>12}")
        for name, (opening, kw) in sc["strategies"].items():
            prices, shares, vs = [], [], []
            for w in sc["worlds"]:
                r, d = play(sc, opening, kw, w)
                base = sc["baseline"]
                if r["status"] == "deal":
                    prices.append(r["price"])
                    shares.append(share(sc, d, r["price"]))
                if base is not None:  # no deal with him: we trade with the fallback dealer at `base`
                    got = r["price"] if r["status"] == "deal" else base
                    vs.append(base - got if buy else got - base)
            n = len(prices)
            fb = f"{sum(vs) / len(vs):>+12.2f}" if vs else f"{'-':>12}"
            if not n:
                print(f"{name:28} {n:>4}/{len(reachable):<4} {'-':>10} {'-':>12} {'-':>8} {fb}")
                continue
            avg = sum(prices) / n
            gain = sc["value"] - avg if buy else avg - sc["leaving_price"]  # buy: value minus price. sell: price above our floor
            print(f"{name:28} {n:>4}/{len(reachable):<4} {avg:>10.1f} {sum(shares) / n:>12.2f} {gain:>8.1f} {fb}")
        print()
    # fix 3: when his last word comes only in words, we must do exactly what we do when the flag is set
    same = total = 0
    for sc in SCENARIOS.values():
        for opening, kw in sc["strategies"].values():
            for w in sc["worlds"]:
                a, _ = play(sc, opening, kw, w)
                b, _ = play(sc, opening, kw, w, final_in_text=True)
                total += 1
                same += a["price"] == b["price"]  # same deal at the same price, or no deal in both
    print(f"final named in words only: same deals and prices as with the flag in {same}/{total} games")
    assert same == total
