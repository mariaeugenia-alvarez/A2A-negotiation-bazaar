"""The duel texts: every one carries the price (and the day when the duel has days), never our limit or weight, never
'last/final' except the last call, in Spanish and English. python3 tests/test_duel_texts.py"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("BAZAAR_KEY", "x")
from duels import TEXTS, offer_text, stage_of  # noqa: E402

checks = 0
for stage in ("opening", "counter", "last_call"):
    for price in (1, 9, 58, 129, 1000):
        for day in (None, 0, 3, 10):
            t = offer_text(stage, price, day)
            assert re.search(rf"(?<!\\d){price}(?!\\d) P", t), (stage, price, day, t)               # the price, in both languages
            assert t.count(f"{price} P") == 2, t                                            # once in Spanish, once in English
            if day is not None:
                assert f"día {day}" in t and f"day {day}" in t, (stage, day, t)             # the day, in both languages
            else:
                assert not re.search(r"\\bdía \\d|\\bday \\d", t), t                           # no day in a price-only duel
            assert " / " in t and len(t) <= 160, t                                          # Spanish / English, short
            low = t.lower()
            for bad in ("límite", "limit", "peso", "weight", "mínimo", "minimum", "bottom"):
                assert bad not in low, (bad, t)
            if stage != "last_call":
                for bad in ("última", "último", "final", "last", "mejor oferta", "best offer", "take it"):
                    assert bad not in low, (bad, t)
            checks += 1
# the last call, and only it, says "best offer"
assert "Mi mejor oferta" in offer_text("last_call", 70, 4) and "My best offer" in offer_text("last_call", 70, 4)
assert "mejor oferta" not in offer_text("opening", 70, 4).lower() and "mejor oferta" not in offer_text("counter", 70, 4).lower()
# the exact texts approved by Thameur
assert offer_text("opening", 96, 5) == ("Rápido y justo: 96 P, día 5. ¿Qué día de entrega te va mejor? / "
                                        "Quick and fair: 96 P, day 5. Which delivery day suits you best?")
assert offer_text("counter", 80, 3) == "Parece que el día te importa: 80 P con día 3. / It seems the day matters to you: 80 P, day 3."
assert offer_text("last_call", 74, 2) == "Mi mejor oferta: 74 P, día 2. / My best offer: 74 P, day 2."
# an unknown stage never crashes: it is read as a counter
assert "Parece que" in offer_text("whatever", 50, 1)
# v2 names the stage; v1 does not (first offer = opening)
assert stage_of({"stage": "last_call"}) == "last_call" and stage_of({"k": 0}) == "opening" and stage_of({"k": 2}) == "counter"
assert len(TEXTS) == 6
checks += 6
print(f"test_duel_texts: {checks} checks passed")
