import logging
import random

from solitaire_spy.cards.creatures import *
from solitaire_spy.cards.mtg_cards import MTGLand
from solitaire_spy.cards.spells import *
from solitaire_spy.constants import *
from solitaire_spy.log import get_logger

log = get_logger(__name__, stdout_level=logging.WARNING)


class MtgEngine:
    def __init__(self, env):
        from solitaire_spy.spy_solitaire import MTGSolitaire  # avoids circular deps
        self.env: MTGSolitaire = env
        self.system_switch_mana_strategy_allowed = True
        self.passing = False  # if True, only instant speed interaction can be used
        # self.passing can be ~interpreted as "it's the opponent's turn" and shall be
        # used to (dis)allow instant-speed interaction for cards

    def is_action_possible(self, card, action):
        if "@" in action:  # action needs an indexed target
            action, target_index = action.split("@")
            action_method = action + "_available"
            return getattr(card, action_method)(self.env, target_index)
        else:
            action_method = action + "_available"
            return getattr(card, action_method)(self.env)

    def get_possible_actions(self):
        possible_actions = []
        possible_actions_cache = set()

        for zone, zone_name in [
            (self.env.hand, "hand"),
            (self.env.battlefield, "battlefield"),
            (self.env.lands, "lands"),
            (self.env.graveyard, "graveyard"),
        ]:
            for card in zone:
                for action in card.actions(self.env):
                    if self.is_action_possible(card, action):
                        # let's not add twice the same action... but redundant copies
                        # of Tinder Wall and Wall of Roots need to be treated separately
                        if (isinstance(card, TinderWall) or isinstance(card, WallOfRoots)) and "cast" not in action:
                            log.debug(f"Available action from {zone_name}: {card} -> {action}")
                            possible_actions.append((card, action))
                        else:
                            if f"{card}X{action}" in possible_actions_cache:
                                continue  # skip duplicate action
                            else:
                                possible_actions_cache.add(f"{card}X{action}")
                                log.debug(f"Available action from {zone_name}: {card} -> {action}")
                                possible_actions.append((card, action))

        different_mana_types_in_pool = sum(
            1 for t in self.env.mana_pool
            if self.env.mana_pool[t] > 1
        ) > 1
        if self.system_switch_mana_strategy_allowed and different_mana_types_in_pool:
            log.debug(f"Available system action: system_switch_mana_strategy")
            possible_actions.append((None, "system_switch_mana_strategy"))

        # probably best to keep these as last
        if not self.passing:
            log.debug(f"Available system action: system_pass")
            possible_actions.append((None, "system_pass"))
        else:
            log.debug(f"Available system action: system_start_new_turn")
            possible_actions.append((None, "system_start_new_turn"))
        return possible_actions

    def discard_card(self, card):
        self.env.hand.remove(card)
        self.env.graveyard.append(card)

    def draw_cards(self, num_cards):
        for _ in range(num_cards):
            try:
                card = self.env.library.pop(0)
                log.info(f"Drew {card}")
                self.env.hand.append(card)
            except IndexError:
                msg = "Lost by drawing from empty library"
                log.info(msg)
                raise GameLostException(msg)

    def get_dead_card_in_hand(self):
        dead_cards = [LotlethGiant, DreadReturn, MesmericFiend, MaskedVandal]
        for dead in dead_cards:  # Lotleth Giant always the first pick
            for card in self.env.hand:
                if isinstance(card, dead):
                    return card
        return None

    def get_worst_card_in_hand(self):
        dead_card = self.get_dead_card_in_hand()
        if dead_card:
            return dead_card
        try:
            return next(
                c for c in self.env.hand
                if not isinstance(c, MTGLand) and
                not isinstance(c, LandGrant) and
                not isinstance(c, GenerousEnt) and
                not isinstance(c, TrollOfKhazadDum) and
                not isinstance(c, SaguWildling) and
                not isinstance(c, WindingWay) and
                not isinstance(c, LeadTheStampede) and
                not isinstance(c, LotusPetal)
            )
        except StopIteration:
            return random.choice(self.env.hand)  # TODO: improve, if possible

    def system_pass(self):
        log.info("Passing")
        self.passing = True
        cards_to_discard = max(len(self.env.hand) - MTG_MAX_CARDS_IN_HAND, 0)
        for _ in range(cards_to_discard):
            self.put_from_hand_to_graveyard(self.get_worst_card_in_hand())

        for mana in self.env.mana_pool:
            self.env.mana_pool[mana] = 0
        for permanent in self.env.battlefield:
            permanent.ability_once_per_turn_activated = False

    def system_start_new_turn(self):
        self.passing = False
        self.env.counter_turn += 1
        for land in self.env.lands:
            land.is_tapped = False
        for mana in self.env.mana_pool:
            self.env.mana_pool[mana] = 0
        for permanent in self.env.battlefield:
            permanent.has_summoning_sickness = False
            permanent.is_tapped = False
            permanent.ability_once_per_turn_activated = False

        self.env.played_land_this_turn = False
        self.system_switch_mana_strategy_allowed = True
        self.draw_cards(1)

    def system_switch_mana_strategy(self):
        if self.env.mana_strategy == MANA_STRATEGY_SCRBG:
            self.env.mana_strategy = MANA_STRATEGY_SCRGB
        else:
            self.env.mana_strategy = MANA_STRATEGY_SCRBG
        log.info(f"Switching mana strategy to {self.env.mana_strategy}")
        # system_switch_mana_strategy will be re-enabled only after a mana-consuming
        # action (e.g. casting a spell or activating an ability)
        self.system_switch_mana_strategy_allowed = False

    def play_land(self, land):
        self.change_card_zone(land, self.env.hand, self.env.lands)

    def bounce_land_to_hand(self, land):
        land.is_tapped = False
        self.change_card_zone(land, self.env.lands, self.env.hand)

    def put_from_hand_to_battlefield(self, permanent):
        self.change_card_zone(permanent, self.env.hand, self.env.battlefield)

    def put_from_hand_to_graveyard(self, spell):
        self.change_card_zone(spell, self.env.hand, self.env.graveyard)

    def put_from_hand_to_library(self, card):
        self.change_card_zone(card, self.env.hand, self.env.library)

    def put_from_graveyard_to_battlefield(self, creature):
        self.change_card_zone(creature, self.env.graveyard, self.env.battlefield)
        creature.enters_the_battlefield(self.env)

    def add_mana(self, color, quantity):
        self.env.mana_pool[color] += quantity

    def sacrifice_creature(self, creature):
        creature.is_tapped = False
        creature.has_summoning_sickness = False
        creature.ability_once_per_turn_activated = False
        if isinstance(creature, WallOfRoots):
            creature.minus_counters = 0
        self.sacrifice_permanent(creature)

    def sacrifice_permanent(self, permanent):
        self.change_card_zone(permanent, self.env.battlefield, self.env.graveyard)
        if isinstance(permanent, EldraziSpawn):
            self.put_from_graveyard_to_exile(permanent)

    def put_from_graveyard_to_exile(self, card):
        self.change_card_zone(card, self.env.graveyard, self.env.exile)

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

class GameLostException(Exception):
    pass
