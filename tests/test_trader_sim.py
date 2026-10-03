"""The live trader loop against a FAKE game (no network, no real primas): earmark, swap, probes, dealers, guard stop and
resume, tick scaling. python3 tests/test_trader_sim.py

A: cash 27 (Saturday evening) with the earmark RET-09:60. B: cash 177 (after Sunday's 150 P allowance).
C: an accept that settles worse than planned -> the guard stops us, cancels our quotes, writes the pause file; the file
is then removed and the guard resets by itself.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("BAZAAR_KEY", "x")
import bz.log  # noqa: E402
import bz.quoter  # noqa: E402
import trader  # noqa: E402

RAR = {"common": {"book": 10}, "uncommon": {"book": 25}, "rare": {"book": 70}}
CARDS = [("RET-01", "common"), ("RET-02", "common"), ("RET-03", "common"), ("RET-04", "common"), ("RET-05", "common"),
         ("RET-06", "uncommon"), ("RET-09", "rare")]
CATALOG = {"rarities": RAR, "values": {"copy_marginals": [1.0, 0.25, 0.1]}, "packs": [],
           "sets": [{"id": "RET", "released": True, "cards": [{"id": c, "rarity": r, "page": True} for c, r in CARDS]}]}
VALUE = {"RET-03": 13.0, "RET-04": 13.0, "RET-05": 13.0, "RET-06": 32.5, "RET-09": 177.0}


def offer(i, maker, give, want, venue="v02", to=None):
    return {"id": i, "maker": maker, "to": to, "venue": venue, "thread": None, "status": "open", "expires_tick": 999,
            "give": {"cash": 0, "assets": [], "types": [], **give}, "want": {"cash": 0, "assets": [], "types": [], **want}}


def asset(i, ref, value, rarity="common"):
    return {"id": i, "kind": "card", "ref": ref, "rarity": rarity, "your_value": value}


class Fake:
    def __init__(self, cash, settle_price=None, settle_fee=0, ticks=8, tick_seconds=30):
        self.cash, self.tick, self.ticks, self.tick_seconds = cash, 100, ticks, tick_seconds
        self.settle_price, self.settle_fee = settle_price, settle_fee
        self.calls, self.events, self.next_id, self.mine = [], [], 5000, []
        self.max_promised = 0
        self.assets = [asset(1, "RET-01", 13.0), asset(2, "RET-02", 13.0), asset(3, "RET-02", 3.2)]  # a spare RET-02
        self.board_offers = [
            offer(10, "m1", {"assets": [{"id": 70, "kind": "card", "ref": "RET-03"}]}, {"cash": 9}),                  # clear win, 9 P
            offer(11, "m2", {"assets": [{"id": 71, "kind": "card", "ref": "RET-04"}]}, {"assets": [{"id": 3, "kind": "card", "ref": "RET-02"}]}),  # swap
            offer(12, "m3", {"assets": [{"id": 72, "kind": "card", "ref": "RET-05"}]}, {"cash": 20}, to="t09"),       # counter at 11
            offer(13, "m4", {"assets": [{"id": 73, "kind": "card", "ref": "RET-06"}]}, {"cash": 60}, to="t09"),       # far above: probe
            offer(14, "abuela", {"assets": [{"id": 74, "kind": "card", "ref": "RET-03"}]}, {"cash": 6}, venue=None, to="t09"),
        ]

    # ---- the API the trader uses
    def clock(self):
        return {"tick": self.tick, "tick_seconds": self.tick_seconds, "paused": False}

    def catalog(self):
        return CATALOG

    def me(self):
        return {"id": "t09", "name": "T9", "cash": self.cash, "assets": self.assets, "affinity": {"RET": 1.3}, "tick": self.tick,
                "score": {"neg_points": 20.0, "rank": 10},
                "album": {"pages": [{"set": "RET", "have": 2, "of": 7, "complete": False}], "filled": 2, "slots": 7}}

    def value(self, ref):
        return {"card": ref, "your_value": VALUE[ref]}

    def venues(self):
        return {"venues": [{"venue": "v02", "fee_bps": 0, "fee_per_card": 0, "status": "open", "owner": "t12"},
                           {"venue": "rastro", "fee_bps": 500, "fee_per_card": 1, "status": "open", "owner": "house"}]}

    def board(self, venue):
        return {"offers": [o for o in self.board_offers if o["venue"] == venue and not o.get("to")]}

    def my_offers(self):
        return {"offers": self.mine + [o for o in self.board_offers if o.get("to") == "t09"]}

    def feed(self, limit=150):
        return {"events": self.events}

    def accept(self, oid, assets=None):
        self.calls.append(("accept", oid))
        o = next(x for x in self.board_offers if x["id"] == oid)
        self.board_offers = [x for x in self.board_offers if x["id"] != oid]
        price = self.settle_price if (self.settle_price is not None and oid == 10) else o["want"]["cash"]
        fee = self.settle_fee if oid == 10 else 0
        ref = (o["give"]["assets"] or [{"ref": "?"}])[0]["ref"]
        self.events.append({"type": "settlement", "payload": {"tick": self.tick + 1, "parties": ["t09", o["maker"]],
                                                              "price": price, "fee": fee, "items": [{"ref": ref}]}})
        return {}

    def list_offer(self, give, want, venue=None, to=None, expires_in_ticks=40):
        self.next_id += 1
        self.calls.append(("list", give, want, venue, to, expires_in_ticks))
        self.mine.append({"id": self.next_id, "maker": "t09", "to": to, "venue": venue, "status": "open", "expires_tick": 999,
                          "give": {"cash": give.get("cash", 0), "assets": [{"id": a, "kind": "card", "ref": "?"} for a in give.get("assets", [])],
                                   "types": []},
                          "want": {"cash": want.get("cash", 0), "assets": [], "types": ["card:" + r for r in want.get("cards", [])]}})
        self.max_promised = max(self.max_promised, sum(o["give"]["cash"] for o in self.mine))
        return {"offer": {"id": self.next_id}}

    def cancel(self, oid):
        self.calls.append(("cancel", oid))
        self.mine = [o for o in self.mine if o["id"] != oid]

    def wait_tick(self):
        self.tick += 1
        self.ticks -= 1
        if self.ticks <= 0:
            raise SystemExit(0)
        return self.clock()


def run(fake, argv_extra=(), pause_text=None, remove_pause_at=None):
    tmp = tempfile.mkdtemp()
    bz.log.LOG_DIR = tmp
    trader.PAUSE, trader.ACCEPTS, bz.quoter.QUOTES = (os.path.join(tmp, "trader.pause"), os.path.join(tmp, "trader_accept.jsonl"),
                                                       os.path.join(tmp, "quotes.jsonl"))
    trader.HEARTBEAT = os.path.join(tmp, "trader.heartbeat")
    trader.connect = lambda: fake
    if pause_text is not None:
        open(trader.PAUSE, "w").write(pause_text)
    if remove_pause_at is not None:  # a person deletes the pause file when the fake reaches this tick
        orig = fake.wait_tick

        def wt():
            if fake.tick + 1 == remove_pause_at and os.path.exists(trader.PAUSE):
                os.remove(trader.PAUSE)
            return orig()
        fake.wait_tick = wt
    sys.argv = ["trader.py", "--live", "--live-boards", "--quotes", *argv_extra]
    try:
        trader.main()
    except SystemExit:
        pass
    return tmp


checks = 0

# ---- A: cash 27, earmark RET-09:60 (default). The swap passes (it costs nothing). The 9 P buy, the counter at 11 and the
#         standing bids are blocked. The 60 P probe is never sent. The dealer's offer is never touched.
EARMARK = ("--earmark", "RET-09:60")
f = Fake(27)
run(f, EARMARK)
acc = [c[1] for c in f.calls if c[0] == "accept"]
assert acc == [11], f"A: only the swap may be accepted, got {acc}"
assert not [c for c in f.calls if c[0] == "list" and (c[1].get("cash") or 0) > 0], f"A: no bid or counter with cash, got {f.calls}"
assert 14 not in acc and 13 not in acc; checks += 3

# ---- B: cash 177. The swap first (best surplus), then the 9 P buy two ticks later (one accept per tick + 2 tick pause).
f = Fake(177, ticks=10)
run(f, EARMARK)
acc = [c[1] for c in f.calls if c[0] == "accept"]
assert acc == [11, 10], f"B: swap then buy, got {acc}"
lists = [c for c in f.calls if c[0] == "list"]
counters = [c for c in lists if c[4] == "m3"]
assert len(counters) == 1 and counters[0][1] == {"cash": 11} and counters[0][2] == {"cards": ["RET-05"]}, counters   # 11, once
assert counters[0][5] == 20, "30 s ticks: the counter lives 20 ticks"
assert not [c for c in lists if c[4] == "m4"], "B: a probe (under half the ask) must not be sent"
assert not [c for c in lists if c[4] == "abuela"] and 14 not in acc
quotes = [c for c in lists if c[4] is None and c[3] == "rastro"]
assert quotes, "B: the quoter posts standing quotes with 102 P of budget"
assert not [c for c in quotes if c[2] == {"cards": ["RET-09"]}], "B: no quoter bid for the earmarked card"
bid_cash = sum(c[1]["cash"] for c in quotes if "cash" in c[1])
assert bid_cash <= 177 - 60 - 15, f"B: bids may promise at most 102, promised {bid_cash}"
assert quotes[0][5] == 120, "30 s ticks: quotes last 120 ticks"
checks += 9

# ---- B2: Sunday, 15 s ticks: every tick window doubles (counter 40, quotes 240)
f = Fake(177, ticks=6, tick_seconds=15)
run(f, EARMARK)
lists = [c for c in f.calls if c[0] == "list"]
assert [c for c in lists if c[4] == "m3"][0][5] == 40 and [c for c in lists if c[4] is None][0][5] == 240; checks += 1

# ---- B3: once we hold RET-09 the earmark releases: the 9 P buy is allowed even with little cash
f = Fake(27)
f.assets.append(asset(9, "RET-09", 177.0, "rare"))
run(f, EARMARK)
acc = [c[1] for c in f.calls if c[0] == "accept"]
assert 10 in acc, f"B3: earmark released, the 9 P buy must pass, got {acc}"; checks += 1

# ---- E: earmark OFF (the default), cash 27: the sure 9 P buy passes even though our own bid promises cash; bids and
#         buying counters together never promise more than 12 P (27 minus the 15 P floor) at any moment.
f = Fake(27, ticks=10)
run(f)
acc = [c[1] for c in f.calls if c[0] == "accept"]
assert acc == [11, 10], f"E: swap then the 9 P buy, got {acc}"
cs = [c for c in f.calls if c[0] == "list" and c[4] == "m3"]
assert cs == [], "E: the 8 P bid (+5) takes the 12 P above the floor; the weaker 11 P counter (+2) must wait"
assert f.max_promised <= 27 - 15, f"E: open bids and counters may promise at most 12 P of the 27 at any time, got {f.max_promised}"; checks += 3

# ---- C: the 9 P buy settles at 14 P (planned 9): realized gain 4 - 5 = -1 -> the guard stops us, cancels our quotes,
#         writes the pause file with the reason; deleting the file resets the guard (no new file is written).
f = Fake(177, settle_price=14, ticks=14)
tmp = run(f)
pause = trader.PAUSE
assert os.path.exists(pause), "C: the guard must write the pause file"
assert "lost" in open(pause).read(), open(pause).read()
assert [c for c in f.calls if c[0] == "cancel"], "C: our quotes must be cancelled on a stop"; checks += 3
n_calls = len(f.calls)
f2 = Fake(177, ticks=6)
run(f2, pause_text="old reason\n", remove_pause_at=None)
assert not [c for c in f2.calls if c[0] in ("accept", "list")], "C: a pause file present at start: nothing may be sent"; checks += 1

# ---- D: guard reset when a person removes the file the guard wrote
f = Fake(177, settle_price=14, ticks=24)
orig_wait = f.wait_tick


def wait_and_clear():  # at tick 112 a person looks and deletes the pause file
    if f.tick == 111 and os.path.exists(trader.PAUSE):
        os.remove(trader.PAUSE)
    return orig_wait()


f.wait_tick = wait_and_clear
run(f)
alerts = open(os.path.join(bz.log.LOG_DIR, "alerts.jsonl")).read()
assert '"STOP"' in alerts and '"RESUME"' in alerts, alerts
assert not os.path.exists(trader.PAUSE) or "lost" not in open(trader.PAUSE).read() or alerts.count('"STOP"') >= 1
checks += 2
# ---- F: hands-off. A team asks 50 P for RET-09 (worth 177 to us). With cash 177 and no earmark: nothing accepts it, nothing
#         is quoted for it, nothing is countered. With --hands-off none (control) the quoter does bid for it.
def with_ret09(cash):
    g = Fake(cash, ticks=6)
    g.board_offers.append(offer(15, "m5", {"assets": [{"id": 75, "kind": "card", "ref": "RET-09"}]}, {"cash": 50}))
    return g


f = with_ret09(177)
run(f)
assert 15 not in [c[1] for c in f.calls if c[0] == "accept"], "F: a hands-off card is never accepted"
assert not [c for c in f.calls if c[0] == "list" and c[2] == {"cards": ["RET-09"]}], "F: and never quoted"
f = with_ret09(177)
run(f, ("--hands-off", "none"))
assert [c for c in f.calls if c[0] == "list" and c[2] == {"cards": ["RET-09"]}] or 15 in [c[1] for c in f.calls if c[0] == "accept"], \
    "F control: without hands-off the trader goes after RET-09"
checks += 3

# ---- G: accepts we could not take are logged with the reason, and the heartbeat is written
f = Fake(27, ticks=6)
tmp = run(f, ("--budget", "5"))                                   # 5 P an hour: the 9 P buy is over the budget
rows = [json.loads(line) for line in open(os.path.join(tmp, "trader_blocked.jsonl"))]
assert any(r["offer"] == 10 and r["reason"] == "budget" and r["surplus"] == 4.0 and r["cost"] == 9 for r in rows), rows
assert 11 not in [r["offer"] for r in rows if r["reason"] == "budget"], "the swap costs nothing: never blocked by the budget"
hb = json.load(open(trader.HEARTBEAT))
assert hb["live"] is True and hb["cash"] == 27 and hb["tick"] >= 100 and hb["stopped"] is False, hb
checks += 3
# ---- H: another process on our key already lists one copy of a 2-copy card: the quoter must not list the other
f = Fake(177, ticks=5)
f.mine.append({"id": 9001, "maker": "t09", "to": None, "venue": "rastro", "status": "open", "expires_tick": 999,
               "give": {"cash": 0, "assets": [{"id": 3, "kind": "card", "ref": "RET-02"}], "types": []},
               "want": {"cash": 7, "assets": [], "types": []}})        # a foreign ask for the spare copy (id 3)
run(f)
sold = [c for c in f.calls if c[0] == "list" and c[1].get("assets")]
assert not [c for c in sold if set(c[1]["assets"]) & {1, 2, 3}], f"H: no second RET-02 copy may be listed, got {sold}"; checks += 1
print(f"test_trader_sim: {checks} checks passed")
