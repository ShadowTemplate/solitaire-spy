import logging
from solitaire_spy.cards.mtg_cards import MTGCreatureSpell, MTGLand
from solitaire_spy.cards.lands import Forest
from solitaire_spy.log import get_logger

log = get_logger(stdout_level=logging.INFO)


class TinderWall(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Tinder Wall", "G", False, True)

    def actions(self, env):
        # for the Spy solitaire we don't need to implement other abilities/properties
        return super().actions(env) + ["sacrifice_for_mana_RR"]

    def cast(self, env):
        super().cast(env)

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)

    def sacrifice_for_mana_RR(self, env):
        log.info(f"Sacrificing {self} for RR")
        env.engine.sacrifice_creature(self)
        env.engine.add_mana('R', 2)

    def sacrifice_for_mana_RR_available(self, env):
        return self in env.battlefield


class GenerousEnt(MTGCreatureSpell):
    def __init__(self):
        # optimization: do not aim at casting Ent
        super().__init__("Generous Ent", "5G", False, False)

    def actions(self, env):
        # for the Spy solitaire we don't need to implement other abilities/properties
        return super().actions(env) + ["forestcycling_forest", "forestcycling_mire"]

    def cast(self, env):
        super().cast(env)

    def cast_available(self, env):
        return False

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)

    def forestcycling_forest(self, env):
        log.info(f"Forestcycling {self} for Forest")
        env.engine.pay_mana({"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 1})
        env.engine.discard_card(self)
        env.engine.search_library_for("Forest")
        env.engine.shuffle_library()

    def forestcycling_forest_available(self, env):
        return self in env.hand and any(c.name == "Forest" for c in env.library) and sum(env.mana_pool.values()) > 0

    def forestcycling_mire(self, env):
        log.info(f"Forestcycling {self} for Haunted Mire")
        env.engine.pay_mana({"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 1})
        env.engine.discard_card(self)
        env.engine.search_library_for("Haunted Mire")
        env.engine.shuffle_library()

    def forestcycling_mire_available(self, env):
        return self in env.hand and any(c.name == "Haunted Mire" for c in env.library) and sum(env.mana_pool.values()) > 0


class TrollOfKhazadDum(MTGCreatureSpell):
    def __init__(self):
        # optimization: do not aim at casting Troll
        super().__init__("Troll of Khazad-dum", "5B", False, False)

    def actions(self, env):
        # for the Spy solitaire we don't need to implement other abilities/properties
        return super().actions(env) + ["swampcycling_swamp", "swampcycling_mire"]

    def cast(self, env):
        super().cast(env)

    def cast_available(self, env):
        return False

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)

    def swampcycling_swamp(self, env):
        log.info(f"Swampcycling {self} for Swamp")
        env.engine.pay_mana({"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 1})
        env.engine.discard_card(self)
        env.engine.search_library_for("Swamp")
        env.engine.shuffle_library()

    def swampcycling_swamp_available(self, env):
        return self in env.hand and any(c.name == "Swamp" for c in env.library) and sum(env.mana_pool.values()) > 0

    def swampcycling_mire(self, env):
        log.info(f"Swampcycling {self} for Haunted Mire")
        env.engine.pay_mana({"W": 0, "U": 0, "B": 0, "R": 0, "G": 0, "C": 1})
        env.engine.discard_card(self)
        env.engine.search_library_for("Haunted Mire")
        env.engine.shuffle_library()

    def swampcycling_mire_available(self, env):
        return self in env.hand and any(c.name == "Haunted Mire" for c in env.library) and sum(env.mana_pool.values()) > 0


class SaguWildling(MTGCreatureSpell):
    def __init__(self):
        # optimization: do not aim at casting Sagu
        super().__init__("Sagu Wildling", "4B", False, False)

    def actions(self, env):
        # for the Spy solitaire we don't need to implement other abilities/properties
        return super().actions(env) + ["roost_seek_forest", "roost_seek_swamp"]

    def cast(self, env):
        super().cast(env)

    def cast_available(self, env):
        return False

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)

    def roost_seek_forest(self, env):
        log.info(f"Casting Roost Seek {self} for Forest")
        env.engine.pay_mana({"W": 0, "U": 0, "B": 0, "R": 0, "G": 1, "C": 0})
        env.engine.put_from_hand_to_library(self)
        env.engine.search_library_for("Forest")
        env.engine.shuffle_library()

    def roost_seek_forest_available(self, env):
        return self in env.hand and any(c.name == "Forest" for c in env.library) and env.mana_pool["G"] > 0 and not env.engine.passing

    def roost_seek_swamp(self, env):
        log.info(f"Casting Roost Seek {self} for Swamp")
        env.engine.pay_mana({"W": 0, "U": 0, "B": 0, "R": 0, "G": 1, "C": 0})
        env.engine.put_from_hand_to_library(self)
        env.engine.search_library_for("Swamp")
        env.engine.shuffle_library()

    def roost_seek_swamp_available(self, env):
        return self in env.hand and any(c.name == "Swamp" for c in env.library) and env.mana_pool["G"] > 0 and not env.engine.passing


class OrnithopterOfParadise(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Ornithopter of Paradise", "2", False, False)

    def actions(self, env):
        # for the Spy solitaire we don't need to implement other abilities/properties
        return super().actions(env) + ["tap_for_mana_G", "tap_for_mana_B"]

    def cast(self, env):
        super().cast(env)

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)

    def tap_for_mana_G(self, env):
        log.info(f"Tapping for mana {self}")
        env.engine.add_mana('G', 1)
        self.is_tapped = True

    def tap_for_mana_G_available(self, env):
        return self in env.battlefield and not self.has_summoning_sickness and not self.is_tapped

    def tap_for_mana_B(self, env):
        log.info(f"Tapping for mana {self}")
        env.engine.add_mana('B', 1)
        self.is_tapped = True

    def tap_for_mana_B_available(self, env):
        return self.tap_for_mana_G_available(env)


class OvergrownBattlement(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Overgrown Battlement", "1G", False, True)

    def actions(self, env):
        return super().actions(env) + ["tap_for_mana_G"]

    def cast(self, env):
        super().cast(env)

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)

    def tap_for_mana_G(self, env):
        log.info(f"Tapping for mana {self}")
        env.engine.add_mana('G', sum(c.is_defender for c in env.battlefield if isinstance(c, MTGCreatureSpell)))
        self.is_tapped = True

    def tap_for_mana_G_available(self, env):
        return self in env.battlefield and not self.has_summoning_sickness and not self.is_tapped


class ElvesOfDeepShadow(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Elves of Deep Shadow", "G", False, False)

    def actions(self, env):
        return super().actions(env) + ["tap_for_mana_B"]

    def cast(self, env):
        super().cast(env)

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)

    def tap_for_mana_B(self, env):
        log.info(f"Tapping for mana {self}")
        env.engine.add_mana('B', 1)
        env.counter_life -= 1
        self.is_tapped = True

    def tap_for_mana_B_available(self, env):
        return self in env.battlefield and not self.has_summoning_sickness and not self.is_tapped and env.counter_life > 1


class MaskedVandal(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Masked Vandal", "1G", False, False)

    # for the Spy solitaire we don't need to implement other abilities/properties
    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)


class MesmericFiend(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Mesmeric Fiend", "1B", True, False)

    # for the Spy solitaire we don't need to implement other abilities/properties
    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)


class SaruliCaretaker(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Saruli Caretaker", "G", False, True)

    def actions(self, env):
        actions = super().actions(env)
        # we need to compute dynamically which creatures Saruli can tap to make mana
        # and for each of them give the option to produce B or G
        for i, creature in enumerate(env.battlefield):
            if not isinstance(creature, MTGCreatureSpell):
                continue
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
        log.info(f"Tapping {self} and {env.battlefield[i]} for mana G")
        env.engine.add_mana('G', 1)
        env.battlefield[i].is_tapped = True
        self.is_tapped = True

    def tap_creature_for_mana_G_available(self, env, i):
        creature_to_tap = env.battlefield[int(i)]
        return self in env.battlefield and not self.has_summoning_sickness and not self.is_tapped and isinstance(creature_to_tap, MTGCreatureSpell) and not creature_to_tap.is_tapped

    def tap_creature_for_mana_B(self, env, i):
        i = int(i)
        log.info(f"Tapping {self} and {env.battlefield[i]} for mana B")
        env.engine.add_mana('B', 1)
        env.battlefield[i].is_tapped = True
        self.is_tapped = True

    def tap_creature_for_mana_B_available(self, env, i):
        # optimization: never tap for B if no B creature card in hand
        # optimization = False
        optimization = any(s for s in env.hand if hasattr(s, "can_be_cast_for_black") and s.can_be_cast_for_black)
        return self.tap_creature_for_mana_G_available(env, i) and optimization


class QuirionRanger(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Quirion Ranger", "G", False, False)

    def actions(self, env):
        actions = super().actions(env)
        # we need to compute dynamically which creatures Quirion can untap
        # and for each of them give the option to bounce a land
        for i, creature in enumerate(env.battlefield):
            if not isinstance(creature, MTGCreatureSpell):
                continue
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
        log.info(f"Untapping {env.battlefield[i]} and bouncing {env.lands[j]}")
        env.battlefield[i].is_tapped = False
        env.engine.bounce_land_to_hand(env.lands[j])
        self.ability_once_per_turn_activated = True

    def untap_creature_bouncing_land_available(self, env, ij):
        i, j = ij.split(",")
        creature_to_untap = env.battlefield[int(i)]
        land_to_bounce = env.lands[int(j)]
        return self in env.battlefield and isinstance(creature_to_untap, MTGCreatureSpell) and isinstance(land_to_bounce, Forest) and not self.ability_once_per_turn_activated


class LotlethGiant(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Lotleth Giant", "6B", True, False)

    def actions(self, env):
        return super().actions(env)

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)
        env.opponent_counter_life -= sum(isinstance(c, MTGCreatureSpell) for c in env.graveyard)


class BalustradeSpy(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Balustrade Spy", "3B", True, False)

    def actions(self, env):
        return super().actions(env)

    def cast_available(self, env):
        # first check if there's mana to cast it
        if not super().cast_available(env):
            return False
        # if so, also checks if Spy can be cast reliably:
        # lands_in_deck_at_start <=
        #   lands_in_play + lands_in_hand + lands_in_graveyard + known_lands_bottom +
        #   (spy_in_hand - 1)  (each additional Spy can take out a land later)
        lands_in_play = len(env.lands)
        lands_in_hand = sum(isinstance(c, MTGLand) for c in env.hand)
        lands_in_graveyard = sum(isinstance(c, MTGLand) for c in env.graveyard)
        spy_in_hand = sum(isinstance(c, BalustradeSpy) for c in env.hand)
        return (env.lands_in_deck <=
                lands_in_play + lands_in_hand + lands_in_graveyard +
                env.known_lands_bottom + spy_in_hand - 1)

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)
        # always choose myself
        while True:
            if len(env.library) == 0:
                break
            card = env.library.pop(0)
            log.info(f"Revealed {card}")
            env.graveyard.append(card)
            if isinstance(card, MTGLand):
                break


class WallOfRoots(MTGCreatureSpell):
    def __init__(self):
        super().__init__("Wall of Roots", "1G", False, True)
        self.minus_counters = 0

    def actions(self, env):
        return super().actions(env) + ["put_counter_for_mana_G"]

    def enters_the_battlefield(self, env):
        super().enters_the_battlefield(env)

    def put_counter_for_mana_G(self, env):
        log.info(f"Putting a -0/-1 counter on {self} to add G")
        self.ability_once_per_turn_activated = True
        env.engine.add_mana('G', 1)

        self.minus_counters += 1
        if self.minus_counters == 5:
            log.info(f"Wall of Roots has 0 toughness and dies")
            self.minus_counters = 0
            env.engine.sacrifice_creature(self)

    def put_counter_for_mana_G_available(self, env):
        return self in env.battlefield and not self.ability_once_per_turn_activated and self.minus_counters < 5

    @property
    def functional_hash(self):
        return super().functional_hash + str(self.minus_counters)
