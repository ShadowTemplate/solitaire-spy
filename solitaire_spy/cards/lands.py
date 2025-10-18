from solitaire_spy.cards.mtg_cards import MTGLand, MTGCard, MTGSpell, MTGCreatureSpell


class Forest(MTGLand):
    def __init__(self):
        super().__init__("Forest", "")

    def actions(self, env):
        return super().actions(env) + ["tap_for_mana_G"]

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

    def actions(self, env):
        return super().actions(env) + ["tap_for_mana_B"]

    def play(self, env):
        super().play(env)

    def tap_for_mana_B(self, env):
        super().tap_for_mana(env)
        env.engine.add_mana('B', 1)

    def tap_for_mana_B_available(self, env):
        return super().tap_for_mana_available(env)


class HauntedMire(Swamp, Forest):
    def __init__(self):
        MTGCard.__init__(self, "Haunted Mire", "")

    def play(self, env):
        super().play(env)
        self.is_tapped = True


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
