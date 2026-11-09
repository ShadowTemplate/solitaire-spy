"""Bootstrap resources/sideboard/matchups.json from the community sideboard sheet.

    python -m solitaire_spy.sideboard.bootstrap

Source: tab "4-land list (Geddon - 0LP3AM2FD2FM)" of
https://docs.google.com/spreadsheets/d/1uxYiWlNwzxCyzVcEL_-B1WD0LT-2BupbYDufa0BWmPQ/edit?gid=1601363831
snapshotted (raw cell values) in resources/sideboard/source_rows.json so no Google access is needed.

The sheet only says "N copies of X go out / in". Two things are inferred from that.

Post-board list ("target"): main - out + in, per card, for every matchup. It is stored on the matchup
and is what makes the implicit information usable for any deck list:
  * cut    = max(0, copies you play - target)  -> a sideboard card the sheet never brings in (e.g.
    Mesmeric Fiend) is cut when your main plays it;
  * bring in = max(0, target - copies you play) -> a main card the sheet keeps (e.g. Avenging Hunter)
    is brought in when your list lacks it.

Ranking (the order of the lists is the ranking):
  * OUT score = copies not in the target / copies of the card in main + sideboard. A card cut
    entirely is the clearest "useless here"; a 1-of trim is marginal.
  * IN: the sheet's explicit sideboard plan first (copies added / sideboard copies), then the cards the
    target keeps (main cards a deck might lack), then everything else.
  * Ties break on the card's popularity across all 38 matchups.
  * Entries the sheet moves explicitly have basis "sheet"; those that only follow from the target have
    basis "implied"; the rest are "inferred" fillers. Tail cards never cut in any matchup get basis
    "untouchable" (OUT only).
  * "Optional:" hints from the Notes column become "optional" entries ranked right after the sheet's.

The JSON is the source of truth afterwards: re-running this script overwrites manual
re-ordering, so it refuses to do so unless --force is given.
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "resources" / "sideboard" / "source_rows.json"
DEST = ROOT / "resources" / "sideboard" / "matchups.json"

SOURCE_URL = ("https://docs.google.com/spreadsheets/d/1uxYiWlNwzxCyzVcEL_-B1WD0LT-2BupbYDufa0BWmPQ"
              "/edit?gid=1601363831")
LAND_SYMBOLS = {"=": "same", "↔": "swap_forest_mountain", "+": "add_mountain"}
RENAMES = {"Gatecreeper Vines": "Gatecreeper Vine"}

# Manual ranking rule: whenever these cards are sided out, they are the first cards to cut, in this order.
FIRST_CUTS = ("Avenging Hunter", "Masked Vandal")

# "Optional:" hints from the Notes column, transcribed by hand (free text, only two rows).
OPTIONAL = {
    "Spy Walls": {"out": [("Wall of Roots", 1)], "in": [("Fang Dragon", 1)]},
    "Golgari Gardens": {"out": [("Saruli Caretaker", 1), ("Gatecreeper Vine", 1)],
                        "in": [("Accursed Marauder", 2)]},
}


def parse_cards(cell):
    """'4 Masked Vandal, 1 Forest' -> [('Masked Vandal', 4), ('Forest', 1)]."""
    cards = []
    for part in filter(None, (p.strip() for p in cell.split(","))):
        m = re.match(r"^(\d+)\s+(.+)$", part)
        if not m:
            raise ValueError(f"Cannot parse {part!r} in {cell!r}")
        name = m.group(2).strip()
        cards.append((RENAMES.get(name, name), int(m.group(1))))
    return cards


def parse_decklist(rows):
    """The sheet's own list lives in columns J/K (count, name): 60 main cards, then the sideboard."""
    entries = []
    for row in rows[2:]:
        if len(row) >= 10 and row[8].strip().isdigit() and row[9].strip():
            entries.append((RENAMES.get(row[9].strip(), row[9].strip()), int(row[8])))
    main, side, total = {}, {}, 0
    for name, n in entries:
        (main if total < 60 else side)[name] = n
        total += n
    return main, side


def parse_matchups(rows):
    out = []
    for row in rows[2:]:
        if len(row) < 5 or not row[2].strip() or row[1].strip() not in LAND_SYMBOLS:
            continue
        out.append({
            "name": row[2].strip(),
            "lands": LAND_SYMBOLS[row[1].strip()],
            "out": parse_cards(row[3]),
            "in": parse_cards(row[4]),
            "notes": row[6].strip() if len(row) > 6 else "",
        })
    return out


def popularity(matchups, side, pool):
    """Average over matchups of (copies moved / copies available) per card."""
    total = {}
    for m in matchups:
        for name, n in m[side]:
            total[name] = total.get(name, 0) + n / pool[name]
    return {name: v / len(matchups) for name, v in total.items()}


def target_counts(m, main, side):
    """The sheet's post-board list for a matchup: main - out + in, for every card of the pool."""
    target = {c: 0 for c in list(main) + list(side)}
    for c, n in main.items():
        target[c] += n
    for c, n in m["out"]:
        target[c] -= n
    for c, n in m["in"]:
        target[c] += n
    assert all(v >= 0 for v in target.values()), (m["name"], target)
    return target


def rank_out(m, optional, target, pool, pop, universe, untouchable):
    """Cut order. cut = copies of the card that are NOT in the post-board list; score = cut / pool."""
    explicit = dict(m["out"])
    cut = {c: pool[c] - target[c] for c in pool}
    entries, seen = [], set()
    for name in sorted((c for c in cut if cut[c] > 0), key=lambda c: (FIRST_CUTS.index(c) if c in FIRST_CUTS else len(FIRST_CUTS), -cut[c] / pool[c], -cut[c], -pop.get(c, 0), c)):
        # "sheet": the sheet cuts it explicitly; "implied": it is simply absent from the post-board list
        entries.append({"card": name, "copies": explicit.get(name, 0), "basis": "sheet" if name in explicit else "implied"})
        seen.add(name)
    for name, n in optional:
        if name not in seen:
            entries.append({"card": name, "copies": n, "basis": "optional"})
            seen.add(name)
    for name in sorted((c for c in universe if c not in seen), key=lambda c: (c in untouchable, -pop.get(c, 0), c)):
        # filler cards never cut in any matchup (sheet or optional note) are "untouchable"
        entries.append({"card": name, "copies": 0, "basis": "untouchable" if name in untouchable else "inferred"})
    return entries


def rank_in(m, optional, target, pool, side, pop):
    """Bring-in order: the sheet's explicit sideboard plan first, then the cards the post-board list
    keeps (main cards a deck might lack), then everything else."""
    explicit = dict(m["in"])
    entries, seen = [], set()
    for name in sorted(explicit, key=lambda c: (-explicit[c] / side[c], -explicit[c], -pop.get(c, 0), c)):
        entries.append({"card": name, "copies": explicit[name], "basis": "sheet"})
        seen.add(name)
    for name, n in optional:
        if name not in seen:
            entries.append({"card": name, "copies": n, "basis": "optional"})
            seen.add(name)
    kept = [c for c in pool if c not in seen and target[c] > 0]
    for name in sorted(kept, key=lambda c: (-target[c] / pool[c], -target[c], c)):
        entries.append({"card": name, "copies": 0, "basis": "implied"})
        seen.add(name)
    for name in sorted((c for c in pool if c not in seen), key=lambda c: (-pop.get(c, 0), c)):
        entries.append({"card": name, "copies": 0, "basis": "inferred"})
    return entries


def build():
    rows = json.loads(SRC.read_text())
    main, side = parse_decklist(rows)
    matchups = parse_matchups(rows)
    assert len(matchups) == 38, len(matchups)
    # copies that exist for a card across main + sideboard: the denominator of the scores
    pool = {c: main.get(c, 0) + side.get(c, 0) for c in list(main) + list(side)}
    targets = {m["name"]: target_counts(m, main, side) for m in matchups}
    cut_view = [{"out": [(c, pool[c] - targets[m["name"]][c]) for c in pool if pool[c] - targets[m["name"]][c] > 0]}
                for m in matchups]
    pop_out = popularity(cut_view, "out", pool)
    pop_in = popularity(matchups, "in", side)
    optional_out = {c for o in OPTIONAL.values() for c, _ in o["out"]}
    untouchable = set(main) - set(pop_out) - optional_out
    result = []
    for m in matchups:
        opt = OPTIONAL.get(m["name"], {"out": [], "in": []})
        target = targets[m["name"]]
        result.append({
            "id": re.sub(r"[^a-z0-9]+", "-", m["name"].lower()).strip("-"),
            "name": m["name"],
            "lands": m["lands"],
            "notes": m["notes"],
            "target": target,
            "out": rank_out(m, opt["out"], target, pool, pop_out, list(main), untouchable),
            "in": rank_in(m, opt["in"], target, pool, side, pop_in),
        })
    return {
        "version": 2,
        "source": {"url": SOURCE_URL, "tab": "4-land list (Geddon - 0LP3AM2FD2FM)"},
        "comment": ("target = copies of each card in the post-board list for the matchup; a deck cuts "
                    "max(0, have - target) and brings in max(0, target - have). 'out' is ordered from the "
                    "first card to cut to the last; 'in' from the first card to bring in to the last "
                    "(copies = explicit moves of the reference list, 0 = implied or filler). Re-order "
                    "freely (drag and drop in the dashboard); order is the ranking."),
        "reference_deck": {"main": main, "sideboard": side},
        "matchups": result,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="overwrite an existing matchups.json")
    args = ap.parse_args()
    if DEST.exists() and not args.force:
        raise SystemExit(f"{DEST} exists (it may hold manual re-ordering); pass --force to overwrite")
    data = build()
    DEST.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"Wrote {len(data['matchups'])} matchups to {DEST}")


if __name__ == "__main__":
    main()
