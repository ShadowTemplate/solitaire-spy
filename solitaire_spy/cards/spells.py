import itertools
import logging

from solitaire_spy.cards.creatures import BalustradeSpy, LotlethGiant
from solitaire_spy.cards.mtg_cards import MTGSpell, MTGLand, MTGCreatureSpell
from solitaire_spy.log import get_logger

log = get_logger(__name__, stdout_level=logging.WARNING)


class LandGrant(MTGSpell):
    def __init__(self):
        MTGSpell.__init__(self, "Land Grant", "1G", False)

    def actions(self, env):
        return ["cast_for_forest", "cast_for_mire", "cast_for_forest_for_free", "cast_for_mire_for_free"]

    def cast(self, env):
        raise ValueError("Land Grant: cast - Not implemented")

    def cast_for_forest(self, env):
        super().cast(env)
        env.engine.search_library_for("Forest")
        env.engine.put_from_hand_to_graveyard(self)

    def cast_for_forest_available(self, env):
        return super().cast_available(env) and any(c.name == "Forest" for c in env.library) and not env.engine.passing

    def cast_for_mire(self, env):
        super().cast(env)
        env.engine.search_library_for("Haunted Mire")
        env.engine.put_from_hand_to_graveyard(self)

    def cast_for_mire_available(self, env):
        return super().cast_available(env) and any(c.name == "Haunted Mire" for c in env.library) and not env.engine.passing

    def cast_for_forest_for_free(self, env):
        log.info("Casting Land Grant for free")
        env.engine.search_library_for("Forest")
        env.engine.put_from_hand_to_graveyard(self)

    def cast_for_forest_for_free_available(self, env):
        return self in env.hand and not any(isinstance(c, MTGLand) for c in env.hand) and any(c.name == "Forest" for c in env.library) and not env.engine.passing

    def cast_for_mire_for_free(self, env):
        log.info("Casting Land Grant for free")
        env.engine.search_library_for("Haunted Mire")
        env.engine.put_from_hand_to_graveyard(self)

    def cast_for_mire_for_free_available(self, env):
        return self in env.hand and not any(isinstance(c, MTGLand) for c in env.hand) and any(c.name == "Haunted Mire" for c in env.library) and not env.engine.passing


class WindingWay(MTGSpell):
    def __init__(self):
        MTGSpell.__init__(self, "Winding Way", "1G", False)

    def cast(self, env):
        super().cast(env)
        log.debug("Choose Creature")  # always choose Creature
        for _ in range(4):
            try:
                card = env.library.pop(0)
                log.info(f"Revealed {card}")
                if isinstance(card, MTGCreatureSpell):
                    env.hand.append(card)
                else:
                    env.graveyard.append(card)
            except IndexError:
                continue
        env.engine.put_from_hand_to_graveyard(self)

    def cast_available(self, env):
        return super().cast_available(env) and not env.engine.passing


class LeadTheStampede(MTGSpell):
    def __init__(self):
        MTGSpell.__init__(self, "Lead the Stampede", "2G", False)

    def cast(self, env):
        super().cast(env)
        cards = []
        for _ in range(5):
            try:
                card = env.library.pop(0)
                log.info(f"Looking at {card}")
                cards.append(card)
            except IndexError:
                continue

        on_the_bottom = []
        # never reveal Lotleth Giant
        for card in cards:
            if isinstance(card, MTGCreatureSpell) and not card.name == "Lotleth Giant":
                log.info(f"Revealed {card}")
                env.hand.append(card)
            else:
                on_the_bottom.append(card)

        lands_on_the_bottom = []
        # always put lands at the bottom, to enable an earlier Spy
        for card in on_the_bottom:
            if not isinstance(card, MTGLand):
                log.info(f"Put bottom {card}")
                env.library.append(card)
            else:
                lands_on_the_bottom.append(card)

        for card in lands_on_the_bottom:
            log.info(f"Put bottom {card} (we are pro!)")
            env.library.append(card)
            env.known_lands_bottom += 1

        env.engine.put_from_hand_to_graveyard(self)

    def cast_available(self, env):
        return super().cast_available(env) and not env.engine.passing


class DreadReturn(MTGSpell):
    def __init__(self):
        MTGSpell.__init__(self, "Dread Return", "2BB", True)

    def actions(self, env):
        # we need to compute dynamically which creatures Dread Return can reanimate
        # while cast from hand
        actions = []
        for i, creature in enumerate(env.graveyard):
            actions.append(f"cast_with_target@{i}")

        # we need to compute dynamically which creatures Dread Return can reanimate
        # and which creatures have to be sacrificed while cast with flashback
        for i, creature in enumerate(env.graveyard):
            for triple in itertools.combinations(range(len(env.battlefield)), 3):
                all_creatures = all(isinstance(env.battlefield[c], MTGCreatureSpell) for c in triple)
                if not all_creatures:
                    continue
                actions.append(f"flashback_with_target@{i},{'-'.join(str(c) for c in triple)}")
        return actions

    def cast(self, env):
        raise ValueError("Dread Return: cast - Not implemented")

    def cast_with_target(self, env, i):
        super().cast(env)
        target = env.graveyard[int(i)]
        log.info(f"Targeting {target}")
        env.engine.put_from_graveyard_to_battlefield(target)
        env.engine.put_from_hand_to_graveyard(self)

    def cast_with_target_available(self, env, i):
        # optional: enable only if Giant/Spy in graveyard
        # optimization = False
        optimization = any(isinstance(c, BalustradeSpy) for c in env.graveyard) and any(isinstance(c, LotlethGiant) for c in env.graveyard)
        return super().cast_available(env) and isinstance(env.graveyard[int(i)], MTGCreatureSpell) and not env.engine.passing and optimization

    def flashback_with_target(self, env, itriple):
        log.info(f"Flashing back {self}")
        i, triple = itriple.split(",")
        target = env.graveyard[int(i)]
        creatures_to_sac = [env.battlefield[int(i)] for i in triple.split("-")]
        log.info(f"Targeting {target} saccing {creatures_to_sac}")
        env.engine.put_from_graveyard_to_exile(self)
        for creature_to_sac in creatures_to_sac:
            env.engine.sacrifice_creature(creature_to_sac)
        env.engine.put_from_graveyard_to_battlefield(target)

    def flashback_with_target_available(self, env, itriple):
        # optional: enable only if Giant/Spy in graveyard
        # optimization = False
        optimization = any(isinstance(c, BalustradeSpy) for c in env.graveyard) and any(isinstance(c, LotlethGiant) for c in env.graveyard)
        i, triple = itriple.split(",")
        creatures_to_sac = [env.battlefield[int(i)] for i in triple.split("-")]
        all_creatures_to_sac = all(isinstance(c, MTGCreatureSpell) for c in creatures_to_sac)
        return self in env.graveyard and isinstance(env.graveyard[int(i)], MTGCreatureSpell) and all_creatures_to_sac and not env.engine.passing and optimization


class LotusPetal(MTGSpell):
    def __init__(self):
        MTGSpell.__init__(self, "Lotus Petal", "0", False)

    def actions(self, env):
        return super().actions(env) + ["sacrifice_for_mana_G", "sacrifice_for_mana_B"]

    def cast(self, env):
        super().cast(env)
        env.engine.put_from_hand_to_battlefield(self)

    def cast_available(self, env):
        return super().cast_available(env) and not env.engine.passing

    def sacrifice_for_mana_G(self, env):
        log.info(f"Sacrificing {self} for G")
        env.engine.add_mana('G', 1)
        env.engine.sacrifice_permanent(self)

    def sacrifice_for_mana_G_available(self, env):
        # optimization: disable sac at instant speed in oppo's turn
        return self in env.battlefield and not env.engine.passing

    def sacrifice_for_mana_B(self, env):
        log.info(f"Sacrificing {self} for B")
        env.engine.add_mana('B', 1)
        env.engine.sacrifice_permanent(self)

    def sacrifice_for_mana_B_available(self, env):
        return self in env.battlefield
