import logging
from abc import ABC, abstractmethod

from solitaire_spy.constants import MANA_TYPES
from solitaire_spy.log import get_logger

log = get_logger(__name__, stdout_level=logging.WARNING)


class MTGCard(ABC):
    def __init__(self, name, mana_cost):
        self.name = name
        self.mana_cost: str = mana_cost
        self.is_tapped = False
        self.has_summoning_sickness = False
        self.is_defender = False
        self.ability_once_per_turn_activated = False

    @abstractmethod
    def actions(self, env):
        pass

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def __hash__(self):
        return id(self)

    @property
    def functional_hash(self):
        return self.name + str(self.is_tapped) + str(self.has_summoning_sickness) + str(self.ability_once_per_turn_activated)

    @property
    def mana_cost_map(self):
        mana_cost_map = {t: self.mana_cost.count(t) for t in MANA_TYPES}
        try:
            mana_cost_map["C"] = int(''.join(filter(str.isdigit, self.mana_cost)))
        except ValueError:
            pass  # no generic cost
        return mana_cost_map


class MTGLand(MTGCard):
    def actions(self, env):
        return ["play"]

    @abstractmethod
    def play(self, env):
        log.info(f"Playing {self}")
        env.played_land_this_turn = True
        env.engine.play_land(self)

    def play_available(self, env):
        return self in env.hand and not env.played_land_this_turn and not env.engine.passing

    def tap_for_mana(self, env):
        log.info(f"Tapping for mana {self}")
        self.is_tapped = True

    def tap_for_mana_available(self, env):
        return self in env.lands and not self.is_tapped


class MTGSpell(MTGCard):
    def __init__(self, name, mana_cost, can_be_cast_for_black):
        super().__init__(name, mana_cost)
        self.can_be_cast_for_black = can_be_cast_for_black

    def actions(self, env):
        return ["cast"]

    @abstractmethod
    def cast(self, env):
        log.info(f"Casting {self}")
        env.engine.pay_mana(self.mana_cost_map)

    def cast_available(self, env):
        if self not in env.hand:
            return False

        all_mana_available = sum(env.mana_pool.values())

        # check if enough color-specific mana is available
        for specific_mana in MANA_TYPES[:-1]:
            if env.mana_pool[specific_mana] < self.mana_cost_map[specific_mana]:
                return False
            all_mana_available -= self.mana_cost_map[specific_mana]

        # check if enough generic mana is available
        return all_mana_available >= self.mana_cost_map['C']


class MTGCreatureSpell(MTGSpell):
    def __init__(self, name, mana_cost, can_be_cast_for_black, is_defender):
        MTGSpell.__init__(self, name, mana_cost, can_be_cast_for_black)
        self.is_defender = is_defender

    def cast(self, env):
        super().cast(env)
        env.engine.put_from_hand_to_battlefield(self)
        self.enters_the_battlefield(env)

    def cast_available(self, env):
        return super().cast_available(env) and not env.engine.passing

    @abstractmethod
    def enters_the_battlefield(self, env):
        log.info(f"Enters the battlefield {self}")
        self.has_summoning_sickness = True
