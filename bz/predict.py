"""Predict each dealer's next price, its secret limit and its final word, from every conversation we can see.

Data: the public feed (logs/feed.jsonl) carries every team's priced messages with every dealer, and our own
transcripts (logs/threads/) add the ones after the feed logger stopped. `load_threads()` rebuilds them all.
Prices are measured "towards us": when a dealer sells, a concession lowers its price; when it buys, it raises it.
`python3 -m bz.predict` fits both models on that data and prints how well they predict.

Abuela Carmen, a midpoint dealer:
  limit     every conversation has a secret limit L
  1st move  her first concession goes half the way to L, rounded down: d1 = (A - L) // 2, so L is 2*d1 or
            2*d1 + 1 past her opening A. One answer tells us her limit within 1 P.
  then      a quarter of the way left each time we move towards her, at least 1 P, never past L
  accepts   our offer once it reaches the price she would say next (never past L)
  final     after 4-7 of her answers, or on reaching L, she names her final offer

El Chato, a Boulware dealer with reciprocity:
  schedule  by his k-th answer he may have conceded, in total, at most floor(a k^2 + b): nothing at first,
            faster and faster later ("a" per kind of deal: ~0.1 for uncommons, ~0.5 for rares)
  reciprocal never more in one answer than our own last step ("Yo no me muevo si tú apenas te mueves")
  accepts   our offer once it reaches the price he would say next
  final     after 4-8 answers

What we control is the same for both: how far we move each time and when we stop. `advise()` turns the
models into the next price to send; `advisor()` wraps it for haggle(advise=...), which agent.py uses by default.

A new dealer (Doña Pilar so far: she bid 16 and never moved) gets no model until it moves in some conversation;
then `family_of()` picks, per kind of deal, whichever family predicts its answers best.
"""
import collections
import json
import math
import os
import statistics

from . import log

FEED_PATH = os.path.join(log.LOG_DIR, "feed.jsonl")
THREAD_DIR = os.path.join(log.LOG_DIR, "threads")
CATALOG_PATH = os.path.join(log.LOG_DIR, "public_cache.json")

# Chato's schedule per kind, fitted on the feed and our transcripts, 57 conversations (python3 -m bz.predict refits it on fresh data)
CHATO_SCHEDULE = {"buy:uncommon": (0.10, 0.5), "buy:rare": (0.48, 0.5), "sell:uncommon": (0.06, 0.0)}
CHATO_A_PER_OPENING = 0.005  # a / opening price, for kinds with too little data (rares: 0.48 / 97)

Answer = collections.namedtuple("Answer", "step conc price final ask ours")
"""One dealer answer: our move towards it since its last answer (None: our first price), its concession,
its new price, whether that is its final word, its price before answering and our price it answered."""


# ---------------------------------------------------------------------------------------------- the data

def _rarities(catalog_path: str = CATALOG_PATH) -> dict:
    try:
        with open(catalog_path, encoding="utf-8") as f:
            cat = json.load(f)["catalog"]
    except (OSError, KeyError, ValueError):
        return {}
    return {c["id"]: c["rarity"] for s in cat["sets"] for c in s["cards"]}


def _cash(offer: dict):
    return ((offer or {}).get("want") or {}).get("cash") or ((offer or {}).get("give") or {}).get("cash")


def kind_of(topic: dict, messages: list, rarity: dict) -> str:
    """sell:<rarity> (xN for several cards), buy:pack:<id>, buy:<rarity> (a named card or any card of a rarity)."""
    topic = topic or {}
    if "sell" in topic:
        n = len(topic["sell"].get("assets") or [])
        for m in messages:
            for a in (((m.get("offer") or {}).get("give") or {}).get("assets") or []):
                if isinstance(a, dict) and a.get("rarity"):
                    return f"sell:{a['rarity']}" + (f"x{n}" if n > 1 else "")
        return "sell:unknown"
    buy = topic.get("buy") or {}
    if "pack" in buy:
        return f"buy:pack:{buy['pack']}"
    if "card" in buy:
        return f"buy:{rarity.get(buy['card'], 'unknown')}"
    if "rarity" in buy:
        return f"buy:{buy['rarity']}"
    return "unknown"


def _feed_threads(path: str) -> dict:
    out: dict = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        events = [json.loads(line) for line in f if line.strip()]
    for e in events:
        p = e.get("payload") or {}
        if p.get("kind") != "persona":
            continue
        t = out.setdefault(p.get("thread"), {"id": p.get("thread"), "messages": [], "deals": []})
        t.setdefault("team", p.get("team"))
        t.setdefault("with", p.get("with"))
        if e["type"] == "thread.opened":
            t["topic"] = p.get("topic")
        elif e["type"] == "thread.message":
            t["messages"].append({"id": p.get("message"), "tick": e["tick"], "sender": p.get("sender"),
                                  "text": p.get("text"), "offer": p.get("offer") or {}})
    # a settlement names the team and the dealer, not the thread: give it to their latest conversation before it
    for e in events:
        p = e.get("payload") or {}
        if e["type"] != "settlement" or not p.get("persona"):
            continue
        team = next((x for x in p.get("parties", []) if x != p["persona"]), None)
        dealer_sold = any(i.get("frm") == p["persona"] for i in p.get("items") or [])
        cands = [t for t in out.values() if t.get("team") == team and t.get("with") == p["persona"]
                 and ("sell" not in (t.get("topic") or {})) == dealer_sold
                 and t["messages"] and t["messages"][0]["tick"] <= e["tick"] <= t["messages"][-1]["tick"] + 3]
        if cands:
            max(cands, key=lambda t: t["messages"][0]["tick"])["deals"].append(p.get("price"))
    for t in out.values():
        t["messages"].sort(key=lambda m: m["id"] or 0)
    return out


def _transcripts(folder: str) -> dict:
    out = {}
    if not os.path.isdir(folder):
        return out
    for name in os.listdir(folder):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            t = json.load(f)
        if t.get("kind") != "persona":
            continue
        msgs = sorted(t.get("messages") or [], key=lambda m: m.get("id") or 0)
        deals = [_cash(m["offer"]) for m in msgs if (m.get("offer") or {}).get("status") == "settled"]
        out[t["id"]] = {"id": t["id"], "team": t.get("team"), "with": t.get("with"), "topic": t.get("topic"),
                        "messages": msgs, "deals": deals}
    return out


def _seq(messages: list, dealer: str) -> list:
    seq = []
    for m in sorted(messages or [], key=lambda m: m.get("id") or 0):
        price = _cash(m.get("offer"))
        if m.get("sender") == dealer:
            seq.append(("D", price, bool((m.get("offer") or {}).get("final"))))
        elif price is not None:
            seq.append(("U", price))
    return seq


def load_threads(feed_path: str = FEED_PATH, transcript_dir: str = THREAD_DIR, catalog_path: str = CATALOG_PATH) -> list:
    """Every dealer conversation we can see, all teams: {id, team, dealer, kind, side, seq, deal}.

    seq is the conversation in order: ("D", price, final) for the dealer, ("U", price) for the team.
    side is the team's side: "buy" when the dealer sells."""
    rarity = _rarities(catalog_path)
    merged = _feed_threads(feed_path)
    for tid, t in _transcripts(transcript_dir).items():  # our own copy is complete: prefer it when longer
        if tid not in merged or len(t["messages"]) >= len(merged[tid]["messages"]):
            merged[tid] = t
    out = []
    for tid, t in sorted(merged.items(), key=lambda x: x[0] or 0):
        dealer = t.get("with")
        if not dealer or not t.get("topic"):  # opened before the feed logger: we miss its start
            continue
        kind = kind_of(t["topic"], t["messages"], rarity)
        out.append({"id": tid, "team": t.get("team"), "dealer": dealer, "kind": kind,
                    "side": "sell" if kind.startswith("sell") else "buy", "seq": _seq(t["messages"], dealer),
                    "deal": t["deals"][-1] if t.get("deals") else None})
    return out


def towards(side: str) -> int:
    """+1 when the dealer sells to us (its price falls as it concedes), -1 when it buys from us."""
    return 1 if side == "buy" else -1


def answers(t: dict) -> tuple:
    """(opening, [Answer, ...]): the dealer's first price, then each later answer and what we did before it.

    A dealer answers the latest price we sent; repeating or backing off is no move (step 0)."""
    d = towards(t["side"])
    ask, ours, seen, out = None, None, None, []
    for ev in t["seq"]:
        if ev[0] == "U":
            ours = ev[1]
            continue
        if ev[1] is None:  # words only (a refusal, a walk-out)
            continue
        if ask is None:
            ask, seen = ev[1], ours
            opening = ev[1]
            continue
        step = None if seen is None and ours is not None else (max(0, d * (ours - seen)) if ours is not None else 0)
        out.append(Answer(step, d * (ask - ev[1]), ev[1], ev[2], ask, ours))
        ask, seen = ev[1], ours
    return (opening if ask is not None else None), out


def moved(a: Answer) -> bool:
    return a.step is None or a.step > 0


# ------------------------------------------------------------------------------------------ Abuela Carmen

def abuela_limit(opening: int, first_price: int, side: str) -> tuple:
    """Her secret limit from her first concession: (the far end, the near end); the far end is the better
    price for us. d1 = (A - L) // 2, so L is 2*d1 or 2*d1 + 1 away from her opening."""
    d = towards(side)
    d1 = d * (opening - first_price)
    return opening - d * (2 * d1 + 1), opening - d * 2 * d1


def abuela_next(ask: int, limit: int, side: str, first: bool = False) -> int:
    """Her answer when we move towards her: half the way to her limit the first time, then a quarter of the
    way left (at least 1 P), never past her limit. Exact in 87 % of answers, otherwise 1 P off."""
    d = towards(side)
    gap = d * (ask - limit)
    if gap <= 0:
        return ask
    gap = gap - gap // 2 if first else gap - max(1, math.floor(gap / 4 + 0.5))
    return limit + d * max(0, gap)


def abuela_path(opening: int, limit: int, side: str, answers_n: int) -> list:
    """Her prices over `answers_n` answers if we move towards her every time."""
    path, ask = [], opening
    for i in range(answers_n):
        ask = abuela_next(ask, limit, side, first=i == 0)
        path.append(ask)
    return path


def abuela_patience(threads: list, side: str = "buy") -> list:
    """How many answers she gave before naming her final (her answers to our moves, the greeting excluded)."""
    out = []
    for t in threads:
        if t["dealer"] != "abuela" or t["side"] != side:
            continue
        _, ans = answers(t)
        n = 0
        for a in ans:
            n += 1
            if a.final:
                out.append(n)
                break
    return out or [4, 5, 6]


def abuela_forecast(opening: int, first_price: int, side: str, patience: list) -> dict:
    """Where her final will land if we move towards her every time, given her first answer.

    Each limit in the bracket and each patience seen in the data is equally likely; she stops early when
    she reaches her limit. Returns the bracket, the expected final and the spread of finals."""
    far, near = abuela_limit(opening, first_price, side)
    finals = []
    for limit in (far, near):
        for k in patience:  # her first answer is the first of her k; then quarter steps
            ask = first_price
            for _ in range(max(0, k - 1)):
                ask = abuela_next(ask, limit, side)
            finals.append(ask)
    return {"limit": (far, near), "expected_final": statistics.mean(finals),
            "best": min(finals) if side == "buy" else max(finals), "worst": max(finals) if side == "buy" else min(finals),
            "finals": sorted(finals)}


# --------------------------------------------------------------------------------------------- El Chato

def chato_allowance(k: int, a: float, b: float) -> int:
    """The most he has conceded, in total, by his k-th answer."""
    return max(0, math.floor(a * k * k + b))


def chato_next(ask: int, conceded: int, k: int, step, a: float, b: float, side: str) -> int:
    """His k-th answer (k from 1): he matches our step, up to what his schedule allows by now."""
    room = chato_allowance(k, a, b) - conceded
    give = room if step is None else min(step, room)
    return ask - towards(side) * max(0, give)


def chato_schedule(kind: str, opening: int = None, fitted: dict = None) -> tuple:
    sched = (fitted or CHATO_SCHEDULE).get(kind)
    if sched:
        return sched
    return (CHATO_A_PER_OPENING * (opening or 0), 0.5)


def fit_chato(threads: list) -> dict:
    """a, b per kind, from these conversations (one dealer's): the schedule that predicts his answers exactly most often, given what each team did."""
    by_kind = collections.defaultdict(list)
    for t in threads:  # the caller picks the dealer's conversations
        _, ans = answers(t)
        if ans:
            by_kind[t["kind"]].append(ans)
    out = {}
    for kind, convs in by_kind.items():
        best = None
        for a in [x / 100 for x in range(2, 81, 2)]:
            for b in (0.0, 0.25, 0.5):
                hits = sum(_chato_hits(ans, a, b)[0] for ans in convs)
                if best is None or hits > best[0]:
                    best = (hits, a, b)
        out[kind] = (best[1], best[2])
    return out


def _chato_hits(ans: list, a: float, b: float) -> tuple:
    hits, conceded = 0, 0
    for k, x in enumerate(ans, 1):
        room = chato_allowance(k, a, b) - conceded
        pred = max(0, room if x.step is None else min(x.step, room))
        hits += pred == x.conc
        conceded += x.conc
    return hits, len(ans)


def chato_plan(opening: int, side: str, kind: str, answers_n: int = 6, fitted: dict = None) -> dict:
    """Our steps that collect everything his schedule allows, and where he ends after `answers_n` answers."""
    a, b = chato_schedule(kind, opening, fitted)
    steps = [max(1, chato_allowance(k, a, b) - chato_allowance(k - 1, a, b)) for k in range(1, answers_n + 1)]
    final = opening - towards(side) * chato_allowance(answers_n, a, b)
    return {"steps": steps, "final": final, "total_steps": sum(steps), "schedule": (a, b)}


# ---------------------------------------------------------------------------------------------- advice

def advise(dealer: str, side: str, kind: str, opening: int, history: list, limit: int, fitted: dict = None) -> dict:
    """What to do next. history: [(our price, the dealer's answer), ...] after its opening, oldest first;
    limit is ours (the most we pay, the least we take).

    Returns {"action": "offer" | "accept", "price", "why", "her_next"}. "accept" means take the dealer's
    standing price now. A final word inside our limit is always worth taking: the dealer walks otherwise."""
    d = towards(side)
    ours = history[-1][0] if history else None
    her = history[-1][1] if history else opening

    def clip(p):
        return min(p, limit) if side == "buy" else max(p, limit)

    def below(p, nxt):  # never offer what the dealer would say anyway: it would take our price instead
        return nxt - d if nxt is not None and d * (p - nxt) >= 0 else p

    if dealer == "abuela":
        if not history:  # far from her: room to move 1 P at a time for as long as her patience lasts
            return {"action": "offer", "price": clip(opening - d * (opening // 2)), "her_next": None,
                    "why": "open far: her first answer goes half the way to her limit and gives it away"}
        far, near = abuela_limit(opening, history[0][1], side)
        if d * (her - near) <= 0 and ours == far:  # we asked for her far end and she stayed: her limit is near
            return {"action": "accept", "price": her, "her_next": her, "why": f"her limit is {near}: take it"}
        nxt = abuela_next(her, far, side)
        if d * (nxt - far) <= 0 or d * (her - near) <= 0:  # at most 1 P left: offer the far end, she takes it if she can
            return {"action": "offer", "price": clip(far), "her_next": nxt, "why": f"her limit is {far}-{near}: offer {far}"}
        price = below(ours + d if ours is not None else clip(opening // 2), nxt)
        if ours is not None and d * (price - ours) <= 0:  # no room left below her next price: offer it, same price
            price = nxt
        return {"action": "offer", "price": clip(price), "her_next": nxt,
                "why": f"her limit is {far}-{near}; she concedes the same whatever our step, so +1 P"}

    if dealer == "chato":
        a, b = chato_schedule(kind, opening, fitted)
        k = len(history) + 1
        conceded = d * (opening - her)
        room = chato_allowance(k, a, b) - conceded
        step = max(1, room)
        if ours is None:
            return {"action": "offer", "price": clip(opening - d * max(4, math.floor(opening * 0.38))), "her_next": opening,
                    "why": "open far: he gives nothing on his first answers anyway"}
        nxt = chato_next(her, conceded, k, step, a, b, side)
        why = f"his schedule allows {room} more on answer {k}; he never gives more than our step: step {step}"
        gap = d * (her - ours)
        if step >= gap - min(step, room):  # this step meets him: he matches it, so we meet in the middle
            step = max(-(-gap // 2), gap - max(0, room))
            nxt = chato_next(her, conceded, k, step, a, b, side)
            why = f"we meet him now: he matches our step up to {room}, so the meeting point is {ours + d * step}"
        return {"action": "offer", "price": clip(ours + d * step), "her_next": nxt, "why": why}

    price = (ours + d) if ours is not None else opening - d * round(opening * 0.3)
    return {"action": "offer", "price": clip(price), "her_next": None, "why": "no model for this dealer yet: small steps"}


MIN_MOVING = 3  # conversations where a new dealer conceded at least once, before family_of() picks its family
MODELS = {"abuela": "midpoint", "chato": "boulware"}  # a new dealer gets the family that fits its data best


def advisor(dealer: str, side: str, kind: str, limit: int, threads: list = None):
    """For haggle(): a function of the live thread (API shape) giving advise()'s next move, or None if we have no
    model for this dealer and kind. The function itself returns {"action": "wait"} while the dealer has not answered
    our last price (never send twice), and None before her first answer (haggle() uses its own opening)."""
    family = MODELS.get(dealer) or (family_of(dealer, threads if threads is not None else load_threads()) or {}).get(kind)
    if family is None:
        return None
    model = {"midpoint": "abuela", "boulware": "chato"}[family]  # same rules, this dealer's own data
    fitted = fit_chato([t for t in (threads or []) if t["dealer"] == dealer]) if family == "boulware" and dealer != "chato" else None

    def next_move(t: dict):
        seq = _seq(t.get("messages"), dealer)
        if not any(e[0] == "D" and e[1] is not None for e in seq):
            return None  # her opening is not here yet
        if seq and seq[-1][0] == "U":
            return {"action": "wait", "price": None, "why": "she has not answered our last price"}
        opening, ans = answers({"seq": seq, "side": side})
        if not ans:  # only her opening so far: our first price is haggle()'s own opening
            return None
        hist = [(a.ours, a.price) for a in ans]
        return advise(model, side, kind, opening, hist, limit, fitted=fitted)
    return next_move


def family_of(dealer: str, threads: list) -> dict:
    """Per kind, the family of rules that predicts this dealer's answers best: "midpoint" (Abuela) or "boulware"
    (El Chato), scored on the same answers (each one after the dealer's first concession). None for a kind where
    the dealer moved in fewer than MIN_MOVING conversations: too little data to tell them apart."""
    by_kind = collections.defaultdict(list)
    for t in threads:
        if t["dealer"] == dealer:
            by_kind[t["kind"]].append(t)
    out = {}
    for kind, ts in by_kind.items():
        sched = fit_chato(ts).get(kind)
        mid = boul = n = 0
        for t in ts:
            opening, ans = answers(t)
            first = next((i for i, a in enumerate(ans) if moved(a)), None)
            if first is None:
                continue
            later = ans[first + 1:]
            far, near = abuela_limit(opening, ans[first].price, t["side"])
            mid += max(sum((abuela_next(a.ask, L, t["side"]) if moved(a) else a.ask) == a.price for a in later)
                       for L in (far, near))
            if sched:
                boul += sum(hit for i, hit in enumerate(_chato_preds(ans, *sched)) if i > first)
            n += len(later)
        moving = sum(1 for t in ts if any(a.conc for a in answers(t)[1]))
        # too few conversations where it moved: no family yet (a guess would set real prices)
        out[kind] = None if moving < MIN_MOVING or not n else ("midpoint" if mid >= boul else "boulware")
    return out


def _chato_preds(ans: list, a: float, b: float) -> list:
    """1 where the Boulware rule predicts the answer's concession exactly, else 0."""
    out, conceded = [], 0
    for k, x in enumerate(ans, 1):
        room = chato_allowance(k, a, b) - conceded
        out.append(int(max(0, room if x.step is None else min(x.step, room)) == x.conc))
        conceded += x.conc
    return out


# ------------------------------------------------------------------------------------------ validation

def evaluate(threads: list) -> dict:
    """How well each model predicts, against the naive guess "1 P per move", on every answer after the first."""
    report = {}
    # Abuela: limit bracket, then each later answer from her limit (the end of the bracket that fits best)
    rows = collections.defaultdict(lambda: {"n": 0, "exact": 0, "abs": 0, "base_exact": 0, "base_abs": 0,
                                            "threads": 0, "bracket_violations": 0})
    for t in threads:
        if t["dealer"] != "abuela":
            continue
        opening, ans = answers(t)
        first = next((i for i, a in enumerate(ans) if moved(a)), None)
        if first is None:
            continue
        r = rows[t["kind"]]
        r["threads"] += 1
        d = towards(t["side"])
        far, near = abuela_limit(opening, ans[first].price, t["side"])
        seen = [a.price for a in ans] + ([t["deal"]] if t["deal"] is not None else [])
        best_seen = min(seen) if d == 1 else max(seen)
        r["bracket_violations"] += d * (best_seen - far) < 0
        scores = []
        for limit in (far, near):
            preds = []
            for a in ans[first + 1:]:
                preds.append((abuela_next(a.ask, limit, t["side"]) if moved(a) else a.ask, a.price))
            scores.append(preds)
        preds = max(scores, key=lambda ps: sum(p == q for p, q in ps))
        for (p, q), a in zip(preds, ans[first + 1:]):
            base = a.ask - d * (1 if moved(a) else 0)
            r["n"] += 1
            r["exact"] += p == q
            r["abs"] += abs(p - q)
            r["base_exact"] += base == q
            r["base_abs"] += abs(base - q)
    report["abuela"] = {k: _summary(v) for k, v in rows.items()}

    # Abuela's final, forecast from her first answer alone, against the old rule of thumb (opening - 2*d1)
    pats = {side: abuela_patience(threads, side) for side in ("buy", "sell")}
    fin = collections.defaultdict(lambda: {"n": 0, "abs": 0, "base_abs": 0})
    for t in threads:
        if t["dealer"] != "abuela":
            continue
        opening, ans = answers(t)
        first = next((a for a in ans if moved(a)), None)
        final = next((a.price for a in ans if a.final), None)
        if first is None or final is None:
            continue
        f = abuela_forecast(opening, first.price, t["side"], pats[t["side"]])
        r = fin[t["kind"]]
        r["n"] += 1
        r["abs"] += abs(f["expected_final"] - final)
        r["base_abs"] += abs(abuela_limit(opening, first.price, t["side"])[1] - final)
    report["abuela_final"] = {k: {"n": v["n"], "mae": round(v["abs"] / v["n"], 2),
                                  "rule_of_thumb_mae": round(v["base_abs"] / v["n"], 2)} for k, v in fin.items()}

    # Chato: leave one conversation out, fit the schedule on the rest, predict its answers
    chato = [t for t in threads if t["dealer"] == "chato" and answers(t)[1]]
    rows = collections.defaultdict(lambda: {"n": 0, "exact": 0, "abs": 0, "base_exact": 0, "base_abs": 0, "threads": 0})
    for t in chato:
        fitted = fit_chato([x for x in chato if x["id"] != t["id"]])
        opening, ans = answers(t)
        a, b = chato_schedule(t["kind"], opening, fitted)
        r = rows[t["kind"]]
        r["threads"] += 1
        conceded = 0
        for k, x in enumerate(ans, 1):
            room = chato_allowance(k, a, b) - conceded
            pred = max(0, room if x.step is None else min(x.step, room))
            base = 1 if moved(x) else 0
            r["n"] += 1
            r["exact"] += pred == x.conc
            r["abs"] += abs(pred - x.conc)
            r["base_exact"] += base == x.conc
            r["base_abs"] += abs(base - x.conc)
            conceded += x.conc
    report["chato"] = {k: _summary(v) for k, v in rows.items()}
    report["chato_schedule"] = fit_chato(chato)
    return report


def _summary(r: dict) -> dict:
    n = max(1, r["n"])
    out = {"threads": r["threads"], "answers": r["n"], "exact": round(r["exact"] / n, 2), "mae": round(r["abs"] / n, 2),
           "baseline_exact": round(r["base_exact"] / n, 2), "baseline_mae": round(r["base_abs"] / n, 2)}
    if "bracket_violations" in r:
        out["bracket_violations"] = r["bracket_violations"]
    return out


def outcomes(threads: list, dealer: str) -> dict:
    """What teams actually got, per kind: deals and finals (the price range we can aim at)."""
    out = collections.defaultdict(lambda: {"deals": [], "finals": []})
    for t in threads:
        if t["dealer"] != dealer:
            continue
        _, ans = answers(t)
        if t["deal"] is not None:
            out[t["kind"]]["deals"].append(t["deal"])
        f = next((a.price for a in ans if a.final), None)
        if f is not None:
            out[t["kind"]]["finals"].append(f)
    return {k: {"deals": sorted(v["deals"]), "finals": sorted(v["finals"])} for k, v in out.items()}


if __name__ == "__main__":
    ths = load_threads()
    print(f"{len(ths)} dealer conversations: " + ", ".join(f"{d} {n}" for d, n in collections.Counter(t['dealer'] for t in ths).most_common()))
    rep = evaluate(ths)
    print("\nAbuela, each answer after her first (model | naive 1 P per move):")
    for k, v in sorted(rep["abuela"].items()):
        print(f"  {k:22s} {v['threads']:3d} conv {v['answers']:3d} answers  exact {v['exact']:.0%} mae {v['mae']:.2f} | "
              f"exact {v['baseline_exact']:.0%} mae {v['baseline_mae']:.2f}   limit bracket broken: {v['bracket_violations']}")
    print("\nAbuela's final, from her first answer alone (model | opening - 2*d1):")
    for k, v in sorted(rep["abuela_final"].items()):
        print(f"  {k:22s} {v['n']:3d} finals  mae {v['mae']:.2f} | {v['rule_of_thumb_mae']:.2f}")
    print("\nEl Chato, each concession, leave-one-conversation-out (model | naive min(step, 1)):")
    for k, v in sorted(rep["chato"].items()):
        print(f"  {k:22s} {v['threads']:3d} conv {v['answers']:3d} answers  exact {v['exact']:.0%} mae {v['mae']:.2f} | "
              f"exact {v['baseline_exact']:.0%} mae {v['baseline_mae']:.2f}")
    print("  schedule a k^2 + b per kind:", {k: v for k, v in sorted(rep["chato_schedule"].items())})
    pats = {side: abuela_patience(ths, side) for side in ("buy", "sell")}
    print(f"\nAbuela's patience (answers before her final), we buy: {sorted(collections.Counter(pats['buy']).items())}, "
          f"we sell: {sorted(collections.Counter(pats['sell']).items())}")
    firsts = collections.defaultdict(collections.Counter)  # her first answers seen, per kind and opening
    for t in ths:
        if t["dealer"] == "abuela":
            opening, ans = answers(t)
            first = next((a for a in ans if moved(a)), None)
            if first is not None:
                firsts[(t["kind"], t["side"], opening)][first.price] += 1
    for (kind, side, opening), seen in sorted(firsts.items()):
        if sum(seen.values()) < 3:
            continue
        for first, n in sorted(seen.items()):
            f = abuela_forecast(opening, first, side, pats[side])
            print(f"  {kind:22s} opening {opening:2d}, first answer {first:2d} ({n:2d}x): limit {min(f['limit'])}-{max(f['limit'])}, "
                  f"final ~{f['expected_final']:.1f} ({min(f['finals'])}-{max(f['finals'])})")
    print("\nEl Chato, steps that collect his whole schedule over 6 answers:")
    for kind, opening, side in (("buy:uncommon", 33, "buy"), ("buy:rare", 97, "buy"), ("sell:uncommon", 13, "sell")):
        p = chato_plan(opening, side, kind, 6, rep["chato_schedule"])
        print(f"  {kind:14s} opening {opening}: our steps {p['steps']} -> his price after 6 answers {p['final']}")
