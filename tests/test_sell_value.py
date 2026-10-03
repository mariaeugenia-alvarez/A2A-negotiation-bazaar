"""A sale's floor comes from what we LOSE (the held asset's `your_value`, or Valuer.copy_value for a spare), never from
b.value(ref): /api/me/value is one MORE copy, about 25 % of a card we hold. Saturday 2026-10-03: RET-06 (worth 32.5 to
us) sold for 26 against a b.value of 8.1, and neg_points fell 19.1 -> 13.0. python3 tests/test_sell_value.py"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from bz.price import Valuer, sell_floor  # noqa: E402
from bz.trade import GameValues  # noqa: E402

# functions that price something we give away: none may call .value(...) (the one-more-copy value)
SELL_PATHS = {"agent.py": ["cmd_sell_spares"], "bz/trade.py": ["lose"], "bz/quotes.py": ["ask_price"]}


def calls_value(fn: ast.AST) -> list:
    return [n.lineno for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "value"]


def test_sell_paths_never_call_value():
    for path, names in SELL_PATHS.items():
        tree = ast.parse(open(os.path.join(ROOT, path), encoding="utf-8").read())
        found = {n.name: n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for name in names:
            assert name in found, f"{path}: {name} not found (renamed? update SELL_PATHS)"
            lines = calls_value(found[name])
            assert not lines, f"{path}:{lines}: {name} prices a sale with .value(), the value of one MORE copy"


def test_lose_reads_the_held_asset_not_the_api():
    class NoValue:  # a sale must not ask /api/me/value
        def value(self, ref):
            raise AssertionError(f"lose() asked b.value({ref!r})")
    held = [{"id": 1, "ref": "RET-06", "your_value": 32.5}]
    assert GameValues(NoValue(), held).lose(held[0]) == 32.5


def test_copy_value_is_what_we_lose_not_one_more():
    catalog = {"rarities": {"common": {"book": 10}}, "values": {"copy_marginals": [1.0, 0.25, 0.1]}, "packs": [],
               "sets": [{"id": "RET", "released": True, "cards": [{"id": f"RET-0{i}", "rarity": "common"} for i in range(1, 7)]}]}
    v = Valuer(catalog, {"RET": 1.0}, {"RET-06": 1})
    one_more, lose = v.card_value("RET-06"), v.copy_value("RET-06")
    assert lose == 4 * one_more, (lose, one_more)  # our only copy is worth 4x the next one
    assert sell_floor(lose) > sell_floor(one_more)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
