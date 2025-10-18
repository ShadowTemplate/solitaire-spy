from solitaire_spy.cards.mtg_cards import MTGCreatureSpell
from solitaire_spy.cards.lands import Forest


class TinderWall(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Tinder Wall", "G", True)

    def actions(self, env):
        # for the Spy solitaire we don't need to implement other abilities/properties
        return super().actions(env) + ["sacrifice_for_mana_RR"]

    def cast(self, env):
        super().cast(env)

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)

    def sacrifice_for_mana_RR(self, env):
        print(f"Sacrificing {self} for RR")
        env.engine.sacrifice_creature(self)
        env.engine.add_mana('R', 2)

    def sacrifice_for_mana_RR_available(self, env):
        return self in env.battlefield


class GenerousEnt(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Generous Ent", "5G", False)

    def actions(self, env):
        # for the Spy solitaire we don't need to implement other abilities/properties
        return super().actions(env) + ["forestcycling_forest", "forestcycling_mire"]

    def cast(self, env):
        super().cast(env)

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)

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

    def actions(self, env):
        # for the Spy solitaire we don't need to implement other abilities/properties
        return super().actions(env) + ["swampcycling_swamp", "swampcycling_mire"]

    def cast(self, env):
        super().cast(env)

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)

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

    def actions(self, env):
        # for the Spy solitaire we don't need to implement other abilities/properties
        return super().actions(env) + ["roost_seek_forest", "roost_seek_swamp"]

    def cast(self, env):
        super().cast(env)

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)

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

    def actions(self, env):
        # for the Spy solitaire we don't need to implement other abilities/properties
        return super().actions(env) + ["tap_for_mana_G", "tap_for_mana_B"]

    def cast(self, env):
        super().cast(env)

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)

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
        return self.tap_for_mana_G_available(env)


class OvergrownBattlement(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Overgrown Battlement", "1G", True)

    def actions(self, env):
        return super().actions(env) + ["tap_for_mana_G"]

    def cast(self, env):
        super().cast(env)

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)

    def tap_for_mana_G(self, env):
        print(f"Tapping for mana {self}")
        env.engine.add_mana('G', sum(c.is_defender for c in env.battlefield))
        self.is_tapped = True

    def tap_for_mana_G_available(self, env):
        return self in env.battlefield and not self.has_summoning_sickness and not self.is_tapped


class ElvesOfDeepShadow(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Elves of Deep Shadow", "G", False)

    def actions(self, env):
        return super().actions(env) + ["tap_for_mana_B"]

    def cast(self, env):
        super().cast(env)

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)

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
    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)


class MesmericFiend(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Mesmeric Fiend", "1B", False)

    # for the Spy solitaire we don't need to implement other abilities/properties
    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)


class SaruliCaretaker(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Saruli Caretaker", "G", True)

    def actions(self, env):
        actions = super().actions(env)
        # we need to compute dynamically which creatures Saruli can tap to make mana
        # and for each of them give the option to produce B or G
        for i, creature in enumerate(env.battlefield):
            if creature != self and not creature.is_tapped:
                actions.append(f"tap_creature_for_mana_G@{i}")
                actions.append(f"tap_creature_for_mana_B@{i}")
        return actions

    def cast(self, env):
        super().cast(env)

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)

    def tap_creature_for_mana_G(self, env, i):
        i = int(i)
        print(f"Tapping {self} and {env.battlefield[i]} for mana G")
        env.engine.add_mana('G', 1)
        env.battlefield[i].is_tapped = True
        self.is_tapped = True

    def tap_creature_for_mana_G_available(self, env, i):
        return self in env.battlefield and not self.has_summoning_sickness and not self.is_tapped and not env.battlefield[int(i)].is_tapped

    def tap_creature_for_mana_B(self, env, i):
        i = int(i)
        print(f"Tapping {self} and {env.battlefield[i]} for mana B")
        env.engine.add_mana('B', 1)
        env.battlefield[i].is_tapped = True
        self.is_tapped = True

    def tap_creature_for_mana_B_available(self, env, i):
        return self.tap_creature_for_mana_G_available(env, i)


class QuirionRanger(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Quirion Ranger", "G", False)

    def actions(self, env):
        actions = super().actions(env)
        # we need to compute dynamically which creatures Quirion can untap
        # and for each of them give the option to bounce a land
        for i, creature in enumerate(env.battlefield):
            for j, land in enumerate(env.lands):
                if isinstance(land, Forest):
                    actions.append(f"untap_creature_bouncing_land@{i},{j}")
        return actions

    def cast(self, env):
        super().cast(env)

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)

    def untap_creature_bouncing_land(self, env, ij):
        i, j = ij.split(",")
        i, j = int(i), int(j)
        print(f"Untapping {env.battlefield[i]} and bouncing {env.lands[j]}")
        env.battlefield[i].is_tapped = False
        env.engine.bounce_land_to_hand(env.lands[j])
        self.ability_once_per_turn_activated = True

    def untap_creature_bouncing_land_available(self, env, ij):
        return self in env.battlefield and any(isinstance(c, Forest) for c in env.lands) and not self.ability_once_per_turn_activated


class LotlethGiant(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Lotleth Giant", "6B", False)

    def actions(self, env):
        return super().actions(env)

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)
        env.opponent_counter_life -= sum(isinstance(c, MTGCreatureSpell) for c in env.graveyard)
