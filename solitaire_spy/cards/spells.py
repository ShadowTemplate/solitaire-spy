import itertools

from solitaire_spy.cards.mtg_cards import MTGSpell, MTGCard, MTGLand, MTGCreatureSpell


class LandGrant(MTGSpell):
    def __init__(self):
        MTGCard.__init__(self, "Land Grant", "1G")

    def actions(self, env):
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


class DreadReturn(MTGSpell):
    def __init__(self):
        MTGCard.__init__(self, "Dread Return", "2BB")

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
                actions.append(f"flashback_with_target@{i},{'-'.join(str(c) for c in triple)}")
        return actions

    def cast(self, env):
        raise ValueError("Dread Return: cast - Not implemented")

    def cast_with_target(self, env, i):
        super().cast(env)
        target = env.graveyard[int(i)]
        print(f"Targeting {target}")
        env.engine.put_from_graveyard_to_battlefield(target)
        env.engine.put_from_hand_to_graveyard(self)

    def cast_with_target_available(self, env, i):
        return super().cast_available(env) and isinstance(env.graveyard[int(i)], MTGCreatureSpell)

    def flashback_with_target(self, env, itriple):
        print(f"Flashing back {self}")
        i, triple = itriple.split(",")
        target = env.graveyard[int(i)]
        creatures_to_sac = [env.battlefield[int(i)] for i in triple.split("-")]
        print(f"Targeting {target} saccing {creatures_to_sac}")
        env.engine.put_from_graveyard_to_exile(self)
        for creature_to_sac in creatures_to_sac:
            env.engine.sacrifice_creature(creature_to_sac)
        env.engine.put_from_graveyard_to_battlefield(target)

    def flashback_with_target_available(self, env, itriple):
        i, triple = itriple.split(",")
        return self in env.graveyard and isinstance(env.graveyard[int(i)], MTGCreatureSpell)
