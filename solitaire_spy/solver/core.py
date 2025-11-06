from collections import defaultdict
from copy import deepcopy
import logging

from solitaire_spy.mtg_engine import GameLostException
from solitaire_spy.solver.heuristics import *
from solitaire_spy.spy_solitaire import MTGSolitaire

from solitaire_spy.log import get_logger

log = get_logger(stdout_level=logging.INFO)


class Solver:
    def __init__(self, env: MTGSolitaire):
        self.env_queues = defaultdict(list)  # one queue for each turn counter
        self.env_queues[0] = [env]  # initial env goes to turn 0
        self.heuristics = [
            play_unique_action,
            play_only_a_land,
            tap_basic_land_for_mana,
            cast_land_grant_for_free,
            cast_lotus_petal,
            no_useless_mana_switch_strategy,
            cast_saruli_before_tapping_battlement,
            cast_spell_if_only_option,
            tutor_land_if_only_option,
            mill_deck_with_spy,
            flashback_giant_for_lethal,
        ]
        self.explored_hashes = set()
        self.explored_hashes.add(env.functional_hash)

    def _get_obvious_action(self, env, possible_actions):
        for heuristic in self.heuristics:
            card, action = heuristic(env, possible_actions)
            if action is not None:
                return card, action
        return None, None

    def solve(self):
        # TODO: keep or mull
        while True:  # a winning game will eventually be found
            log.info(f"In queue: {sum(len(values) for q, values in self.env_queues.items())}")
            # let's start from universes with low counter_turn
            for i in range(len(self.env_queues)):
                if len(self.env_queues[i]) > 0:
                    env = self.env_queues[i].pop(0)
                    break
            log.info(f"Playing turn {env.counter_turn}")

            # check if there are obvious actions and play them first (no need to copy)
            action = True
            game_loss = False
            while action:
                possible_actions = env.engine.get_possible_actions()
                card, action = self._get_obvious_action(env, possible_actions)
                if action is not None:
                    log.debug(f"Queuing after obvious action {card}: {action}")
                    try:
                        env.step(card, action)
                        # env.render()
                        if env.opponent_counter_life <= 0:
                            log.info(
                                f"You won at turn {env.counter_turn} "
                                f"(lands in deck: {any(isinstance(c, MTGLand) for c in env.library)}, "
                                f"cards in library: {len(env.library)})!"
                            )
                            return env
                        # uncomment block below to enqueue env after each obvious action
                        # this probably doesn't make much sense and only slows down
                        # self.env_queue.append(env)
                        # continue
                    except GameLostException:
                        game_loss = True
                        break
            if game_loss:
                continue  # pick the next env

            possible_actions = env.engine.get_possible_actions()  # refresh after obvious ones
            possible_actions = self.greedify_action(env, possible_actions)
            if len(possible_actions) == 2:
                log.debug("Explore for optimizations...")

            # no obvious action: BFS-search
            for i in range(len(possible_actions)):
                new_env = deepcopy(env)
                # after deepcopy, objects get new ids: need to re-get_possible_actions
                # (and we know there are no obvious ones)
                new_possible_actions = new_env.engine.get_possible_actions()
                new_possible_actions = self.greedify_action(new_env, new_possible_actions)
                card, action = new_possible_actions[i]
                try:
                    log.debug(
                        f"Queuing after possible action {card}: {action}"
                    )
                    new_env.step(card, action)
                    if new_env.opponent_counter_life <= 0:
                        log.info(
                            f"You won at turn {env.counter_turn} "
                            f"(lands in deck: {any(isinstance(c, MTGLand) for c in env.library)}, "
                            f"cards in library: {len(env.library)})!"
                        )
                        return new_env
                    if new_env.functional_hash not in self.explored_hashes:
                        self.env_queues[new_env.counter_turn].append(new_env)
                    else:
                        log.debug("Great: computation saved!")
                except GameLostException:
                    continue  # pick the next action

    def greedify_action(self, env, possible_actions):
        # If you can play a Forest and also cycle for another Forest (not Mire!),
        # just play the Forest first: what you'd get cycling is the same anyway
        has_mire = any(c.name == "Haunted Mire" for c in env.library)
        forest_card, forest_action = None, None
        can_cycle_for_forest = False
        for card, action in possible_actions:
            if action == "forestcycling_forest":
                can_cycle_for_forest = True
            if isinstance(card, Forest) and action == "play":
                forest_card, forest_action = card, action
        if not has_mire and can_cycle_for_forest and forest_card is not None:
            log.debug("Applying greedy strategy: play Forest before cycling for Forest")
            possible_actions = [ca for ca in possible_actions if ca[1] != "forestcycling_forest"]

        # If you can play land(s) and also do something else (except getting lands),
        # prioritize the play of a/the land
        can_play_land = False
        can_tutor_land = False
        for card, action in possible_actions:
            if isinstance(card, MTGLand) and action == "play":
                can_play_land = True
            if "forestcycling" in action or "swampcycling" in action or "roost_seek" in action:
                can_tutor_land = True
        if can_play_land and not can_tutor_land:
            log.debug("Applying greedy strategy: prioritize land play")
            possible_actions = [ca for ca in possible_actions if ca[1] == "play"]

        # Greedy strategy: if you can do something, always do it.
        # Let's exclude envs where you can "just pass" with other options available.
        # Exceptions:
        # - Wall of Roots (when we might want to save some mana for later)
        # - Tinder Wall (when we might want to save some mana for later)
        # - Lotus Petal (when we might want to save some mana for later)
        # - Balustrade Spy (can cause us to lose)
        can_pass = False
        too_greedy_actions = 0
        for card, action in possible_actions:
            if action == "system_pass":
                can_pass = True
            if action == "sacrifice_for_mana_RR" or action == "put_counter_for_mana_G" or action == "sacrifice_for_mana_G" or action == "sacrifice_for_mana_B":
                too_greedy_actions += 1
            if isinstance(card, BalustradeSpy) and action == "cast":
                too_greedy_actions += 1
        # if you have 2 or more (not too greedy) actions, and one of them is pass...
        if can_pass and len(possible_actions) - too_greedy_actions >= 2:
            # ... let's not explore the env where you just pass
            log.debug("Applying greedy strategy: ignore 'just pass'")
            possible_actions = [ca for ca in possible_actions if ca[1] != "system_pass"]

        return possible_actions
