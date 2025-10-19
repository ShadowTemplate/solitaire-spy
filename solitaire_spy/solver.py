from solitaire_spy.cards.creatures import BalustradeSpy, LotlethGiant
from solitaire_spy.cards.lands import Forest, Swamp
from solitaire_spy.cards.mtg_cards import MTGLand, MTGCreatureSpell
from solitaire_spy.cards.spells import LandGrant, DreadReturn
from solitaire_spy.mtg_engine import GameLostException
from solitaire_spy.spy_solitaire import MTGSolitaire


class Solver:
    def __init__(self, env: MTGSolitaire):
        self.env = env
        self.game_log = []

    def solve(self):
        # TODO: keep or mull
        self.play_optimally()

    def get_obvious_action(self, possible_actions):
        # only one possible action, do it
        if len(possible_actions) == 1:
            return possible_actions[0]

        free_land_grant = 0
        free_land_grant_card, free_land_grant_action = None, None
        can_cast_spy = False
        spy_card, spy_action = None, None
        can_flashback_dread_return = False

        # if a basic land can be tapped for mana, do it
        for card, action in possible_actions:
            if isinstance(card, Forest) and action == "tap_for_mana_G":
                return card, action
            if isinstance(card, Swamp) and action == "tap_for_mana_B":
                return card, action
            if isinstance(card, LandGrant) and "for_free" in action:
                free_land_grant += 1
                free_land_grant_card, free_land_grant_action = card, action
            if isinstance(card, BalustradeSpy):
                can_cast_spy = True
                spy_card, spy_action = card, action
            if isinstance(card, DreadReturn) and "flashback" in action:
                can_flashback_dread_return = True

        # if Land Grant in hand can be used to freely get only one type of land, do it
        if free_land_grant == 1:
            return free_land_grant_card, free_land_grant_action

        # if Spy in hand can be cast to 100% mill the deck and win, do it
        lands_in_play = len(self.env.lands)
        lands_in_hand = sum(isinstance(c, MTGLand) for c in self.env.hand)
        all_lands_ready = lands_in_play + lands_in_hand + self.env.known_lands_bottom == self.env.lands_in_deck
        dread_return_in_deck = any(isinstance(c, DreadReturn) for c in self.env.library)
        giant_in_deck = any(isinstance(c, LotlethGiant) for c in self.env.library)
        if can_cast_spy and len(self.env.battlefield) >= 2 and all_lands_ready and dread_return_in_deck and giant_in_deck:
            return spy_card, spy_action

        # if Dread Return can be flashed-back for lethal, do it
        giant_in_graveyard = any(isinstance(c, LotlethGiant) for c in self.env.graveyard)
        damage_giant_will_do = sum(isinstance(c, MTGCreatureSpell) for c in self.env.graveyard) + 2  # -1 Giant itself + 3 creatures sacrificed
        if can_flashback_dread_return and giant_in_graveyard and damage_giant_will_do >= self.env.opponent_counter_life:
            for i, gy_card in enumerate(self.env.graveyard):
                if gy_card.name == "Lotleth Giant":
                    return next(p for p in possible_actions if f"flashback_with_target@{i}" in p[1])

        # no obvious play
        return None, None

    def play_optimally(self):
        game_lost = False
        while self.env.opponent_counter_life > 0 and not game_lost:
            possible_actions = self.env.engine.get_possible_actions()

            # check if there are obvious actions and play them first
            card, action = self.get_obvious_action(possible_actions)
            if action is not None:
                self.env.step(card, action)
                self.env.render()
                continue

            # fork universes
            card, action = possible_actions[0]
            try:
                self.env.step(card, action)
                self.env.render()
            except GameLostException:
                game_lost = True
        if game_lost:
            print(f"You lost at turn {self.env.counter_turn}!")
        else:
            print(f"You won at turn {self.env.counter_turn}!")
