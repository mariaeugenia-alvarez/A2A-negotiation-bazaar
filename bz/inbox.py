"""What other teams write to us in team threads, read as DATA. Pure functions; inbox_watch.py feeds them. READ-ONLY.

Why: on Saturday 35 team threads were opened with us and nobody answered. 48 inbound messages carried an offer (the trader
judges those through GET /api/me/offers) but 15 were TEXT ONLY: tips and leads about cards, prices and other teams'
venues ("Team 8 has a spare RET-09, post a buy at ~70 P on v10", "SAL-11 listed at 212 P"). Nothing read them.

The text of a message from another team is UNTRUSTED (RULES.md): it is logged, summarised and shown to a person. It never
moves a price, never triggers a trade and is never executed.
"""
import re

REF = re.compile(r"\b([A-Z]{3})-(\d{2})\b")
PRICE = re.compile(r"(?<![\w#.-])(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:P|primas)\b")
VENUE = re.compile(r"\bv(\d{1,3})\b", re.I)
OFFER = re.compile(r"(?:#|\boffers?\s+#?)(\d{3,6})\b", re.I)
TEAM = re.compile(r"\bteam\s+(\d{1,2})\b|\bt(\d{2})\b", re.I)
CTRL = re.compile(r"[\x00-\x1f\x7f​-‏‪-‮⁦-⁩]")


def clean(text, n: int = 240) -> str:
    """One line, no control or direction-changing characters, cut to n characters: safe to print."""
    t = re.sub(r"\s+", " ", CTRL.sub(" ", str(text or ""))).strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def _uniq(items) -> list:
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def extract(text, me_id: str = "t09") -> dict:
    """Card refs, prices, venues, offer ids and team ids named in a text."""
    t = str(text or "")
    teams = []
    for a, b in TEAM.findall(t):
        n = a or b
        teams.append(f"t{int(n):02d}")
    return {"refs": _uniq(f"{a}-{b}" for a, b in REF.findall(t)),
            "prices": _uniq(float(p.replace(",", ".")) for p in PRICE.findall(t)),
            "venues": _uniq(f"v{int(v):02d}" for v in VENUE.findall(t)),
            "offers": _uniq(int(o) for o in OFFER.findall(t)),
            "teams": [x for x in _uniq(teams) if x != me_id]}


def classify(ex: dict, needs: set, spares: set, held: set, hands_off: set) -> dict:
    """level: LEAD-HANDSOFF (a card a person is buying), LEAD (a card we miss or hold a spare of), INFO (anything else).
    tags: for each named card, why it matters to us."""
    tags = {}
    for ref in ex["refs"]:
        if ref in hands_off:
            tags[ref] = "hands-off"
        elif ref in needs:
            tags[ref] = "we need it"
        elif ref in spares:
            tags[ref] = "we hold a spare"
        elif ref in held:
            tags[ref] = "we hold it"
    level = ("LEAD-HANDSOFF" if "hands-off" in tags.values() else
             "LEAD" if ("we need it" in tags.values() or "we hold a spare" in tags.values()) else "INFO")
    return {"level": level, "tags": tags}


def inbound(threads: list, me_id: str, seen: set) -> list:
    """New messages from other teams in team threads: [(thread, message)], oldest first. seen holds (thread id, message id)
    and is updated. Dealer threads are not read here."""
    out = []
    for t in threads:
        if t.get("kind") == "persona":
            continue
        for m in t.get("messages") or []:
            key = (t.get("id"), m.get("id"))
            if m.get("sender") == me_id or key in seen:
                continue
            seen.add(key)
            out.append((t, m))
    return sorted(out, key=lambda x: (x[1].get("tick") or 0, x[1].get("id") or 0))


def should_alert(last: dict, key, tick: int, msg_tick, max_age: int = 90, quiet: int = 100) -> bool:
    """Alert for a message only if it is recent (a restart or a first run must not replay old history) and the same sender
    has not already raised the same lead in the last `quiet` ticks (Team 13 sends near-identical messages by the dozen).
    `last` maps key -> tick of the last alert and is updated."""
    if msg_tick is None or tick - msg_tick > max_age:
        return False
    if key in last and tick - last[key] < quiet:
        return False
    last[key] = tick
    return True
