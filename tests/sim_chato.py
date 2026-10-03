"""Free simulation of a strict, impatient dealer like El Chato (no primas, no network).

What we know about him: patience 0.35 (Abuela 0.85), strictness 0.85, memory 0.9. Silver pack list 150, opening ask 188.
He buys uncommons and rares; his list price for an uncommon is 26.
Calibrated on 52 threads of other teams with him in the public feed (ticks 60-293) and our thread 294:
  - when he sells he mirrors our step: we go up 4, he comes down about 4 (`give` 0.5-1). The first `sticky` steps
    he only gives 1 (t04: our 60, 66, 72 got 96, 95, 92). Rare: ask 97, deals at 82-93, his ask reached 82 in a
    thread with no deal, so his limit is 82 or below. A step over 5 P only gets 1 P back: our thread 505
    (60, 71, 82, 93 against 97, 96, 95, "Subiste once, yo bajo uno"; it closed with no deal). Uncommon (list 26): ask 33, deals at 28-32, final at 28.
    Silver pack: ask 188, one deal at 181 (our steps of 10 got 0, 2, 5).
  - when he buys he barely moves: uncommon bid 13 in 14 of 15 threads, deals at 13, 13, 15 (thread 294: 13 against
    our 22, 18, 14: "Yo no me muevo si tú apenas te mueves")
  - he names his final offer after `patience` of our messages: 3 when he buys (thread 294), but 5-9 when he sells
    (rare threads ran 8-9 of their messages with no final word)
  - an insulting price costs him one unit of patience (buying: we offer under 60 % of his ask,
    selling: we ask over twice his bid). Not seen in the feed: t12 offered 5 and 7 for a rare and still bought at 89.
  - a repeated price ends the thread
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

    def __init__(self, side, start, limit, patience, give, final_in_text=False, sticky=0):
        self.side, self.start, self.limit, self.pat, self.give = side, start, limit, patience, give
        self.sticky = sticky  # his first `sticky` moves are 1 P, whatever our step
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
            step = abs(price - self.last)
            # a big jump only gets 1 P back (thread 505: "Subiste once, yo bajo uno")
            move = 1 if self.sticky > 0 or step > BIG_STEP else round(self.give * step)
            move = max(1, move) if self.give else 0
            self.sticky -= 1
            self.price = max(self.limit, self.price - move) if buy else min(self.limit, self.price + move)
        self.last = price
        self._post(self.price, final=self.msgs >= self.pat)


SELLING_PATIENCES, STICKY, BIG_STEP = (5, 7, 9), (1, 2), 5
SCENARIOS = {
    "buy a rare (LAV-09, worth 112 to us, list 77, ask 97)": dict(
        side="buy", start=97, leaving_price=93, value=112.0, baseline=None,  # no other dealer sells rares
        # his limit, patience, give, opening ask, sticky. The lowest deal in the feed is 82, his ask reached 82.
        worlds=[(lim, pat, g, 97, st) for lim in (74, 78, 82, 86) for pat in SELLING_PATIENCES for g in (0.5, 1.0)
                for st in STICKY],
        strategies={"today: open 38 (half list), 15% steps": (38, dict(step_frac=0.15)),
                    "open 60, pace over 6": (60, dict(patience=6)),
                    "open 60, pace over 8": (60, dict(patience=8)),
                    "open 65, pace over 6": (65, dict(patience=6)),
                    "open 70, pace over 6": (70, dict(patience=6)),
                    "open 75, pace over 4": (75, dict(patience=4)),
                    "open 60, pace over 3 (thread 505)": (60, dict(patience=3)),
                    "open 66, pace over 8": (66, dict(patience=8)),
                    "open 70, pace over 8": (70, dict(patience=8)),
                    "open 74, pace over 6": (74, dict(patience=6)),
                    "open 78, pace over 4": (78, dict(patience=4))}),
    "buy the silver pack": dict(
        side="buy", start=188, leaving_price=122, value=135.9, baseline=None,
        # his limit, patience, give, opening ask, sticky. One deal in the feed, at 181: no limit reaches 122.
        worlds=[(lim, pat, g, 188, st) for lim in (165, 172, 181) for pat in SELLING_PATIENCES for g in (0.5, 1.0)
                for st in STICKY],
        strategies={"open 75, pace over 3": (75, dict(patience=3)),
                    "open 95, pace over 6": (95, dict(patience=6))}),
    "buy an uncommon (LAV-08, worth 40 to us, Abuela sells it at list 25)": dict(
        side="buy", start=None, leaving_price=26, value=40.0, baseline=21,  # Abuela sold us LAV-08 at 21
        # his limit, patience, give, opening ask, sticky. Feed: ask 33, deals 28-32, final at 28.
        worlds=[(lim, pat, g, 33, st) for lim in (26, 27, 28) for pat in SELLING_PATIENCES for g in (0.5, 1.0)
                for st in STICKY],
        strategies={"today: open 13, 15% steps": (13, dict(step_frac=0.15)),
                    "open 13, pace over 6": (13, dict(patience=6)),
                    "open 20, pace over 6": (20, dict(patience=6))}),
    "sell a spare uncommon": dict(
        side="sell", start=None, leaving_price=13, value=5.6, baseline=13,  # our floor is Abuela's bid
        # his limit, patience, give, opening bid. Feed: bid 13, deals 13, 13, 15. give 0: he does not move at all.
        worlds=[(lim, pat, g, 13) for lim in (13, 14, 15) for pat in (2, 3, 4) for g in (0, 0.25)],
        strategies={"today: open 31, 15% steps": (31, dict(step_frac=0.15)),
                    "open 22, pace over 2": (22, dict(patience=2)),
                    "open 18, pace over 2": (18, dict(patience=2)),
                    "open 16, pace over 2": (16, dict(patience=2))}),
}


def play(sc, opening, kw, world, final_in_text=False):
    if sc["side"] == "buy":
        limit, patience, give, *rest = world  # a world may carry its own opening ask and sticky moves
        d = SimChato("buy", rest[0] if rest else sc["start"], limit, patience, give, final_in_text,
                     sticky=rest[1] if len(rest) > 1 else 0)
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
    return (price - d.start) / (d.limit - d.start) if d.limit != d.start else 1.0  # no range: he never moves


if __name__ == "__main__":
    for title, sc in SCENARIOS.items():
        buy = sc["side"] == "buy"
        reachable = [w for w in sc["worlds"] if (w[0] <= sc["leaving_price"] if buy else w[0] >= sc["leaving_price"])]
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
