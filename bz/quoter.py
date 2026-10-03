"""Keeps our standing quotes (bz/quotes.py) open on the market, and watches them with bz/guard.py. Used by trader.py.

It touches ONLY the quotes it posted itself (their ids are in logs/quotes.jsonl, so a restart remembers them).
Any other open offer on our key is "foreign": it is counted (cash it promises, cards it asks for), reported once,
and never cancelled. Every action and every alert goes to logs/quotes.jsonl and logs/alerts.jsonl.
"""
import json
import os
import subprocess

from bazaar_sdk import BazaarError

from . import log
from .guard import Guard, CASH_FLOOR
from .quotes import plan
from .trade import wanted_refs

QUOTES = os.path.join(log.LOG_DIR, "quotes.jsonl")
VENUE = "rastro"        # 18 of 24 team trades on Saturday settled there
EXPIRES = 120           # ticks a quote stays up (the Day 2 hints suggest a long life)
REPRICE_AFTER = 20      # ticks before a quote may be cancelled to change its price
MAX_POST_PER_TICK = 4   # the game allows 12 new listings per tick; we leave room for counters
MAX_OPEN = 26           # the game allows 30 open offers per team


def load_own() -> dict:
    """offer id -> quote, for quotes we posted and have not seen close."""
    own = {}
    if os.path.exists(QUOTES):
        for line in open(QUOTES, encoding="utf-8"):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("event") == "posted":
                own[e["offer"]] = e
            elif e.get("event") in ("cancelled", "filled", "closed"):
                own.pop(e.get("offer"), None)
    return own


class Quoter:
    def __init__(self, b, budget: int, notify: bool = False):
        self.b, self.budget, self.notify = b, budget, notify
        self.own = load_own()
        self.guard = Guard()
        self.told = set()  # alerts already given once

    def alert(self, level: str, text: str, once: str = None) -> None:
        if once:
            if once in self.told:
                return
            self.told.add(once)
        log.event("alerts", level=level, text=text)
        log.say(f"ALERT {level}: {text}")
        if self.notify and level in ("STOP", "WIN", "PAGE", "FOREIGN"):
            try:
                subprocess.run(["osascript", "-e", f'display notification "{text[:180]}" with title "Bazaar {level}"'],
                               timeout=3, check=False)
            except (OSError, subprocess.SubprocessError):
                pass

    def step(self, tick: int, st, mine: list, values, best_bid, settlement_for, pause_file: str, acting: bool) -> None:
        me_id, cash = st.me["id"], st.cash
        open_ours = {o["id"]: o for o in mine if o.get("maker") == me_id and o.get("status") == "open"}
        # 1. quotes that closed since last tick: filled (the feed has the settlement) or expired
        for oid in [i for i in self.own if i not in open_ours]:
            q = self.own.pop(oid)
            hit = settlement_for(self.b, me_id, {q["ref"]}, q["tick"])
            event = "filled" if hit else "closed"
            log.event("quotes", event=event, offer=oid, side=q["side"], ref=q["ref"], price=q["price"], value=q["value"],
                      settled=(hit or {}).get("price"), tick=tick)
            if hit:
                self.guard.fill(tick, q["ref"], q["side"], int(hit.get("price") or q["price"]), q["value"])
        self.guard.score((st.me.get("score") or {}).get("neg_points"))
        # 2. foreign offers on our key: count them, report them once, never touch them
        foreign = [o for i, o in open_ours.items() if i not in self.own and not o.get("to")]
        for o in foreign:
            gives = [a.get("ref") for a in (o.get("give") or {}).get("assets") or []]
            self.alert("FOREIGN", f"offer {o['id']} on our key not posted by the quoter: gives {gives or o['give'].get('cash')}"
                       f" for {wanted_refs(o) or o['want'].get('cash')}", once=f"foreign{o['id']}")
        foreign_cash = sum(int((o.get("give") or {}).get("cash") or 0) for o in foreign)
        foreign_refs = {r for o in foreign for r in wanted_refs(o)}
        foreign_assets = {a["id"] for o in open_ours.values() if o["id"] not in self.own
                          for a in (o.get("give") or {}).get("assets") or []}
        # 3. pages one card from complete: a person decides the last card (its value includes the whole page bonus)
        for p in st.me["album"]["pages"]:
            if not p["complete"] and p["of"] - p["have"] == 1:
                self.alert("PAGE", f"{p['set']} page is one card from complete: decide the last card by hand",
                           once=f"page{p['set']}{p['have']}")
        # 4. what we want open now
        cat = st.catalog
        book = {r: v["book"] for r, v in cat["rarities"].items()}
        rarity = {c["id"]: c["rarity"] for s in cat["sets"] for c in s["cards"]}
        others = {}
        for ref in {r for refs in st.missing().values() for r in refs}:
            bb = best_bid(ref)
            if bb:
                others[ref] = bb
        spares = [a for a in st.spares() if a["id"] not in foreign_assets]
        budget = max(0, min(self.budget, cash - foreign_cash - CASH_FLOOR)) if self.guard.may_bid(cash) else 0
        want = plan(st.missing(), st.me["album"]["pages"], spares, values.gain, rarity.get, book, others,
                    foreign_refs, budget)
        key = lambda q: (q["side"], q.get("asset") or q["ref"])  # noqa: E731
        wanted = {key(q): q for q in want}
        # 5. stoppers: a stop cancels every quote we own and pauses the trader until a person looks
        for level, text in self.guard.drain():
            self.alert(level, text)
        if self.guard.stopped:
            if acting:
                for oid in list(self.own):
                    self._cancel(oid, tick, "guard stop")
                with open(pause_file, "w", encoding="utf-8") as f:
                    f.write(self.guard.reason + "\n")
            return
        for oid, q in list(self.own.items()):  # alerts on quotes that wait too long or are outbid
            if tick - q["tick"] >= 100:
                self.alert("STALE", f"{q['side']} {q['ref']} at {q['price']} open for {tick - q['tick']} ticks",
                           once=f"stale{oid}")
            if q["side"] == "bid" and best_bid(q["ref"]) > q["price"]:
                self.alert("OUTBID", f"another team bids {best_bid(q['ref'])} for {q['ref']}, we bid {q['price']}",
                           once=f"outbid{oid}{best_bid(q['ref'])}")
        if not acting:
            log.event("quotes", event="plan", tick=tick, budget=budget, want=want)
            return
        # 6. cancel ours that are no longer wanted, or whose price changed (after a while: no churn)
        for oid, q in list(self.own.items()):
            w = wanted.get(key(q))
            if w is None or (w["price"] != q["price"] and tick - q["tick"] >= REPRICE_AFTER):
                self._cancel(oid, tick, "not wanted" if w is None else f"reprice {q['price']} -> {w['price']}")
        # 7. post what is missing
        have = {key(q) for q in self.own.values()}
        room = MAX_OPEN - len(open_ours)
        for q in [w for k, w in wanted.items() if k not in have][:max(0, min(MAX_POST_PER_TICK, room))]:
            give, want_ = ({"cash": q["price"]}, {"cards": [q["ref"]]}) if q["side"] == "bid" else \
                          ({"assets": [q["asset"]]}, {"cash": q["price"]})
            try:
                res = self.b.list_offer(give, want_, venue=VENUE, expires_in_ticks=EXPIRES)
            except BazaarError as e:
                self.guard.error(tick, e.code)
                log.say(f"[t{tick}] quote {q['side']} {q['ref']} refused: {e}")
                continue
            oid = (res.get("offer") or res).get("id")
            rec = {"event": "posted", "offer": oid, "tick": tick, **{k: q.get(k) for k in ("side", "ref", "price", "value", "gain", "asset")}}
            self.own[oid] = rec
            log.event("quotes", **rec)
            log.say(f"[t{tick}] QUOTE {q['side']} {q['ref']} at {q['price']} (worth {q['value']} to us, +{q['gain']})")

    def _cancel(self, oid, tick: int, why: str) -> None:
        try:
            self.b.cancel(oid)
        except BazaarError as e:
            self.guard.error(tick, e.code)
            log.say(f"[t{tick}] cancel {oid} refused: {e}")
            return
        q = self.own.pop(oid, {})
        log.event("quotes", event="cancelled", offer=oid, ref=q.get("ref"), why=why, tick=tick)
        log.say(f"[t{tick}] cancelled quote {oid} ({q.get('side')} {q.get('ref')}): {why}")
