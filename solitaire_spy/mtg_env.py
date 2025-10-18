import random

from solitaire_spy.constants import MANA_TYPES, STARTING_LIFE, MANA_STRATEGY_SCRBG
from solitaire_spy.mtg_engine import MtgEngine
from solitaire_spy.spy_gui import ImageGridApp


class MTGSolitaire:
    def __init__(self, deck, tk_root):
        print("*** init ***")
        self.engine = MtgEngine(self)
        self.library = deck
        # random.shuffle(self.library)
        self.hand = []
        self.engine.draw_cards(7)
        self.lands = []
        self.battlefield = []
        self.graveyard = []
        self.mana_pool = {m: 0 for m in MANA_TYPES}
        self.counter_turn = 1
        self.counter_life = STARTING_LIFE
        self.played_land_this_turn = False
        self.tk_root = tk_root
        self.known_lands_bottom = 0
        self.gui_battlefield = ImageGridApp(self.tk_root, "Battlefield", self.battlefield, columns=10)
        self.gui_lands = ImageGridApp(self.tk_root, "Lands", self.lands, columns=10)
        self.gui_hand = ImageGridApp(self.tk_root, "Hand", self.hand, columns=10)
        self.gui_graveyard = ImageGridApp(self.tk_root, "Graveyard", self.graveyard, columns=10)
        self.gui_mana_pool = ImageGridApp(self.tk_root, "Mana pool", self.mana_pool, columns=len(self.mana_pool))
        self.mana_strategy = MANA_STRATEGY_SCRBG
        self.render()

    def step(self, card, action):
        print("*** step ***")
        if action.startswith("system_"):
            getattr(self.engine, action)()
        elif "@" in action:  # action needs an indexed target
            action, target_index = action.split("@")
            getattr(card, action)(self, int(target_index))
        else:
            getattr(card, action)(self)

    def render(self):
        print("*** render ***")
        print(f"Turn: {self.counter_turn}, Library: {len(self.library)}, Life: {self.counter_life}")
        print(f"Hand: {len(self.hand)} {self.hand}")
        print(f"Battlefield: {len(self.battlefield)} {self.battlefield}")
        print(f"Lands: {len(self.lands)} {self.lands}")
        print(f"Graveyard: {len(self.graveyard)} {self.graveyard}")
        print(f"Mana pool: {[f'{i} {self.mana_pool[i]}' for i in MANA_TYPES]}")
        self.tk_root.title(f"MTGO at home - Turn {self.counter_turn} - Life {self.counter_life}")
        self.gui_battlefield.load_images(self)
        self.gui_lands.load_images(self)
        self.gui_hand.load_images(self)
        self.gui_graveyard.load_images(self)
        self.gui_mana_pool.load_images(self)
