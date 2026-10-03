"""Banco de pruebas: our haggle() against simulated dealers whose secret limit we know (free, no network).

Each configuration (our opening, our pacing, the model) plays every world of every dealer family: midpoint (like
Abuela), boulware (like El Chato) and immobile (like Doña Pilar, who never moved). A world fixes the dealer's limit,
its patience and our own reserve, so we can score what no live thread can tell us:

  ZOPA   the prices both sides accept. Buying: from his limit L up to our reserve R, width R - L.
  SE+    surplus efficiency: what we keep over the ZOPA width, (R - price) / (R - L); 0 without a deal.
         The mean over worlds with a ZOPA, so a 2 P margin and a 200 P one weigh the same.
  AGR+   share of worlds with a ZOPA where we close             SE+ = AGR+ x CSE+
  CSE+   mean SE+ over those deals
  FAGR-  share of worlds without a ZOPA where we close anyway (lower is better)
  viol   deals past our own reserve, over every game (lower is better; must stay 0)

Every figure carries a 95 % bootstrap interval over the worlds. Fixed concessors (haggle() moving 1 %, 10 % or
30 % of the room left on each message) are the floor: a configuration that does not beat the 30 % one is no
improvement. The words we write do not move a simulated dealer, so the persona does not enter here.

    python3 -m bz.testbed            # the table
    python3 -m bz.testbed --json F   # the data, as the dashboard reads it
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
import random
import shutil
import tempfile

from . import log
from .predict import abuela_next, advisor, chato_allowance, chato_schedule, towards

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(log.LOG_DIR, "testbed.json")
SOURCES = ("testbed.py", "haggle.py", "predict.py", "texts.py")  # a change in any of them reruns the testbed
RESAMPLES, SEED = 1000, 9

# what each side looks like: the dealer's opening price and the grid of worlds
OPENING = {"buy": 100, "sell": 40}
LIMITS = {"buy": (70, 76, 82, 88, 94), "sell": (46, 52, 58, 64, 70)}
RESERVES = {"buy": (80, 90), "sell": (60, 50)}  # ours: the most we pay, the least we take
IMMOBILE_RESERVES = {"buy": (90, 96, 104, 112), "sell": (30, 36, 44, 50)}  # around his one price
PATIENCES = (4, 6, 8)


class SimDealer:
    """A dealer that answers each of our prices by its family's rule, never past its limit. side is OUR side."""
    final_at_limit = False

    def __init__(self, name, side, start, limit, patience, kind):
        self.name, self.side, self.d, self.kind = name, side, towards(side), kind
        self.start, self.price, self.limit, self.pat = start, start, limit, patience
        self.answers, self.conceded, self.last = 0, 0, None
        self.status, self.reason, self.deal_price = "open", None, None
        self.offers, self.messages = [], []
        self._post(start)

    def _post(self, p, final=False):
        for o in self.offers:
            o["status"] = "withdrawn"
        leg = {"cash": p}
        offer = {"id": len(self.offers) + 1, "maker": self.name, "status": "open", "final": final,
                 "want": leg if self.side == "buy" else {}, "give": leg if self.side == "sell" else {}}
        self.offers.append(offer)
        self.messages.append({"id": len(self.messages) + 1, "sender": self.name, "text": "", "offer": offer})

    def answer(self, step):
        raise NotImplementedError

    # the part of the API haggle() uses
    def my_threads(self, status=None): return {"threads": []}
    def open_thread(self, who, topic=None): return {"id": 1}
    def close_thread(self, tid): self.status = "closed"
    def accept(self, oid): self.status, self.deal_price = "accepting", self.price

    def thread(self, tid):
        return {"id": 1, "status": self.status, "closed_reason": self.reason, "standing_offers": self.offers,
                "messages": self.messages}

    def wait_tick(self):
        if self.status == "accepting":
            self.status = "deal"

    def say(self, tid, text, price):
        if self.status != "open":
            return
        self.messages.append({"id": len(self.messages) + 1, "sender": "us", "text": text, "offer": {"give": {"cash": price}}})
        d = self.d
        if price == self.last:  # the same price again is spam: he stops talking to us
            self.status, self.reason = "closed", "cooloff"
            return
        if d * (price - self.price) >= 0:  # we met his price
            self.status, self.deal_price = "accepting", price
            return
        if self.offers[-1]["final"]:  # we did not take his last word: he walks
            self.status, self.reason = "closed", "walked"
            return
        step = None if self.last is None else max(0, d * (price - self.last))
        self.last = price
        self.answers += 1
        new = self.answer(step)
        new = max(new, self.limit) if d > 0 else min(new, self.limit)
        if d * (price - new) >= 0:  # we reached what he would say next: he takes ours
            self.status, self.deal_price = "accepting", price
            return
        self.conceded += abs(new - self.price)
        self.price = new
        self._post(new, final=self.answers >= self.pat or (self.final_at_limit and new == self.limit))


class Midpoint(SimDealer):
    """Abuela: half the way to her limit on her first answer, then a quarter of what is left."""
    final_at_limit = True

    def answer(self, step):
        return abuela_next(self.price, self.limit, self.side, first=self.answers == 1)


class Boulware(SimDealer):
    """El Chato: by his k-th answer at most floor(a k^2 + b) conceded in all, never more than our own step."""

    def answer(self, step):
        a, b = chato_schedule(self.kind, self.start)
        room = chato_allowance(self.answers, a, b) - self.conceded
        return self.price - self.d * max(0, room if step is None else min(step, room))


class Immobile(SimDealer):
    """Doña Pilar: one price, never moves."""

    def answer(self, step):
        return self.price


FAMILIES = {  # id -> (label, simulated dealer, the dealer name our model knows it by)
    "midpoint": ("Punto medio (como Abuela)", Midpoint, "abuela"),
    "boulware": ("Boulware (como El Chato)", Boulware, "chato"),
    "immobile": ("Inmóvil (como Doña Pilar)", Immobile, "pilar"),
}

# one row each: how far our opening is from his price, and how we pace (the model, a horizon, a fixed share)
CONFIGS = [
    {"id": "model50", "label": "Modelo · apertura 50 %", "tier": "model", "open": 0.50, "model": True, "patience": 6},
    {"id": "model35", "label": "Modelo · apertura 35 %", "tier": "model", "open": 0.35, "model": True, "patience": 6},
    {"id": "pace4", "label": "Ritmo 4 · apertura 50 %", "tier": "pace", "open": 0.50, "patience": 4},
    {"id": "pace8", "label": "Ritmo 8 · apertura 50 %", "tier": "pace", "open": 0.50, "patience": 8},
    {"id": "pace6o35", "label": "Ritmo 6 · apertura 35 %", "tier": "pace", "open": 0.35, "patience": 6},
    {"id": "fixed01", "label": "Concesor fijo 1 %", "tier": "baseline", "open": 0.50, "step_frac": 0.01},
    {"id": "fixed10", "label": "Concesor fijo 10 %", "tier": "baseline", "open": 0.50, "step_frac": 0.10},
    {"id": "fixed30", "label": "Concesor fijo 30 %", "tier": "baseline", "open": 0.50, "step_frac": 0.30, "floor": True},
]


def worlds(family: str) -> list:
    """(side, his opening, his limit, his patience, our reserve) for every world of this family."""
    out = []
    for side in ("buy", "sell"):
        a = OPENING[side]
        if family == "immobile":
            out += [(side, a, a, pat, r) for r in IMMOBILE_RESERVES[side] for pat in (4, 8)]
        else:
            out += [(side, a, lim, pat, r) for lim in LIMITS[side] for r in RESERVES[side] for pat in PATIENCES]
    return out


def play(cfg: dict, family: str, world: tuple) -> dict:
    from .haggle import haggle
    side, start, limit, patience, reserve = world
    _, cls, name = FAMILIES[family]
    kind = f"{side}:testbed"  # no fitted schedule: El Chato's per-opening rule, the same for the dealer and the model
    dealer = cls(name, side, start, limit, patience, kind)
    opening = round(start * (1 - cfg["open"])) if side == "buy" else round(start * (1 + cfg["open"]))
    kw = {"step_frac": cfg["step_frac"]} if "step_frac" in cfg else {"patience": cfg["patience"]}
    if cfg.get("model"):
        kw["advise"] = advisor(name, side, kind, reserve, threads=[])  # None for a dealer we have no model of
    r = haggle(dealer, name, {}, side, opening, reserve, **kw)
    d = towards(side)
    zopa = d * (reserve - limit)
    deal = r["status"] == "deal"
    price = r["price"] if deal else None
    return {"side": side, "limit": limit, "patience": patience, "reserve": reserve, "zopa": zopa > 0,
            "deal": deal, "price": price, "msgs": len(r["ours"]),
            "se": (d * (reserve - price) / zopa if deal else 0.0) if zopa > 0 else None,
            "viol": deal and d * (price - reserve) > 0}


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def _ci(xs, rng):
    """The mean and its 95 % bootstrap interval; None for an empty sample."""
    if not xs:
        return None
    n = len(xs)
    means = sorted(sum(rng.choice(xs) for _ in range(n)) / n for _ in range(RESAMPLES))
    return {"v": round(_mean(xs), 4), "lo": round(means[int(0.025 * RESAMPLES)], 4), "hi": round(means[int(0.975 * RESAMPLES) - 1], 4), "n": n}


def metrics(games: list, rng) -> dict:
    zopa = [g for g in games if g["zopa"]]
    closed = [g for g in zopa if g["deal"]]
    return {"se": _ci([g["se"] for g in zopa], rng), "agr": _ci([float(g["deal"]) for g in zopa], rng),
            "cse": _ci([g["se"] for g in closed], rng), "fagr": _ci([float(g["deal"]) for g in games if not g["zopa"]], rng),
            "viol": _ci([float(g["viol"]) for g in games], rng), "games": len(games), "zopa_games": len(zopa)}


@contextlib.contextmanager
def _sandbox():
    """haggle() logs and keeps transcripts: send them to a temporary folder, never to logs/."""
    from . import learn
    saved = log.LOG_DIR, learn.THREAD_DIR
    tmp = tempfile.mkdtemp(prefix="testbed-")
    log.LOG_DIR, learn.THREAD_DIR = tmp, os.path.join(tmp, "threads")
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            yield
    finally:
        log.LOG_DIR, learn.THREAD_DIR = saved
        shutil.rmtree(tmp, ignore_errors=True)


def run() -> dict:
    rng = random.Random(SEED)
    rows = []
    with _sandbox():
        for cfg in CONFIGS:
            per = {f: [play(cfg, f, w) for w in worlds(f)] for f in FAMILIES}
            rows.append({**{k: cfg[k] for k in ("id", "label", "tier")}, "floor": bool(cfg.get("floor")),
                         "all": metrics([g for gs in per.values() for g in gs], rng),
                         "by_family": {f: metrics(gs, rng) for f, gs in per.items()}})
    return {"src": source_hash(), "configs": rows, "families": {f: v[0] for f, v in FAMILIES.items()},
            "worlds": {f: len(worlds(f)) for f in FAMILIES}, "resamples": RESAMPLES}


def source_hash() -> str:
    h = hashlib.sha256()
    for name in SOURCES:
        with open(os.path.join(HERE, name), "rb") as f:
            h.update(f.read())
    return h.hexdigest()[:16]


def cached(path: str = CACHE_PATH) -> dict:
    """The last run if the code it measured has not changed since, else a new run (about 3 s)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("src") == source_hash():
            return data
    except (OSError, ValueError):
        pass
    data = run()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data


def _fmt(m):
    return "-" if m is None else f"{m['v']:.2f} [{m['lo']:.2f}-{m['hi']:.2f}]"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", metavar="FILE", help="write the data to FILE instead of printing the table")
    args = ap.parse_args()
    data = run()
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return
    floor = next(r for r in data["configs"] if r["floor"])["all"]["se"]["v"]
    print(f"{'configuration':26} {'SE+ up':>18} {'AGR+ up':>18} {'CSE+ up':>18} {'FAGR- down':>18} {'viol down':>18}")
    for r in data["configs"]:
        m = r["all"]
        flag = "" if r["tier"] == "baseline" or m["se"]["v"] > floor else "  < floor (fixed 30 %)"
        print(f"{r['label']:26} {_fmt(m['se']):>18} {_fmt(m['agr']):>18} {_fmt(m['cse']):>18} {_fmt(m['fagr']):>18} {_fmt(m['viol']):>18}{flag}")
    print("\nSE+ per dealer family")
    print(f"{'configuration':26} " + " ".join(f"{data['families'][f][:24]:>26}" for f in FAMILIES))
    for r in data["configs"]:
        print(f"{r['label']:26} " + " ".join(f"{_fmt(r['by_family'][f]['se']):>26}" for f in FAMILIES))


if __name__ == "__main__":
    main()
