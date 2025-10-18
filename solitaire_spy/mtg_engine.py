import random

from solitaire_spy.constants import MANA_STRATEGY_SCRBG, MANA_STRATEGY_SCRGB, \
    MANA_TYPES, MTG_MAX_CARDS_IN_HAND


class MtgEngine:
    def __init__(self, env):
        from solitaire_spy.mtg_env import MTGSolitaire  # here to avoid circular deps
        self.env: MTGSolitaire = env
        self.system_switch_mana_strategy_allowed = True

    def is_action_possible(self, card, action):
        if "@" in action:  # action needs an indexed target
            action, target_index = action.split("@")
            action_method = action + "_available"
            return getattr(card, action_method)(self.env, int(target_index))
        else:
            action_method = action + "_available"
            return getattr(card, action_method)(self.env)

    def get_possible_actions(self):
        possible_actions = []

        for zone, zone_name in [
            (self.env.hand, "hand"),
            (self.env.battlefield, "battlefield"),
            (self.env.lands, "lands"),
            (self.env.graveyard, "graveyard"),
        ]:
            for card in zone:
                for action in card.actions(self.env):
                    if self.is_action_possible(card, action):
                        print(f"Available action from {zone_name}: {card} -> {action}")
                        possible_actions.append((card, action))

        if self.system_switch_mana_strategy_allowed:
            print(f"Available system action: system_switch_mana_strategy")
            possible_actions.append((None, "system_switch_mana_strategy"))

        print(f"Available system action: system_pass")
        possible_actions.append((None, "system_pass"))  # probably best to keep as last
        return possible_actions

    def discard_card(self, card):
        self.env.hand.remove(card)
        self.env.graveyard.append(card)

    def draw_cards(self, num_cards):
        for _ in range(num_cards):
            try:
                card = self.env.library.pop(0)
                print(f"Drew {card}")
                self.env.hand.append(card)
            except IndexError:
                print(f"ERROR: lost by drawing from empty library")
                raise

    def system_pass(self):
        print("Passing")
        cards_to_discard = max(len(self.env.hand) - MTG_MAX_CARDS_IN_HAND, 0)
        # TODO: discard to hand size
        if cards_to_discard > 0:
            raise ValueError("Discard to hand size not implemented yet")

        for mana in self.env.mana_pool:
            self.env.mana_pool[mana] = 0
        self.env.counter_turn += 1

        for land in self.env.lands:
            land.is_tapped = False
        for permanent in self.env.battlefield:
            permanent.has_summoning_sickness = False
            permanent.is_tapped = False

        self.env.played_land_this_turn = False
        self.system_switch_mana_strategy_allowed = True
        self.draw_cards(1)
        # TODO: handle instant speed plays during opponent's turn

    def system_switch_mana_strategy(self):
        if self.env.mana_strategy == MANA_STRATEGY_SCRBG:
            self.env.mana_strategy = MANA_STRATEGY_SCRGB
        else:
            self.env.mana_strategy = MANA_STRATEGY_SCRBG
        print(f"Switching mana strategy to {self.env.mana_strategy}")
        # system_switch_mana_strategy will be re-enabled only after a mana-consuming
        # action (e.g. casting a spell or activating an ability)
        self.system_switch_mana_strategy_allowed = False

    def play_land(self, land):
        self.change_card_zone(land, self.env.hand, self.env.lands)

    def put_from_hand_to_battlefield(self, creature):
        self.change_card_zone(creature, self.env.hand, self.env.battlefield)

    def put_from_hand_to_graveyard(self, spell):
        self.change_card_zone(spell, self.env.hand, self.env.graveyard)

    def put_from_hand_to_library(self, card):
        self.change_card_zone(card, self.env.hand, self.env.library)

    def add_mana(self, color, quantity):
        self.env.mana_pool[color] += quantity

    def sacrifice_creature(self, creature):
        self.change_card_zone(creature, self.env.battlefield, self.env.graveyard)

    @staticmethod
    def change_card_zone(card, from_zone, to_zone):
        from_zone.remove(card)
        to_zone.append(card)

    def pay_mana(self, mana_cost_map):
        # pay color-specific mana
        for specific_mana in MANA_TYPES[:-1]:
            self.env.mana_pool[specific_mana] -= mana_cost_map[specific_mana]

        # pay generic mana
        mana_to_pay = mana_cost_map["C"]
        for color in self.env.mana_strategy:
            if mana_to_pay > 0:
                mana_to_pay = self._spend_mana_to_pay(color, mana_to_pay)

        self.system_switch_mana_strategy_allowed = True

        if mana_to_pay > 0:
            raise ValueError(f"You are cheating: you can't pay {mana_to_pay} mana!")

    def _spend_mana_to_pay(self, color, generic_mana_to_pay):
        if self.env.mana_pool[color] >= generic_mana_to_pay:
            self.env.mana_pool[color] -= generic_mana_to_pay
            return 0
        else:
            generic_mana_to_pay -= self.env.mana_pool[color]
            self.env.mana_pool[color] = 0
            return generic_mana_to_pay

    def search_library_for(self, card_name):
        for i in range(len(self.env.library)):
            if self.env.library[i].name == card_name:
                self.change_card_zone(self.env.library[i], self.env.library, self.env.hand)
                break

    def shuffle_library(self):
        random.shuffle(self.env.library)
        self.env.known_lands_bottom = 0
