"""Our agent. Commands:

    python3 agent.py status                     cash, level, score, spares, missing page cards
    python3 agent.py buy-pack [--limit 23]      haggle a neighbourhood pack from Abuela, then open it
    python3 agent.py sell-spares [--n 2]        sell our cheapest spare commons/uncommons to Abuela
    python3 agent.py buy-card LAV-09            haggle one card we miss from Abuela
    python3 agent.py abuela [--packs 1 --spares 2]   a session: spares first, then packs
    python3 agent.py learn                      save past conversations, show what we learned per dealer

Every haggle with Abuela or El Chato follows the dealer's fitted model (bz/predict.py: her limit from her first
answer, his concession schedule); --model learn goes back to the pacing learned per kind (bz/learn.py), which also
remains the fallback for dealers with no model yet. --no-learn turns both off.
Limits come from what the item is worth to us (bz/price.py): buy up to its value minus --margin, sell never below
what the copy is worth to us. If Abuela has never gone past our limit, we skip the haggle; --force tries anyway.

BAZAAR_KEY (and optionally BAZAAR_URL) come from the environment or a .env file next to this one.
"""
import argparse
import os
import sys

from bazaar_sdk import Bazaar, BazaarError
from bz import learn, log, predict, price
from bz.haggle import haggle
from bz.state import State

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DEALER = "abuela"


def load_env() -> None:
    path = os.path.join(HERE, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            k, sep, v = line.strip().partition("=")
            if sep and not k.startswith("#"):
                os.environ.setdefault(k.strip().removeprefix("export "), v.strip().strip("'\""))


def connect() -> Bazaar:
    load_env()
    key = os.environ.get("BAZAAR_KEY")
    if not key:
        sys.exit("Falta BAZAAR_KEY: exporta la clave del equipo o ponla en .env (BAZAAR_KEY=tk-...).")
    return Bazaar(os.environ.get("BAZAAR_URL", "https://bazaar.causaprima.ai"), key)


def menu(b: Bazaar, dealer: str) -> dict:
    return b.dealer(dealer)["menu"]


def sells_item(m: dict, **match) -> dict:
    return next((s for s in m["sells"] if all(s.get(k) == v for k, v in match.items())), None)


def learned(st: State, args, kind: str) -> dict:
    """haggle() keyword arguments learned from earlier conversations of this kind."""
    if getattr(args, "no_learn", False):
        return {}
    traits = (learn.load_traits().get(args.dealer) or {})
    p = learn.plan(args.dealer, kind, st.cards_by_id, traits=traits)
    if getattr(args, "patience", None):  # --patience: our own pacing beats the guess from his trait
        p["patience"] = args.patience
    log.say(learn.describe(args.dealer, kind, p))
    return {k: p[k] for k in ("target", "accept_at", "patience")}


def modeled(args, side: str, kind: str, limit: int) -> dict:
    """haggle(advise=...): the dealer's fitted model from bz/predict.py, unless --model learn or there is none."""
    if getattr(args, "no_learn", False) or getattr(args, "model", "predict") != "predict":
        return {}
    pkind = kind.replace("buy:card:", "buy:").replace("buy:rarity:", "buy:")
    adv = predict.advisor(args.dealer, side, pkind, limit)
    if adv is None:
        log.say(f"[{args.dealer}] {pkind}: no fitted model yet, learned pacing only (python3 -m bz.predict)")
        return {}
    log.say(f"[{args.dealer}] {pkind}: prices from the fitted model (bz/predict.py)")
    return {"advise": adv}


def skipped(side: str, label: str, why: str) -> dict:
    log.say(f"skip {label}: {why}")
    return {"side": side, "label": label, "status": "skipped", "reason": why, "price": None, "ours": [], "theirs": []}


def out_of_reach(args, side: str, limit: int, plan: dict):
    """Why the haggle cannot work, or None: her best price ever is already beyond our limit."""
    best = plan.get("accept_at")
    if getattr(args, "force", False) or best is None:
        return None
    if side == "buy" and best > limit:
        return f"her best price ever is {best}, above our limit {limit}"
    if side == "sell" and best < limit:
        return f"her best bid ever is {best}, below our floor {limit}"
    return None


def cmd_learn(b: Bazaar, st: State, _args) -> None:
    n = learn.backfill(b)
    print(f"saved {n} new transcripts")
    for dealer, kinds in learn.build_model(st.cards_by_id).items():
        for kind, s in kinds.items():
            print(f"{dealer:8} {kind:24} n={s['n']} haggled={s['haggled']} first={s['first']} best={s['best']} "
                  f"patience={s['patience']} deals={s['deals']} opening_accepts={s['opening_accepts']}")
            print("         " + learn.describe(dealer, kind, learn.plan(dealer, kind, st.cards_by_id)))


def cmd_status(b: Bazaar, st: State, _args) -> None:
    me = st.me
    score = me.get("score") or {}
    print(f"{me['name']}: {me['cash']} P, level {me['level']}, score {score.get('score')} (rank {score.get('rank')})")
    print(f"unlocked: {me.get('unlocked') or me.get('dealers')}")
    cards = st.cards()
    print(f"{len(cards)} cards, {len(st.packs())} sealed packs, value {sum(a.get('your_value') or 0 for a in cards):.1f}")
    for a in st.spares():
        print(f"  spare {a['ref']:7} {a['name'][:28]:28} {a.get('rarity', ''):9} worth {a.get('your_value')} to us")
    for set_id, miss in st.missing().items():
        print(f"  {set_id}: missing {len(miss)} page cards {' '.join(miss)}")


def open_new_packs(b: Bazaar, st: State, ref: str = "sobre_barrio") -> None:
    st.refresh()
    for p in st.packs(ref):
        try:
            res = b.open_pack(p["id"])
        except BazaarError as e:
            log.say(f"cannot open pack {p['id']}: {e}")
            continue
        log.event("packs", pack=p["id"], cards=res.get("cards"), luck=res.get("luck"))
        for c in res.get("cards", []):
            log.say(f"  pulled {c.get('ref', c.get('id'))} {c['name']} · {c['rarity']} · #{c.get('serial')}/{c.get('print_run')}")


def bounded(side: str, asked, default: int, bound: int = None) -> int:
    """Our limit: --limit when given, else the default; never past what the card is worth to us (CLAUDE.md).
    Crossing that bound needs Maru's OK, so it is done by hand, not with a flag."""
    bound = default if bound is None else bound
    if asked is None:
        return default
    ok = min(asked, bound) if side == "buy" else max(asked, bound)
    if ok != asked:
        log.say(f"--limit {asked} crosses our value bound {bound}: using {ok} (ask Maru to cross it)")
    return ok


def cmd_buy_pack(b: Bazaar, st: State, args) -> dict:
    pack = args.pack
    item = sells_item(menu(b, args.dealer), pack=pack)
    if not item:
        sys.exit(f"{args.dealer} does not sell {pack}")
    lp = item["list_price"]
    worth = price.from_state(st).pack_value(pack)
    limit = min(st.cash, bounded("buy", args.limit, price.buy_cap(worth, margin=args.margin)))
    label = f"pack (list {lp}, worth {worth:.1f} to us)"
    log.say(f"{label}: limit {limit}")
    if limit < 1:
        return skipped("buy", label, f"worth {worth:.1f} to us: not worth buying")
    opening = args.open or round(lp * 0.5)
    plan = learned(st, args, f"buy:pack:{pack}")
    why = out_of_reach(args, "buy", limit, plan)
    if why:
        return skipped("buy", label, why)
    res = haggle(b, args.dealer, {"buy": {"pack": pack}}, "buy", opening, limit,
                 step_frac=args.step, label=label, **plan, **modeled(args, "buy", f"buy:pack:{pack}", limit))
    if res["status"] == "deal" and not args.keep:
        open_new_packs(b, st, pack)
    return res


def cmd_buy_card(b: Bazaar, st: State, args) -> dict:
    card = st.cards_by_id.get(args.card)
    if not card:
        sys.exit(f"unknown card {args.card}")
    item = sells_item(menu(b, args.dealer), rarity=card["rarity"])
    if not item:
        sys.exit(f"{args.dealer} does not sell {card['rarity']} cards")
    worth = b.value(args.card)["your_value"]
    lp = item["list_price"]
    limit = min(st.cash, lp, bounded("buy", args.limit, price.buy_cap(worth, margin=args.margin)))
    label = f"{args.card} (list {lp}, worth {worth} to us)"
    if limit < 1:
        return skipped("buy", label, f"{args.card} is worth {worth} to us: not worth buying")
    plan = learned(st, args, f"buy:card:{card['rarity']}")
    why = out_of_reach(args, "buy", limit, plan)
    if why:
        return skipped("buy", label, why)
    return haggle(b, args.dealer, {"buy": {"card": args.card}}, "buy", args.open or round(lp * 0.5), limit,
                  step_frac=args.step, label=label, **plan, **modeled(args, "buy", f"buy:card:{card['rarity']}", limit))


def cmd_sell_spares(b: Bazaar, st: State, args) -> list:
    m = menu(b, args.dealer)
    buys = {r["rarity"] for r in m["buys"]}
    prices = {s["rarity"]: s["list_price"] for s in m["sells"] if s.get("rarity")}
    only = getattr(args, "card", None)  # --card: sell only spares of this card
    out, tried = [], set()
    for _ in range(args.n):
        st.refresh()  # another session on our key may have sold a spare since we last looked
        a = next((x for x in st.spares(rarities=buys) if x["id"] not in tried and (not only or x["ref"] == only)), None)
        if a is None:
            log.say(f"no spare left to sell{' for ' + only if only else ''}")
            break
        tried.add(a["id"])
        valuer = price.from_state(st)
        rarity = st.cards_by_id[a["ref"]]["rarity"]
        worth = valuer.copy_value(a["ref"])
        elsewhere = learn.best_elsewhere(args.dealer, f"sell:{rarity}", st.cards_by_id)
        # never sell below what the copy is worth to us, nor below what another dealer already paid
        floor = bounded("sell", args.limit, max(price.sell_floor(worth), elsewhere or 0), price.sell_floor(worth))
        log.say(f"floor {floor} for {a['ref']}: worth {worth:.1f} to us, best bid at other dealers {elsewhere}")
        # a dealer that only buys this rarity (Ernesto, epics) has no list price for it: start from the card's book
        opening = args.open or max(floor + 1, round(prices.get(rarity, st.cards_by_id[a["ref"]].get("book", 10)) * 1.2))
        label = f"spare {a['ref']} (worth {worth:.1f} to us)"
        plan = learned(st, args, f"sell:{rarity}")
        why = out_of_reach(args, "sell", floor, plan)
        if why:
            out.append(skipped("sell", label, why))
            continue
        res = haggle(b, args.dealer, {"sell": {"assets": [a["id"]]}}, "sell", opening, floor,
                     step_frac=args.step, label=label, **plan, **modeled(args, "sell", f"sell:{rarity}", floor))
        out.append(res)
        if res["status"] == "error":
            break
    return out


def cmd_abuela(b: Bazaar, st: State, args) -> None:
    args.open = args.limit = None
    sells = cmd_sell_spares(b, st, args) if args.spares else []
    buys = []
    for _ in range(args.packs):
        st.refresh()
        buys.append(cmd_buy_pack(b, st, args))
        if buys[-1]["status"] in ("error", "skipped"):
            break
    for r in sells + buys:
        print(f"{r['side']:4} {r['label'][:45]:45} {r['status']:12} price {r['price']}  path ours {r['ours']} hers {r['theirs']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="The Bazaar agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("learn")
    for name in ("buy-pack", "buy-card", "sell-spares", "abuela"):
        p = sub.add_parser(name)
        p.add_argument("--dealer", default=DEFAULT_DEALER, help="who to trade with (abuela, chato)")
        p.add_argument("--step", type=float, default=0.15, help="share of the room left to our limit we concede per message")
        p.add_argument("--no-learn", action="store_true", help="ignore what earlier conversations taught us")
        p.add_argument("--force", action="store_true", help="haggle even if her best price ever is beyond our limit")
        p.add_argument("--margin", type=float, default=0.1, help="share of an item's value we keep as profit when buying")
        p.add_argument("--model", choices=("predict", "learn"), default="predict",
                       help="predict: the dealer's fitted model sets our prices (bz/predict.py); learn: the old pacing")
        p.add_argument("--patience", type=int, help="pace our concessions over this many messages (El Chato: 8 when he sells)")
        if name != "abuela":
            p.add_argument("--open", type=int, help="our first price")
            p.add_argument("--limit", type=int, help="most we pay (buy) / least we take (sell)")
        if name == "buy-card":
            p.add_argument("card")
        if name == "sell-spares":
            p.add_argument("--n", type=int, default=1)
        if name == "sell-spares":
            p.add_argument("--card", help="sell only spares of this card (e.g. LAT-02)")
        if name == "buy-pack":
            p.add_argument("--pack", default="sobre_barrio", help="pack id (chato sells sobre_plata)")
        if name in ("buy-pack", "abuela"):
            p.add_argument("--keep", action="store_true", help="do not open the pack")
        if name == "abuela":
            p.add_argument("--packs", type=int, default=1)
            p.add_argument("--spares", type=int, default=2)
    args = ap.parse_args()
    if args.cmd == "abuela":
        args.n, args.pack = args.spares, "sobre_barrio"
    b = connect()
    st = State(b)
    if args.cmd not in ("status", "learn"):
        learn.backfill(b)
        try:
            learn.save_traits(b)
        except BazaarError as e:
            log.say(f"could not save dealer traits: {e}")
    {"status": cmd_status, "learn": cmd_learn, "buy-pack": cmd_buy_pack, "buy-card": cmd_buy_card,
     "sell-spares": cmd_sell_spares, "abuela": cmd_abuela}[args.cmd](b, st, args)


if __name__ == "__main__":
    main()
