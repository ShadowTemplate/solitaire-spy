from abc import ABC, abstractmethod

from solitaire_spy.constants import MANA_TYPES


class MTGCard(ABC):
    def __init__(self, name, mana_cost):
        self.name = name
        self.mana_cost: str = mana_cost
        self.is_tapped = False
        self.has_summoning_sickness = False
        self.is_defender = False

    @property
    @abstractmethod
    def actions(self):
        pass

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def __hash__(self):
        return id(self)

    @property
    def mana_cost_map(self):
        mana_cost_map = {t: self.mana_cost.count(t) for t in MANA_TYPES}
        try:
            mana_cost_map["C"] = int(''.join(filter(str.isdigit, self.mana_cost)))
        except ValueError:
            pass  # no generic cost
        return mana_cost_map


class MTGLand(MTGCard):
    @property
    def actions(self):
        return ["play"]

    @abstractmethod
    def play(self, env):
        # if not self.play_available(env):
        #     raise ValueError("ERROR: unable to play")
        print(f"Playing {self}")
        env.played_land_this_turn = True
        env.engine.play_land(self)

    def play_available(self, env):
        return self in env.hand and not env.played_land_this_turn

    def tap_for_mana(self, env):
        print(f"Tapping for mana {self}")
        self.is_tapped = True

    def tap_for_mana_available(self, env):
        return self in env.lands and not self.is_tapped


class MTGSpell(MTGCard):
    @property
    def actions(self):
        return ["cast"]

    @abstractmethod
    def cast(self, env):
        print(f"Casting {self}")
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


class Forest(MTGLand):
    def __init__(self):
        super().__init__("Forest", "")

    @property
    def actions(self):
        return super().actions + ["tap_for_mana_G"]

    def play(self, env):
        super().play(env)

    def tap_for_mana_G(self, env):
        super().tap_for_mana(env)
        env.engine.add_mana('G', 1)

    def tap_for_mana_G_available(self, env):
        return super().tap_for_mana_available(env)


class Swamp(MTGLand):
    def __init__(self):
        super().__init__("Swamp", "")

    @property
    def actions(self):
        return super().actions + ["tap_for_mana_B"]

    def play(self, env):
        super().play(env)

    def tap_for_mana_B(self, env):
        super().tap_for_mana(env)
        env.engine.add_mana('B', 1)

    def tap_for_mana_B_available(self, env):
        return super().tap_for_mana_available(env)


class HauntedMire(Forest, Swamp):
    def __init__(self):
        MTGCard.__init__(self, "Haunted Mire", "")

    def play(self, env):
        super().play(env)
        self.is_tapped = True


class LandGrant(MTGSpell):
    def __init__(self):
        MTGCard.__init__(self, "Land Grant", "1G")

    @property
    def actions(self):
        return ["cast_for_forest", "cast_for_mire", "cast_for_forest_for_free", "cast_for_mire_for_free"]

    def cast(self, env):
        raise ValueError("Land Grant: cast - Not implemented")

    def cast_for_forest(self, env):
        super().cast(env)
        env.engine.search_library_for("Forest")
        env.engine.put_from_hand_to_graveyard(self)

    def cast_for_forest_available(self, env):
        return super().cast_available(env) and any(c.name == "Forest" for c in env.library)

    def cast_for_mire(self, env):
        super().cast(env)
        env.engine.search_library_for("Haunted Mire")
        env.engine.put_from_hand_to_graveyard(self)

    def cast_for_mire_available(self, env):
        return super().cast_available(env) and any(c.name == "Haunted Mire" for c in env.library)

    def cast_for_forest_for_free(self, env):
        print("Casting Land Grant for free")
        env.engine.search_library_for("Forest")
        env.engine.put_from_hand_to_graveyard(self)

    def cast_for_forest_for_free_available(self, env):
        return self in env.hand and not any(isinstance(c, MTGLand) for c in env.hand) and any(c.name == "Forest" for c in env.library)

    def cast_for_mire_for_free(self, env):
        print("Casting Land Grant for free")
        env.engine.search_library_for("Haunted Mire")
        env.engine.put_from_hand_to_graveyard(self)

    def cast_for_mire_for_free_available(self, env):
        return self in env.hand and not any(isinstance(c, MTGLand) for c in env.hand) and any(c.name == "Haunted Mire" for c in env.library)


class MTGCreatureSpell(MTGSpell):
    def __init__(self, name, mana_cost, is_defender):
        MTGCard.__init__(self, name, mana_cost)
        self.is_defender = is_defender

    def cast(self, env):
        super().cast(env)
        env.engine.put_from_hand_to_battlefield(self)
        self.has_summoning_sickness = True


class TinderWall(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Tinder Wall", "G", True)

    @property
    def actions(self):
        # for the Spy solitaire we don't need to implement other abilities/properties
        return super().actions + ["sacrifice_for_mana_RR"]

    def cast(self, env):
        super().cast(env)

    def sacrifice_for_mana_RR(self, env):
        print(f"Sacrificing {self} for RR")
        env.engine.sacrifice_creature(self)
        env.engine.add_mana('R', 2)

    def sacrifice_for_mana_RR_available(self, env):
        return self in env.battlefield


class GenerousEnt(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Generous Ent", "5G", False)

    @property
    def actions(self):
        # for the Spy solitaire we don't need to implement other abilities/properties
        return super().actions + ["forestcycling_forest", "forestcycling_mire"]

    def cast(self, env):
        super().cast(env)

    def forestcycling_forest(self, env):
        print(f"Forestcycling {self} for Forest")
        env.engine.pay_mana({"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 1})
        env.engine.discard_card(self)
        env.engine.search_library_for("Forest")
        env.engine.shuffle_library()

    def forestcycling_forest_available(self, env):
        return self in env.hand and any(c.name == "Forest" for c in env.library) and sum(env.mana_pool.values()) > 0

    def forestcycling_mire(self, env):
        print(f"Forestcycling {self} for Haunted Mire")
        env.engine.pay_mana({"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 1})
        env.engine.discard_card(self)
        env.engine.search_library_for("Haunted Mire")
        env.engine.shuffle_library()

    def forestcycling_mire_available(self, env):
        return self in env.hand and any(c.name == "Haunted Mire" for c in env.library) and sum(env.mana_pool.values()) > 0


class TrollOfKhazadDum(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Troll of Khazad-dum", "5B", False)

    @property
    def actions(self):
        # for the Spy solitaire we don't need to implement other abilities/properties
        return super().actions + ["swampcycling_swamp", "swampcycling_mire"]

    def cast(self, env):
        super().cast(env)

    def swampcycling_swamp(self, env):
        print(f"Swampcycling {self} for Swamp")
        env.engine.pay_mana({"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 1})
        env.engine.discard_card(self)
        env.engine.search_library_for("Swamp")
        env.engine.shuffle_library()

    def swampcycling_swamp_available(self, env):
        return self in env.hand and any(c.name == "Swamp" for c in env.library) and sum(env.mana_pool.values()) > 0

    def swampcycling_mire(self, env):
        print(f"Swampcycling {self} for Haunted Mire")
        env.engine.pay_mana({"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 1})
        env.engine.discard_card(self)
        env.engine.search_library_for("Haunted Mire")
        env.engine.shuffle_library()

    def swampcycling_mire_available(self, env):
        return self in env.hand and any(c.name == "Haunted Mire" for c in env.library) and sum(env.mana_pool.values()) > 0


class SaguWildling(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Sagu Wildling", "4B", False)

    @property
    def actions(self):
        # for the Spy solitaire we don't need to implement other abilities/properties
        return super().actions + ["roost_seek_forest", "roost_seek_swamp"]

    def cast(self, env):
        super().cast(env)

    def roost_seek_forest(self, env):
        print(f"Casting Roost Seek {self} for Forest")
        env.engine.pay_mana({"W": 0, "U": 0, "B": 0, "R": 0, "G": 1, "C": 0})
        env.engine.put_from_hand_to_library(self)
        env.engine.search_library_for("Forest")
        env.engine.shuffle_library()

    def roost_seek_forest_available(self, env):
        return self in env.hand and any(c.name == "Forest" for c in env.library) and env.mana_pool["G"] > 0

    def roost_seek_swamp(self, env):
        print(f"Casting Roost Seek {self} for Swamp")
        env.engine.pay_mana({"W": 0, "U": 0, "B": 0, "R": 0, "G": 1, "C": 0})
        env.engine.put_from_hand_to_library(self)
        env.engine.search_library_for("Swamp")
        env.engine.shuffle_library()

    def roost_seek_swamp_available(self, env):
        return self in env.hand and any(c.name == "Swamp" for c in env.library) and env.mana_pool["G"] > 0


class OrnithopterOfParadise(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Ornithopter of Paradise", "2", False)

    @property
    def actions(self):
        # for the Spy solitaire we don't need to implement other abilities/properties
        return super().actions + ["tap_for_mana_G", "tap_for_mana_B"]

    def cast(self, env):
        super().cast(env)

    def tap_for_mana_G(self, env):
        print(f"Tapping for mana {self}")
        env.engine.add_mana('G', 1)
        self.is_tapped = True

    def tap_for_mana_G_available(self, env):
        return self in env.battlefield and not self.has_summoning_sickness and not self.is_tapped

    def tap_for_mana_B(self, env):
        print(f"Tapping for mana {self}")
        env.engine.add_mana('B', 1)
        self.is_tapped = True

    def tap_for_mana_B_available(self, env):
        return self in env.battlefield and not self.has_summoning_sickness and not self.is_tapped


class OvergrownBattlement(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Overgrown Battlement", "1G", True)

    @property
    def actions(self):
        return super().actions + ["tap_for_mana_G"]

    def cast(self, env):
        super().cast(env)

    def tap_for_mana_G(self, env):
        print(f"Tapping for mana {self}")
        env.engine.add_mana('G', sum(c.is_defender for c in env.battlefield))
        self.is_tapped = True

    def tap_for_mana_G_available(self, env):
        return self in env.battlefield and not self.has_summoning_sickness and not self.is_tapped


class ElvesOfDeepShadow(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Elves of Deep Shadow", "G", False)

    @property
    def actions(self):
        return super().actions + ["tap_for_mana_B"]

    def cast(self, env):
        super().cast(env)

    def tap_for_mana_B(self, env):
        print(f"Tapping for mana {self}")
        env.engine.add_mana('B', 1)
        env.counter_life -= 1
        self.is_tapped = True

    def tap_for_mana_B_available(self, env):
        return self in env.battlefield and not self.has_summoning_sickness and not self.is_tapped and env.counter_life > 1


class MaskedVandal(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Masked Vandal", "1G", False)

    # for the Spy solitaire we don't need to implement other abilities/properties


class MesmericFiend(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Mesmeric Fiend", "1B", False)

    # for the Spy solitaire we don't need to implement other abilities/properties


class WindingWay(MTGSpell):
    def __init__(self):
        MTGCard.__init__(self, "Winding Way", "1G")

    def cast(self, env):
        super().cast(env)
        print("Choose Creature")  # always choose Creature
        for _ in range(4):
            card = env.library.pop(0)
            print(f"Revealed {card}")
            if isinstance(card, MTGCreatureSpell):
                env.hand.append(card)
            else:
                env.graveyard.append(card)
        env.engine.put_from_hand_to_graveyard(self)


class LeadTheStampede(MTGSpell):
    def __init__(self):
        MTGCard.__init__(self, "Lead the Stampede", "2G")

    def cast(self, env):
        super().cast(env)
        cards = []
        for _ in range(5):
            card = env.library.pop(0)
            print(f"Looking at {card}")
            cards.append(card)

        on_the_bottom = []
        # never reveal Lotleth Giant
        for card in cards:
            if isinstance(card, MTGCreatureSpell) and not card.name == "Lotleth Giant":
                print(f"Revealed {card}")
                env.hand.append(card)
            else:
                on_the_bottom.append(card)

        lands_on_the_bottom = []
        # always put lands at the bottom, to enable an earlier Spy
        for card in on_the_bottom:
            if not isinstance(card, MTGLand):
                print(f"Put bottom {card}")
                env.library.append(card)
            else:
                lands_on_the_bottom.append(card)

        for card in lands_on_the_bottom:
            print(f"Put bottom {card} (we are pro!)")
            env.library.append(card)
            env.known_lands_bottom += 1

        env.engine.put_from_hand_to_graveyard(self)
