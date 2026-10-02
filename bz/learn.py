"""Learn each dealer's habits from our own conversations and turn them into a plan for the next one.

After every haggle we save the full transcript (logs/threads/<id>.json). From all transcripts with a dealer
we build, per kind of deal ("sell:uncommon", "buy:pack:sobre_barrio", "buy:card:common", ...):

  first      her opening prices
  best       the best price she reached in each conversation (sell: highest bid, buy: lowest ask)
  patience   how many of our messages she took before naming her final offer
  moves      how many times she changed her price, and by how much

The plan for the next conversation of that kind:

  target     her best price ever: we pace our concessions to stand there two messages before her usual final
             offer (she meets us in the middle, so where we stand when her patience ends sets the price)
  accept_at  the best price she has ever given: once she offers it and stops moving, we take it (no ticks
             wasted waiting for her final word; while she still moves we keep exploring)
  patience   our number of messages to spread the concessions over
"""
import json
import os
import statistics

from bazaar_sdk import BazaarError

from . import log
from .texts import says_final

THREAD_DIR = os.path.join(log.LOG_DIR, "threads")
MODEL_PATH = os.path.join(log.LOG_DIR, "dealer_model.json")
TRAITS_PATH = os.path.join(log.LOG_DIR, "dealer_traits.json")
MESSAGES_PER_TRAIT = 8  # first guess, from Abuela alone (patience 0.85, final after 5-7 of our messages)


def _cash(o: dict):
    return (o.get("want") or {}).get("cash") or (o.get("give") or {}).get("cash")


def kind_of(t: dict, cards_by_id: dict = None) -> str:
    """The kind of deal a thread is about: sell:<rarity>, buy:pack:<id>, buy:card:<rarity>, buy:rarity:<r>."""
    topic = t.get("topic") or {}
    if "sell" in topic:
        for m in t.get("messages") or []:
            for a in ((m.get("offer") or {}).get("give") or {}).get("assets") or []:
                if isinstance(a, dict) and a.get("rarity"):
                    return f"sell:{a['rarity']}"
        return "sell:unknown"
    buy = topic.get("buy") or {}
    if "pack" in buy:
        return f"buy:pack:{buy['pack']}"
    if "card" in buy:
        rarity = (cards_by_id or {}).get(buy["card"], {}).get("rarity", "unknown")
        return f"buy:card:{rarity}"
    if "rarity" in buy:
        return f"buy:rarity:{buy['rarity']}"
    return "unknown"


def features(t: dict, cards_by_id: dict = None) -> dict:
    """What one conversation tells us about the dealer."""
    dealer = t.get("with")
    kind = kind_of(t, cards_by_id)
    sell = kind.startswith("sell")
    hers, ours, final_at, deal_price, ours_seen = [], [], None, None, 0
    for m in t.get("messages") or []:
        o = m.get("offer") or {}
        p = _cash(o)
        if o.get("status") == "settled" and p is not None:
            deal_price = p
        if p is None:
            continue
        if m.get("sender") == dealer:
            hers.append(p)
            if (o.get("final") or says_final(m.get("text"))) and final_at is None:
                final_at = ours_seen
        else:
            ours.append(p)
            ours_seen += 1
    # her best: her own offers and the price of the deal (she may accept OUR offer, better than any of hers)
    seen = hers + ([deal_price] if deal_price is not None else [])
    best = (max(seen) if sell else min(seen)) if seen else None
    moves = sum(1 for a, b in zip(hers, hers[1:]) if a != b)
    return {"thread": t.get("id"), "dealer": dealer, "kind": kind, "status": t.get("status"),
            "closed_reason": t.get("closed_reason"), "hers": hers, "ours": ours, "first": hers[0] if hers else None,
            "best": best, "final_after": final_at, "moves": moves, "deal_price": deal_price,
            "accepted_opening": deal_price is not None and hers and deal_price == hers[0] and len(ours) == 0}


def save_thread(b, thread_id: int) -> dict:
    """Store one transcript once it has ended (open threads are re-read later)."""
    t = b.thread(thread_id)
    if t.get("status") != "open":
        os.makedirs(THREAD_DIR, exist_ok=True)
        with open(os.path.join(THREAD_DIR, f"{thread_id}.json"), "w", encoding="utf-8") as f:
            json.dump(t, f, ensure_ascii=False, indent=1)
    return t


def backfill(b) -> int:
    """Save every ended conversation we have had (also those from before this module existed)."""
    res = b.my_threads()
    n = 0
    for th in res.get("threads", []) if isinstance(res, dict) else []:
        path = os.path.join(THREAD_DIR, f"{th['id']}.json")
        if th.get("status") != "open" and not os.path.exists(path):
            try:
                save_thread(b, th["id"])
                n += 1
            except BazaarError as e:
                log.say(f"cannot read thread {th['id']}: {e}")
    return n


def transcripts() -> list:
    if not os.path.isdir(THREAD_DIR):
        return []
    out = []
    for name in sorted(os.listdir(THREAD_DIR), key=lambda n: int(n.split(".")[0]) if n[0].isdigit() else 0):
        with open(os.path.join(THREAD_DIR, name), encoding="utf-8") as f:
            out.append(json.load(f))
    return out


def build_model(cards_by_id: dict = None) -> dict:
    """dealer -> kind -> statistics, from every saved transcript. Written to logs/dealer_model.json."""
    model: dict = {}
    for t in transcripts():
        f = features(t, cards_by_id)
        if f["dealer"] is None or f["first"] is None:
            continue
        model.setdefault(f["dealer"], {}).setdefault(f["kind"], []).append(f)
    out = {}
    for dealer, kinds in model.items():
        out[dealer] = {}
        for kind, fs in kinds.items():
            sell = kind.startswith("sell")
            haggled = [f for f in fs if f["ours"]]  # a conversation where we never spoke says little about her limit
            bests = [f["best"] for f in (haggled or fs)]
            finals = [f["final_after"] for f in haggled if f["final_after"] is not None]
            out[dealer][kind] = {
                "n": len(fs), "haggled": len(haggled),
                "first": [f["first"] for f in fs],
                "best": bests,
                "best_ever": max(bests) if sell else min(bests),
                "best_median": statistics.median(bests),
                "patience": statistics.median(finals) if finals else None,
                "moves_median": statistics.median([f["moves"] for f in haggled]) if haggled else None,
                "deals": [f["deal_price"] for f in fs if f["deal_price"] is not None],
                "opening_accepts": sum(1 for f in fs if f["accepted_opening"]),
                "threads": [f["thread"] for f in fs],
            }
    os.makedirs(log.LOG_DIR, exist_ok=True)
    with open(MODEL_PATH, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    return out


def save_traits(b) -> dict:
    """Keep each dealer's public traits (patience, strictness, ...) next to the model. One entry per dealer."""
    res = b.dealers()
    traits = {d["id"]: d.get("traits") or {} for d in res.get("personas", res.get("dealers", []))}
    os.makedirs(log.LOG_DIR, exist_ok=True)
    with open(TRAITS_PATH, "w", encoding="utf-8") as f:
        json.dump(traits, f, ensure_ascii=False, indent=1)
    return traits


def load_traits() -> dict:
    if not os.path.exists(TRAITS_PATH):
        return {}
    with open(TRAITS_PATH, encoding="utf-8") as f:
        return json.load(f)


def messages_per_trait(model: dict, traits: dict) -> float:
    """Our messages before a dealer names its final offer, per unit of its patience trait, seen across dealers.
    Each dealer is measured on its own conversations. Only this one number is shared between them."""
    ratios = [s["patience"] / traits[d]["patience"] for d, kinds in model.items() for s in kinds.values()
              if s["patience"] is not None and (traits.get(d) or {}).get("patience")]
    return statistics.median(ratios) if ratios else MESSAGES_PER_TRAIT


def best_elsewhere(dealer: str, kind: str, cards_by_id: dict = None):
    """Her best price for this kind at the OTHER dealers: our outside option (sell: highest bid, buy: lowest ask)."""
    seen = [kinds[kind]["best_ever"] for d, kinds in build_model(cards_by_id).items()
            if d != dealer and kind in kinds and kinds[kind]["haggled"]]
    if not seen:
        return None
    return max(seen) if kind.startswith("sell") else min(seen)


def plan(dealer: str, kind: str, cards_by_id: dict = None, traits: dict = None) -> dict:
    """Learned parameters for haggle(): target, accept_at, patience (all None without data).

    With no conversation of this kind yet, patience comes from the dealer's public patience trait."""
    model = build_model(cards_by_id)
    stats = model.get(dealer, {}).get(kind)
    if not stats or not stats["haggled"]:
        prior = None
        if traits and traits.get("patience"):
            ratio = messages_per_trait(model, load_traits())
            prior = max(2, round(ratio * traits["patience"]))
        return {"target": None, "accept_at": None, "patience": prior, "stats": stats,
                "source": "prior" if prior else None}
    patience = stats["patience"]
    # Aim at her best ever, not the median: with Abuela the price is set by where WE stand when her patience runs
    # out ("let's meet in the middle"), so we reach the target two messages before her usual final offer.
    return {
        "target": stats["best_ever"],
        "accept_at": stats["best_ever"],
        "patience": max(2, int(patience) - 2) if patience is not None else 4,
        "stats": stats,
    }


def describe(dealer: str, kind: str, p: dict) -> str:
    s = p.get("stats")
    if not s or not s["haggled"]:
        if p.get("source") == "prior":
            return (f"[{dealer}] {kind}: no haggled conversations yet, pacing over {p['patience']} messages "
                    f"(guess from its patience trait)")
        return f"[{dealer}] {kind}: no haggled conversations yet, default pacing"
    return (f"[{dealer}] {kind}: learned from {s['haggled']} haggles (her best {s['best']}, final after "
            f"~{s['patience']} of our messages) -> target {p['target']}, take at {p['accept_at']} once she stalls, "
            f"pace over {p['patience']} messages")
