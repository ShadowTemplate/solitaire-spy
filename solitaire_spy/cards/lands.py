from solitaire_spy.cards.mtg_cards import MTGLand, MTGCard


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
