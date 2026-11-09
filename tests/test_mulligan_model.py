import math
from pathlib import Path

import numpy as np
import pytest

from solitaire_spy.mulligan import model

DECK = Path(__file__).parents[1] / "resources" / "stock_main_no_initiative.txt"


@pytest.fixture(scope="module")
def space():
    return model.HandSpace(model.load_decklist(DECK))


@pytest.fixture(scope="module")
def tags(space):
    return model.load_tags("/nonexistent", space)


def leaf(target, cmp=">=", value=1, metric="count"):
    return {"type": "count", "target": target, "metric": metric, "cmp": cmp, "value": value}


def rule(rid, decision, children, sizes=model.HAND_SIZES, modes=model.MODES, mode="all", include=(), exclude=()):
    return {"id": rid, "name": rid, "decision": decision, "enabled": True,
            "sizes": list(sizes), "modes": list(modes),
            "include": list(include), "exclude": list(exclude),
            "condition": {"type": "group", "mode": mode, "negate": False, "children": children}}


def hand_row(space, **cards):
    row = np.zeros(len(space.names), dtype=np.int8)
    for name, n in cards.items():
        row[space.index[name.replace("_", " ")]] = n
    return row


def test_deck_is_60_cards(space):
    assert space.deck_size == 60


def test_hands_are_seven_cards_unique_and_probabilities_sum_to_one(space):
    assert space.probs.sum() == pytest.approx(1.0)
    assert len({tuple(r) for r in space.hands}) == len(space.hands)
    assert (space.hands.sum(axis=1) == 7).all()


def test_single_hand_probability(space):
    row = hand_row(space, Forest=3, Swamp=1, Generous_Ent=3)
    i = np.flatnonzero((space.hands == row).all(axis=1))[0]
    expect = math.comb(3, 3) * math.comb(1, 1) * math.comb(4, 3) / math.comb(60, 7)
    assert space.probs[i] == pytest.approx(expect)


def test_land_count_matches_hypergeometric(space, tags):
    res = model.evaluate_scope(space, tags, [rule("a", "keep", [leaf("tag:land", "==", 0)])], 7, "play")
    assert space.probs[res.decision == 0].sum() == pytest.approx(math.comb(56, 7) / math.comb(60, 7))


def test_first_match_wins_and_conflict_detected(space, tags):
    rules = [rule("keep", "keep", [leaf("tag:land")]), rule("mull", "mull", [leaf("tag:land")])]
    s = model.summarize(space, tags, rules)["7:play"]
    assert s["mull"] == 0 and s["conflict"] == pytest.approx(s["keep"])
    assert s["rules"]["mull"]["captured"] == 0 and s["rules"]["mull"]["raw"] > 0


def test_scope_filters_size_and_mode(space, tags):
    rules = [rule("r", "mull", [], sizes=[6], modes=["draw"])]
    s = model.summarize(space, tags, rules)
    assert s["6:draw"]["undecided"] == pytest.approx(0)
    assert s["6:draw"]["covered_hands"] == len(space.hands)
    assert s["6:play"]["undecided"] == pytest.approx(1)
    assert s["7:draw"]["undecided"] == pytest.approx(1)
    assert s["6:play"]["rules"]["r"] is None


def test_distinct_metric_and_nested_not(space, tags):
    two_kinds = rule("d", "keep", [leaf("tag:mana_creature", ">=", 2, "distinct")])
    res = model.evaluate_scope(space, tags, [two_kinds], 7, "play")
    for h in np.flatnonzero(res.decision == 0)[:200]:
        names = [n for n, _ in space.hand_dict(space.hands[h]) if n in tags["mana_creature"]]
        assert len(names) >= 2
    neg = rule("n", "mull", [{"type": "group", "mode": "any", "negate": True, "children": [leaf("tag:land")]}])
    res = model.evaluate_scope(space, tags, [neg], 7, "play")
    assert space.probs[res.decision == 1].sum() == pytest.approx(math.comb(56, 7) / math.comb(60, 7))


def test_query_hands_undecided_sorted_and_has_filter(space, tags):
    out = model.query_hands(space, tags, [], 7, "play", "undecided", has=["Forest"], limit=10)
    ps = [h["p"] for h in out["hands"]]
    assert ps == sorted(ps, reverse=True)
    assert all(any(n == "Forest" for n, _ in h["cards"]) for h in out["hands"])


def test_validation_rejects_bad_rules():
    with pytest.raises(ValueError):
        model.validate_rules([rule("x", "maybe", [])])
    with pytest.raises(ValueError):
        model.validate_rules([rule("x", "keep", [leaf("land")])])
    with pytest.raises(ValueError):
        model.validate_rules([rule("x", "keep", []), rule("x", "mull", [])])


def test_legacy_bottom_and_zone_fields_are_ignored(space, tags):
    # rules saved while the bottom plan existed must still load and evaluate
    legacy = rule("old", "keep", [dict(leaf("tag:land"), zone="kept")])
    legacy["bottom"] = [{"target": "card:Lotleth Giant", "keep": 0}]
    model.validate_rules([legacy])
    s = model.summarize(space, tags, [legacy])["6:play"]
    assert s["covered_hands"] > 0 and "incomplete" not in s


# ---------------------------------------------------------------- must include / must not include

def test_include_and_exclude_lists(space, tags):
    r = rule("r", "keep", [],
             include=[{"target": "card:Forest", "min": 2}, {"target": "card:Generous Ent", "min": 1}],
             exclude=[{"target": "card:Lotleth Giant"}, {"target": "tag:spy"}])
    res = model.evaluate_scope(space, tags, [r], 7, "play")
    h = space.hands
    f, e = space.index["Forest"], space.index["Generous Ent"]
    g, s = space.index["Lotleth Giant"], space.index["Balustrade Spy"]
    expect = (h[:, f] >= 2) & (h[:, e] >= 1) & (h[:, g] == 0) & (h[:, s] == 0)
    assert expect.any()
    assert ((res.decision == 0) == expect).all()


def test_include_combines_with_condition(space, tags):
    r = rule("r", "keep", [leaf("tag:land", ">=", 3)], include=[{"target": "card:Swamp", "min": 1}])
    res = model.evaluate_scope(space, tags, [r], 7, "play")
    h = space.hands
    land = h[:, space.index["Forest"]] + h[:, space.index["Swamp"]]
    assert ((res.decision == 0) == ((land >= 3) & (h[:, space.index["Swamp"]] >= 1))).all()


def test_validation_rejects_bad_include():
    with pytest.raises(ValueError):
        model.validate_rules([rule("x", "keep", [], include=[{"target": "Forest", "min": 1}])])
    with pytest.raises(ValueError):
        model.validate_rules([rule("x", "keep", [], include=[{"target": "card:Forest", "min": 0}])])
