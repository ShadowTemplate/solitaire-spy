import copy
import json
import tempfile
import unittest
from pathlib import Path

from solitaire_spy.sideboard import bootstrap, server


class BootstrapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = bootstrap.build()

    def test_parse_cards(self):
        self.assertEqual(bootstrap.parse_cards("4 Masked Vandal, 1 Gatecreeper Vines"),
                         [("Masked Vandal", 4), ("Gatecreeper Vine", 1)])

    def test_reference_deck_is_60_plus_15(self):
        ref = self.doc["reference_deck"]
        self.assertEqual(sum(ref["main"].values()), 60)
        self.assertEqual(sum(ref["sideboard"].values()), 15)

    def test_every_matchup_ranks_the_whole_pool_once(self):
        ref = self.doc["reference_deck"]
        for m in self.doc["matchups"]:
            # both lists rank the whole pool (main + sideboard) exactly once, and the target covers it
            pool = set(ref["main"]) | set(ref["sideboard"])
            for side in ("out", "in"):
                cards = [e["card"] for e in m[side]]
                self.assertEqual(len(cards), len(set(cards)), m["name"])
            # OUT: every main card, plus the sideboard cards that are not fully brought in
            self.assertTrue(set(ref["main"]) <= {e["card"] for e in m["out"]} <= pool, m["name"])
            self.assertEqual({e["card"] for e in m["in"]}, pool, m["name"])
            self.assertEqual(set(m["target"]), pool, m["name"])

    def test_sheet_entries_come_first_and_keep_their_copies(self):
        m = next(m for m in self.doc["matchups"] if m["name"] == "MonoU Terror")
        out = [(e["card"], e["copies"]) for e in m["out"] if e["basis"] == "sheet"]
        self.assertEqual(out, [("Avenging Hunter", 3), ("Masked Vandal", 4), ("Wall of Roots", 2), ("Saruli Caretaker", 1)])
        tiers = [("sheet" if e["basis"] == "implied" else e["basis"]) for e in m["out"]]
        self.assertEqual(tiers, sorted(tiers, key=("sheet", "optional", "inferred", "untouchable").index))

    def test_target_is_the_post_board_list(self):
        by = {m["name"]: m["target"] for m in self.doc["matchups"]}
        # Madness: -3 Hunter +3 Marauder; Fiend stays at the single main copy (sideboard copies unused)
        self.assertEqual((by["MonoR Madness"]["Avenging Hunter"], by["MonoR Madness"]["Accursed Marauder"],
                          by["MonoR Madness"]["Mesmeric Fiend"]), (0, 3, 1))
        self.assertEqual(by["MonoU Terror"]["Mesmeric Fiend"], 4)     # all 3 sideboard copies come in
        self.assertEqual(by["MonoR Rally"]["Mesmeric Fiend"], 0)      # the main copy is cut and none come in
        self.assertEqual(by["Gruul Ramp"]["Accursed Marauder"], 1)    # partial bring-in
        self.assertEqual(by["Jund Wildfire"]["Avenging Hunter"], 3)   # kept: a deck lacking it should add it
        for name, t in by.items():
            self.assertEqual(sum(t.values()), 60, name)  # the sheet's swaps are balanced

    def test_deck_diff_against_target(self):
        # a deck that mains Fiend x4 and has no Hunter: cut/bring-in = distance to the target
        m = next(m for m in self.doc["matchups"] if m["name"] == "MonoR Madness")
        deck = {"Mesmeric Fiend": 4, "Masked Vandal": 4}
        cut = {c: deck[c] - m["target"][c] for c in deck if deck[c] > m["target"][c]}
        self.assertEqual(cut, {"Mesmeric Fiend": 3})                   # first card to cut, as expected
        m = next(m for m in self.doc["matchups"] if m["name"] == "Jund Wildfire")
        add = {c: m["target"][c] - deck.get(c, 0) for c in ("Avenging Hunter", "Mountain") if m["target"][c] > deck.get(c, 0)}
        self.assertEqual(add, {"Avenging Hunter": 3, "Mountain": 1})

    def test_vandal_then_hunter_are_the_first_cuts_when_sided_out(self):
        committed = json.loads(bootstrap.DEST.read_text())
        for doc in (self.doc, committed):
            ref = doc["reference_deck"]["main"]
            for m in doc["matchups"]:
                expected = [c for c in bootstrap.FIRST_CUTS if m["target"][c] < ref[c]]
                self.assertEqual([e["card"] for e in m["out"][:len(expected)]], expected, m["name"])
            self.assertTrue(any(m["target"]["Avenging Hunter"] < ref["Avenging Hunter"] for m in doc["matchups"]))

    def test_untouchables_are_never_cut_anywhere_and_come_last(self):
        cut = {e["card"] for m in self.doc["matchups"] for e in m["out"] if e["basis"] in ("sheet", "optional")}
        for m in self.doc["matchups"]:
            untouchable = {e["card"] for e in m["out"] if e["basis"] == "untouchable"}
            self.assertTrue(untouchable and not untouchable & cut, m["name"])
            self.assertTrue(all(e["basis"] != "untouchable" for e in m["in"]))
        self.assertIn("Balustrade Spy", untouchable)
        self.assertNotIn("Masked Vandal", untouchable)

    def test_optional_notes(self):
        m = next(m for m in self.doc["matchups"] if m["name"] == "Spy Walls")
        self.assertIn(("Fang Dragon", "optional"), [(e["card"], e["basis"]) for e in m["in"]])

    def test_committed_json_matches_a_fresh_bootstrap(self):
        # guards against the script and the shipped file drifting apart (before manual re-ordering)
        committed = json.loads(bootstrap.DEST.read_text())
        self.assertEqual([m["id"] for m in committed["matchups"]], [m["id"] for m in self.doc["matchups"]])


class ServerTest(unittest.TestCase):
    def test_load_decklist_with_sideboard(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.txt"
            p.write_text("4 Forest\n2 Lead The Stampede\n\nSideboard\n3 Fang Dragon\n")
            deck = server.load_decklist(p)
            self.assertEqual(deck["main"], [{"name": "Forest", "count": 4}, {"name": "Lead The Stampede", "count": 2}])
            self.assertEqual(deck["sideboard"], [{"name": "Fang Dragon", "count": 3}])

    def test_blank_line_sideboard_and_split_cards(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.txt"
            p.write_text("4 Sagu Wildling // Roost Seek\n3 Forest\n\n3 Fang Dragon // Forktail Sweep\n1 Mountain")
            deck = server.load_decklist(p)
            self.assertEqual(deck["main"], [{"name": "Sagu Wildling", "count": 4}, {"name": "Forest", "count": 3}])
            self.assertEqual(deck["sideboard"], [{"name": "Fang Dragon", "count": 3}, {"name": "Mountain", "count": 1}])

    def test_default_deck_parses(self):
        deck = server.load_decklist(server.DECK_DIR / "stock_main_no_initiative.txt")
        self.assertEqual(sum(c["count"] for c in deck["main"]), 60)

    def test_validate_matchups(self):
        prev = json.loads(server.MATCHUPS.read_text())
        server.validate_matchups(prev, prev)
        bad = copy.deepcopy(prev)
        bad["matchups"][0]["out"].append(dict(bad["matchups"][0]["out"][0]))  # duplicate card
        with self.assertRaises(ValueError):
            server.validate_matchups(bad, prev)
        bad = copy.deepcopy(prev)
        bad["matchups"].pop()
        with self.assertRaises(ValueError):
            server.validate_matchups(bad, prev)
        bad = copy.deepcopy(prev)
        bad["matchups"][0]["in"][0]["basis"] = "magic"
        with self.assertRaises(ValueError):
            server.validate_matchups(bad, prev)


if __name__ == "__main__":
    unittest.main()
