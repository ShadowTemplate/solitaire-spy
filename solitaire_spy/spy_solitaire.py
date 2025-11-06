import logging
import random

from solitaire_spy.cards.mtg_cards import MTGLand
from solitaire_spy.constants import *
from solitaire_spy.log import get_logger
from solitaire_spy.mtg_engine import MtgEngine
from solitaire_spy.spy_gui import ImageGridApp

log = get_logger(stdout_level=logging.INFO)


class MTGSolitaire:
    def __init__(self, deck, tk_root):
        log.debug("*** init ***")
        self.engine = MtgEngine(self)
        self.library = deck
        self.lands_in_deck = sum(isinstance(c, MTGLand) for c in deck)
        while True:
            random.shuffle(self.library)
            # uncomment to force certain hands
            # if any(isinstance(c, MTGLand) for c in self.library[:7]) and any(isinstance(c, BalustradeSpy) for c in self.library[:7]):
            # if any(isinstance(c, MTGLand) for c in self.library[:7]):
            #     continue
            break
        self.hand = []
        self.engine.draw_cards(7)
        self.lands = []
        self.battlefield = []
        self.graveyard = []
        self.exile = []
        self.mana_pool = {m: 0 for m in MANA_TYPES}
        self.counter_turn = 1
        self.counter_life = STARTING_LIFE
        self.opponent_counter_life = STARTING_LIFE
        self.played_land_this_turn = False
        self.known_lands_bottom = 0
        self.mana_strategy = MANA_STRATEGY_SCRBG
        self.steps_log = []
        self.kept_at = 7

        self.tk_root = tk_root
        self.gui_battlefield = None
        self.gui_lands = None
        self.gui_hand = None
        self.gui_graveyard = None
        self.gui_exile = None
        self.gui_mana_pool = None

        if tk_root:
            self.gui_battlefield = ImageGridApp(
                self.tk_root, "Battlefield", self.battlefield, columns=10
            )
            self.gui_lands = ImageGridApp(
                self.tk_root, "Lands", self.lands, columns=10
            )
            self.gui_hand = ImageGridApp(
                self.tk_root, "Hand", self.hand, columns=10
            )
            self.gui_graveyard = ImageGridApp(
                self.tk_root, "Graveyard", self.graveyard, columns=10
            )
            self.gui_exile = ImageGridApp(
                self.tk_root, "Exile", self.exile, columns=10
            )
            self.gui_mana_pool = ImageGridApp(
                self.tk_root, "Mana pool", self.mana_pool, columns=len(self.mana_pool)
            )
        self.render()

    def step(self, card, action):
        log.debug("*** step ***")
        self.steps_log.append((card, action))
        if action.startswith("system_"):
            getattr(self.engine, action)()
        elif "@" in action:  # action needs an indexed target
            action, target_index = action.split("@")
            getattr(card, action)(self, target_index)
        else:
            getattr(card, action)(self)

    def render(self):
        log.debug("*** render ***")
        log.info(f"Turn: {self.counter_turn}, Library: {len(self.library)}, Life: {self.counter_life}")
        log.info(f"Hand: {len(self.hand)} {self.hand}")
        log.info(f"Battlefield: {len(self.battlefield)} {self.battlefield}")
        log.info(f"Lands: {len(self.lands)} {self.lands}")
        log.info(f"Graveyard: {len(self.graveyard)} {self.graveyard}")
        log.info(f"Exile: {len(self.exile)} {self.exile}")
        log.info(f"Mana pool: {[f'{i} {self.mana_pool[i]}' for i in MANA_TYPES]}")
        if not self.tk_root:
            return
        # update GUI
        if not self.engine.passing:
            self.tk_root.title(
                f"MTGO at home | "
                f"Turn {self.counter_turn} (mine) | "
                f"Life {self.counter_life} vs {self.opponent_counter_life}"
            )
        else:
            self.tk_root.title(
                f"MTGO at home | "
                f"Turn {self.counter_turn} (opponent) | "
                f"Life {self.counter_life} vs {self.opponent_counter_life}"
            )
        self.gui_battlefield.load_images(self)
        self.gui_lands.load_images(self)
        self.gui_hand.load_images(self)
        self.gui_graveyard.load_images(self)
        self.gui_exile.load_images(self)
        self.gui_mana_pool.load_images(self)

    @property
    def functional_hash(self):
        # same number of cards left in library
        h = "D|"
        h += str(len(self.library))
        # same lands in library
        h += "|LL|"
        h += ",".join(sorted(c.name for c in self.library if isinstance(c, MTGLand)))
        # same cards in hand
        h += "|H|"
        h += ",".join(sorted(c.name for c in self.hand))
        # same lands in play and same tapped status
        h += "|LP|"
        h += ",".join(sorted(c.functional_hash for c in self.lands))
        # same battlefield
        h += "|B|"
        h += ",".join(sorted(c.functional_hash for c in self.battlefield))
        # same graveyard
        h += "|G|"
        h += ",".join(sorted(c.name for c in self.graveyard))
        # same exile
        h += "|E|"
        h += ",".join(sorted(c.name for c in self.exile))
        # same mana pool
        h += "|M|"
        h += str(self.mana_pool)
        # same counter turn
        h += "|T|"
        h += str(self.counter_turn)
        # same opponent life
        h += "|OL|"
        h += str(self.opponent_counter_life)
        # same played land this turn
        h += "|PL|"
        h += str(self.played_land_this_turn)
        # same known lands on the bottom
        h += "|KL|"
        h += str(self.known_lands_bottom)
        # same mana strategy
        h += "|MS|"
        h += self.mana_strategy
        return h
