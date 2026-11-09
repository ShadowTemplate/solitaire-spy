"""Opening-hand enumeration and keep/mulligan rule evaluation.

Every scope evaluates the same space of 7-card opening hands (a multiset of cards, stored as a vector
of counts, one slot per distinct card name), each with its exact hypergeometric probability.
Coverage is exact, not sampled.  A scope is a kept hand size (7..2, i.e. 0..5 mulligans taken) plus
on the play / on the draw; "mull" at kept size N means "go down to N-1".  Which cards would be put on
the bottom when keeping fewer than 7 is deliberately not modelled.

A *rule* is: decision (keep/mull) + scope (kept sizes, modes) + requirements
(`include` / `exclude` card or tag lists) + an optional nested condition.  Rules are ordered; the first
enabled rule whose scope and requirements match a hand decides it.  The goal is to leave no hand undecided.
"""
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SEEN = 7  # cards seen in every opening hand
HAND_SIZES = (7, 6, 5, 4, 3, 2)  # kept hand sizes = scopes (mulligans taken: 0..5)
MODES = ("play", "draw")
DECISIONS = ("keep", "mull")
CMP_OPS = {
    ">=": np.greater_equal,
    "<=": np.less_equal,
    "==": np.equal,
    "!=": np.not_equal,
    ">": np.greater,
    "<": np.less,
}


# --------------------------------------------------------------------------- deck

def load_decklist(path):
    """Parse an `N Card Name` list. Stops at a Sideboard marker (sideboards are ignored)."""
    cards = []
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if re.match(r"(?i)^(sideboard|sb:)", line):
            break
        m = re.match(r"^(\d+)x?\s+(.+)$", line)
        if not m:
            raise ValueError(f"Cannot parse deck line: {raw!r}")
        name, n = m.group(2).strip(), int(m.group(1))
        for entry in cards:
            if entry[0] == name:
                entry[1] += n
                break
        else:
            cards.append([name, n])
    return [(n, c) for n, c in cards]


# --------------------------------------------------------------------------- hands

class HandSpace:
    """All distinct 7-card opening hands of the deck, with exact probabilities."""

    def __init__(self, deck):
        self.names = [n for n, _ in deck]
        self.copies = np.array([c for _, c in deck], dtype=np.int64)
        self.deck_size = int(self.copies.sum())
        self.index = {n: i for i, n in enumerate(self.names)}
        self.hands = self._enumerate()  # int8 (n_hands, n_cards)
        self.probs = self._probabilities(self.hands)  # float64 (n_hands,)

    def _enumerate(self):
        partial = np.zeros((1, len(self.names)), dtype=np.int8)
        used = np.zeros(1, dtype=np.int8)
        for i, copies in enumerate(self.copies):
            parts, uses = [], []
            for c in range(int(copies) + 1):
                keep = used + c <= SEEN
                if not keep.any():
                    break
                block = partial[keep].copy()
                block[:, i] = c
                parts.append(block)
                uses.append(used[keep] + c)
            partial = np.concatenate(parts)
            used = np.concatenate(uses)
        return partial[used == SEEN]

    def _probabilities(self, hands):
        ways = np.ones(len(hands), dtype=np.float64)
        for i, copies in enumerate(self.copies):
            table = np.array([math.comb(int(copies), c) for c in range(SEEN + 1)], dtype=np.float64)
            ways *= table[hands[:, i]]
        return ways / math.comb(self.deck_size, SEEN)

    def hand_dict(self, row):
        return [(self.names[i], int(c)) for i, c in enumerate(row) if c]


# --------------------------------------------------------------------------- tags

def resolve_target(space, tags, target):
    """`card:Name` or `tag:name` -> 0/1 membership vector over the deck's card slots."""
    kind, _, key = target.partition(":")
    vec = np.zeros(len(space.names), dtype=np.int16)
    if kind == "card" and key in space.index:
        vec[space.index[key]] = 1
    elif kind == "tag":
        for card in tags.get(key, []):
            if card in space.index:
                vec[space.index[card]] = 1
    return vec


# --------------------------------------------------------------------------- rules

def default_rule():
    return {
        "id": "", "name": "", "decision": "keep", "enabled": True, "note": "",
        "sizes": list(HAND_SIZES), "modes": list(MODES), "include": [], "exclude": [],
        "condition": {"type": "group", "mode": "all", "negate": False, "children": []},
    }


def validate_rules(rules):
    """Raise ValueError on structurally broken rules. Returns the rules unchanged."""
    seen = set()
    for r in rules:
        if not r.get("id") or r["id"] in seen:
            raise ValueError(f"Rule id missing or duplicated: {r.get('id')!r}")
        seen.add(r["id"])
        if r.get("decision") not in DECISIONS:
            raise ValueError(f"Rule {r['id']}: decision must be keep or mull")
        _validate_condition(r.get("condition"), r["id"])
        for item in list(r.get("include", [])) + list(r.get("exclude", [])):
            if not str(item.get("target", "")).startswith(("card:", "tag:")) or int(item.get("min", 1)) < 1:
                raise ValueError(f"Rule {r['id']}: bad include/exclude entry")
    return rules


def _validate_condition(node, rid):
    if not isinstance(node, dict):
        raise ValueError(f"Rule {rid}: bad condition")
    if node.get("type") == "group":
        if node.get("mode") not in ("all", "any"):
            raise ValueError(f"Rule {rid}: group mode must be all or any")
        for ch in node.get("children", []):
            _validate_condition(ch, rid)
    elif node.get("type") == "count":
        if node.get("cmp") not in CMP_OPS or node.get("metric", "count") not in ("count", "distinct"):
            raise ValueError(f"Rule {rid}: bad comparison")
        if not str(node.get("target", "")).startswith(("card:", "tag:")):
            raise ValueError(f"Rule {rid}: target must be card:<name> or tag:<name>")
        int(node.get("value"))
    else:
        raise ValueError(f"Rule {rid}: unknown condition type")


def requirements_mask(space, tags, hands, rule):
    """Hands that hold every `include` target (>= min copies) and none of the `exclude` targets."""
    ok = np.ones(len(hands), dtype=bool)
    for item in rule.get("include", []):
        ok &= (hands @ resolve_target(space, tags, item["target"])) >= int(item.get("min", 1))
    for item in rule.get("exclude", []):
        ok &= (hands @ resolve_target(space, tags, item["target"])) == 0
    return ok


def eval_condition(space, tags, hands, node, cache):
    if node["type"] == "group":
        masks = [eval_condition(space, tags, hands, ch, cache) for ch in node.get("children", [])]
        if node["mode"] == "all":
            out = np.logical_and.reduce(masks) if masks else np.ones(len(hands), dtype=bool)
        else:
            out = np.logical_or.reduce(masks) if masks else np.zeros(len(hands), dtype=bool)
        return ~out if node.get("negate") else out
    key = (node["target"], node.get("metric", "count"))
    if key not in cache:
        vec = resolve_target(space, tags, node["target"])
        if key[1] == "distinct":
            cache[key] = ((hands > 0) & (vec > 0)).sum(axis=1)
        else:
            cache[key] = hands @ vec
    return CMP_OPS[node["cmp"]](cache[key], int(node["value"]))


@dataclass
class ScopeResult:
    size: int
    mode: str
    decision: np.ndarray  # per hand: -1 undecided, 0 keep, 1 mull
    first: np.ndarray  # per hand: index of deciding rule, -1 if none
    matched: list  # per rule: bool mask (raw match, ignoring earlier rules); None if rule not in scope
    conflict: np.ndarray  # bool per hand: matched by both a keep and a mull rule


def evaluate_scope(space, tags, rules, size, mode):
    hands, n = space.hands, len(space.hands)
    decision = np.full(n, -1, dtype=np.int8)
    first = np.full(n, -1, dtype=np.int32)
    matched = []
    cache = {}
    any_keep = np.zeros(n, dtype=bool)
    any_mull = np.zeros(n, dtype=bool)
    for idx, rule in enumerate(rules):
        if not rule.get("enabled", True) or size not in rule["sizes"] or mode not in rule["modes"]:
            matched.append(None)
            continue
        mask = eval_condition(space, tags, hands, rule["condition"], cache) & requirements_mask(space, tags, hands, rule)
        matched.append(mask)
        (any_keep if rule["decision"] == "keep" else any_mull).__ior__(mask)
        take = mask & (first < 0)
        first[take] = idx
        decision[take] = DECISIONS.index(rule["decision"])
    return ScopeResult(size, mode, decision, first, matched, any_keep & any_mull)


def summarize(space, tags, rules):
    """Coverage stats for every (size, mode) scope. Probabilities are exact fractions."""
    out = {}
    p = space.probs
    for size in HAND_SIZES:
        for mode in MODES:
            res = evaluate_scope(space, tags, rules, size, mode)
            per_rule = {}
            for idx, rule in enumerate(rules):
                m = res.matched[idx]
                if m is None:
                    per_rule[rule["id"]] = None
                    continue
                cap = res.first == idx
                per_rule[rule["id"]] = {
                    "captured": float(p[cap].sum()), "captured_hands": int(cap.sum()),
                    "raw": float(p[m].sum()), "raw_hands": int(m.sum()),
                    "conflict": float(p[m & res.conflict].sum()),
                }
            out[f"{size}:{mode}"] = {
                "size": size, "mode": mode, "hands": len(p),
                "keep": float(p[res.decision == 0].sum()),
                "mull": float(p[res.decision == 1].sum()),
                "undecided": float(p[res.decision == -1].sum()),
                "undecided_hands": int((res.decision == -1).sum()),
                "covered_hands": int((res.decision >= 0).sum()),
                "conflict": float(p[res.conflict].sum()),
                "rules": per_rule,
            }
    return out


def query_hands(space, tags, rules, size, mode, flt="undecided", has=(), offset=0, limit=50):
    """Page through the 7-card hands of one scope, most probable first.

    flt: all | undecided | keep | mull | conflict | rule:<id> (decided by it) | matched:<id>
    has: card names that must each be present at least once.
    """
    res = evaluate_scope(space, tags, rules, size, mode)
    hands, p = space.hands, space.probs
    ids = [r["id"] for r in rules]
    if flt == "all":
        mask = np.ones(len(p), dtype=bool)
    elif flt == "undecided":
        mask = res.decision == -1
    elif flt in DECISIONS:
        mask = res.decision == DECISIONS.index(flt)
    elif flt == "conflict":
        mask = res.conflict
    elif flt.startswith(("rule:", "matched:")):
        kind, _, rid = flt.partition(":")
        if rid not in ids:
            raise ValueError(f"Unknown rule {rid}")
        i = ids.index(rid)
        if kind == "rule":
            mask = res.first == i
        else:
            mask = res.matched[i] if res.matched[i] is not None else np.zeros(len(p), dtype=bool)
    else:
        raise ValueError(f"Unknown filter {flt}")
    for name in has:
        if name in space.index:
            mask = mask & (hands[:, space.index[name]] > 0)
    sel = np.flatnonzero(mask)
    sel = sel[np.argsort(-p[sel], kind="stable")]
    page = sel[offset:offset + limit]
    rows = []
    for h in page:
        fi = int(res.first[h])
        rows.append({
            "cards": space.hand_dict(hands[h]),
            "p": float(p[h]),
            "decision": None if res.decision[h] < 0 else DECISIONS[res.decision[h]],
            "rule": ids[fi] if fi >= 0 else None,
            "matched": [ids[i] for i, m in enumerate(res.matched) if m is not None and m[h]],
        })
    return {"total": int(len(sel)), "mass": float(p[sel].sum()), "hands": rows}


# --------------------------------------------------------------------------- persistence

DEFAULT_TAGS = {
    "land": ["Forest", "Swamp"],
    "basic_land": ["Forest", "Swamp"],
    "forest": ["Forest"],
    "swamp": ["Swamp"],
    "land_finder": ["Land Grant", "Generous Ent", "Sagu Wildling", "Gatecreeper Vine"],
    "mana_creature": ["Elves of Deep Shadow", "Overgrown Battlement", "Saruli Caretaker", "Wall of Roots"],
    "black_source": ["Swamp", "Elves of Deep Shadow"],
    "selection": ["Winding Way", "Lead the Stampede"],
    "spy": ["Balustrade Spy"],
    "dread_return": ["Dread Return"],
    "giant": ["Lotleth Giant"],
    "payoff": ["Balustrade Spy", "Dread Return", "Lotleth Giant"],
}


def load_tags(path, space):
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text())
    # decks differ in capitalisation ("Lead The Stampede"), so match card names case-insensitively
    lower = {n.lower(): n for n in space.names}
    tags = {t: [lower[c.lower()] for c in cs if c.lower() in lower] for t, cs in DEFAULT_TAGS.items()}
    return {t: cs for t, cs in tags.items() if cs}


def save_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(p)
