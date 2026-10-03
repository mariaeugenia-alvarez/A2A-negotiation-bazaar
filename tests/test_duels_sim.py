"""The real duels.py loop (v2) against a FAKE duel server: no network. Checks the live path end to end: tick 0 silence, the
opening at tick 1 with the right text and day, one message per tick, texts that carry price (and day), limit never crossed.
python3 tests/test_duels_sim.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("BAZAAR_KEY", "x")
import bz.log  # noqa: E402
import duels  # noqa: E402


class Fake:
    def __init__(self, role, limit, issues, script, w=None, meaning=None, ticks=12, start=500):
        self.role, self.limit, self.issues, self.script = role, limit, issues, script
        self.w, self.meaning, self.start, self.end = w, meaning, start, start + ticks
        self.tick, self.msgs, self.rival, self.sent, self.accepted, self.status = start, [], None, [], [], "live"

    def clock(self):
        return {"tick": self.tick, "tick_seconds": 30}

    def _rival_speaks(self):  # the scripted rival speaks at the START of a tick
        if self.tick in self.script and self.status == "live":
            p, dy = self.script[self.tick]
            self.msgs.append({"tick": self.tick, "from": "Rival Azul", "text": "", "price": p, "days": dy})
            self.rival = {"id": 900 + self.tick, "price": p, "tick": self.tick, "days": dy}

    def duels(self, done=False):
        if done or self.status != "live":
            return {"duels": []}
        return {"duels": [{"duel": 77, "status": "live", "role": self.role, "your_limit": self.limit, "issues": self.issues,
                           "your_days_weight": self.w, "days_meaning": self.meaning, "deadline_tick": self.end,
                           "decay_per_round": 0.08, "messages": list(self.msgs), "rival_offer": self.rival, "item": "X"}]}

    def duel_say(self, did, text="", price=None, days=None):
        self.sent.append({"tick": self.tick, "text": text, "price": price, "days": None})
        self.msgs.append({"tick": self.tick, "from": "you", "text": text, "price": price, "days": None})

    def call(self, method, path, body=None):
        self.sent.append({"tick": self.tick, "text": body["text"], "price": body["price"], "days": body["days"]})
        self.msgs.append({"tick": self.tick, "from": "you", "text": body["text"], "price": body["price"], "days": body["days"]})

    def duel_accept(self, did):
        self.accepted.append(self.tick)
        self.status = "deal"

    def wait_tick(self):
        self.tick += 1
        if self.tick >= self.end or self.status != "live":
            self.status = "done" if self.status == "live" else self.status
        self._rival_speaks()
        return self.clock()


def run(fake, *extra):
    bz.log.LOG_DIR = tempfile.mkdtemp()
    duels.connect = lambda: fake
    sys.argv = ["duels.py", "--duel-ticks", "12", *extra]
    fake._rival_speaks()
    try:
        duels.main()
    except SystemExit:
        pass
    return fake


checks = 0
DAYS = "each day of delay costs you this much"
# S1: price only, buyer limit 100, a silent rival. Tick 500 (start): nothing. Tick 501: the opening at 0.75 x 100.
f = run(Fake("buyer", 100, ["price"], {}))
assert f.sent and f.sent[0]["tick"] == 501 and f.sent[0]["price"] == 75, f.sent
assert f.sent[0]["text"] == "Rápido y justo: 75 P. / Quick and fair: 75 P.", f.sent[0]["text"]
assert len({s["tick"] for s in f.sent}) == len(f.sent), "one message per tick at most"; checks += 3
# S2: two issues. The opening at tick 501 carries a day (0-10) in both languages, never beyond our limit.
f = run(Fake("buyer", 100, ["price", "days"], {}, w=2, meaning=DAYS))
s = f.sent[0]
assert s["tick"] == 501 and s["price"] == 75 and 0 <= s["days"] <= 10, s
assert f"día {s['days']}" in s["text"] and f"day {s['days']}" in s["text"] and "75 P" in s["text"], s
assert s["text"].startswith("Rápido y justo") and "¿Qué día de entrega te va mejor?" in s["text"]; checks += 3
# S3: the rival opens far outside our limit and answers our opening: a counter text names the day, price stays <= 100
f = run(Fake("buyer", 100, ["price", "days"], {500: (150, 5), 502: (145, 5), 504: (140, 5)}, w=2, meaning=DAYS, ticks=14))
texts = [(x["tick"], x["price"], x["days"], x["text"]) for x in f.sent]
assert texts, "S3: the agent must speak"
assert all(p <= 100 and 0 <= d <= 10 for _, p, d, _ in texts), texts
assert all(f"{p} P" in t and f"día {d}" in t and f"day {d}" in t for _, p, d, t in texts), texts
assert any(t.startswith("Parece que el día te importa") for *_, t in texts) or len(texts) == 1, texts
assert all("última" not in t.lower() and "final" not in t.lower() and "last" not in t.lower() for *_, t in texts)
assert len({x["tick"] for x in f.sent}) == len(f.sent); checks += 5
# S4: a price-only seller: the counter text has no day, the price never goes below our cost
f = run(Fake("seller", 60, ["price"], {500: (40, None), 502: (45, None), 504: (48, None)}, ticks=14))
assert f.sent and all(x["price"] >= 60 and x["days"] is None for x in f.sent), f.sent
assert all("día" not in x["text"] and "day" not in x["text"].replace("delivery", "") for x in f.sent), f.sent
assert f.sent[0]["text"].startswith("Rápido y justo"); checks += 3
# S5: a rival who offers inside our limit and keeps moving: we stay silent (waiting), then take it
f = run(Fake("buyer", 100, ["price"], {500: (95, None), 501: (92, None), 502: (90, None)}, ticks=12))
assert not f.sent or f.sent[0]["tick"] > 502, f"S5: no message while he concedes alone, got {f.sent}"
assert f.accepted, "S5: the in-limit offer must be taken"; checks += 2
# S6: v1 still works with the new texts (the fallback): its first offer is the opening text
f = run(Fake("buyer", 100, ["price"], {}), "--policy", "v1")
assert f.sent and f.sent[0]["text"].startswith("Rápido y justo") and f.sent[0]["price"] <= 100, f.sent; checks += 1
print(f"test_duels_sim: {checks} checks passed")
