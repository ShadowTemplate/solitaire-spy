import random
import timeit
from collections import defaultdict
from copy import deepcopy
import logging

from solitaire_spy.constants import *
from solitaire_spy.mtg_engine import GameLostException
from solitaire_spy.solver.heuristics import *
from solitaire_spy.spy_solitaire import MTGSolitaire

from solitaire_spy.log import get_logger

log = get_logger(__name__, stdout_level=logging.WARNING)


class Solver:
    def __init__(self, env: MTGSolitaire):
        self.env_queues = defaultdict(list)  # one queue for each turn counter
        # We are going to create a list of queues.
        # Each i-th queue will contain all the games to be explored currently at turn i.
        self.env_queues[0] = [env]  # initial env and mulligans go to turn 0
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
        self.turns_explored = 0

    def _get_obvious_action(self, env, possible_actions):
        for heuristic in self.heuristics:
            card, action = heuristic(env, possible_actions)
            if action is not None:
                return card, action
        return None, None

    def solve(self, greedily=True, early_abort=True, start_time=None, with_lucky_wins=True, initial_hand_size=None):
        if not initial_hand_size:
            self.keep_and_mull()
        else:
            self.start_with(initial_hand_size)
        while sum(len(values) for _, values in self.env_queues.items()) > 0:
            queue_size = sum(len(values) for _, values in self.env_queues.items())
            if queue_size % 100 == 0:
                log.info(f"In queue: {queue_size}")
            # let's start from universes with low counter_turn
            for i in range(len(self.env_queues)):
                if len(self.env_queues[i]) > 0:
                    env = self.env_queues[i].pop(0)
                    break
            if start_time and timeit.default_timer() - start_time > MAX_SOLVER_RUNTIME:
                log.info(
                    f"Reached maximum computation time for solving "
                    f"({MAX_SOLVER_RUNTIME:.2f} s). Aborting..."
                )
                return EXECUTION_TIMEOUT, env

            if env.counter_turn > self.turns_explored:
                log.info(f"Playing turn {env.counter_turn}")
                self.turns_explored = env.counter_turn

            if env.counter_turn >= MAX_TURN:
                log.info(f"Playing turn {env.counter_turn}")
                return EXECUTION_TRUNCATED, env

            if early_abort and self.is_useless_game(env):
                log.debug("Optimization: early aborting useless game")
                continue

            if len(env.steps_log) == 0:  # game just started
                # keep a backup of initial hand for final stats
                env.initial_hand = deepcopy(env.hand)

            # check if there are obvious actions and play them first (no need to copy)
            action = True
            game_loss = False
            while action:
                if early_abort and self.is_useless_game(env):
                    log.debug("Optimization: early aborting useless game")
                    game_loss = True
                    break

                possible_actions = env.engine.get_possible_actions()
                card, action = self._get_obvious_action(env, possible_actions)
                if action is not None:
                    log.debug(f"Queuing after obvious action {card}: {action}")
                    try:
                        env.step(card, action)
                        # env.render()
                        if env.opponent_counter_life <= 0:
                            if not with_lucky_wins and env.unknown_lands_in_deck_on_combo > 0:
                                log.debug("Ignoring lucky win...")
                                game_loss = True
                                continue
                            else:
                                log.info(
                                    f"You won at turn {env.counter_turn} "
                                    f"(lands in deck: {sum(isinstance(c, MTGLand) for c in env.library)}, "
                                    f"cards in library: {len(env.library)}, "
                                    f"keep at {env.kept_at})!"
                                )
                                return EXECUTION_SUCCEEDED, env
                    except GameLostException:
                        game_loss = True
                        break
            if game_loss:
                continue  # pick the next env

            possible_actions = env.engine.get_possible_actions()  # refresh after obvious ones
            if greedily:
                possible_actions = self.greedify_action(env, possible_actions)

            # no obvious action: BFS-search
            for i in range(len(possible_actions)):
                new_env = deepcopy(env)
                # after deepcopy, objects get new ids: need to re-get_possible_actions
                # (and we know there are no obvious ones)
                new_possible_actions = new_env.engine.get_possible_actions()
                if greedily:
                    new_possible_actions = self.greedify_action(new_env, new_possible_actions)
                card, action = new_possible_actions[i]
                try:
                    log.debug(
                        f"Queuing after possible action {card}: {action}"
                    )
                    new_env.step(card, action)
                    if new_env.opponent_counter_life <= 0:
                        if not with_lucky_wins and env.unknown_lands_in_deck_on_combo > 0:
                            log.debug("Ignoring lucky win...")
                        else:
                            log.info(
                                f"You won at turn {new_env.counter_turn} "
                                f"(lands in deck: {sum(isinstance(c, MTGLand) for c in new_env.library)}, "
                                f"cards in library: {len(new_env.library)}, "
                                f"keep at {new_env.kept_at})!"
                            )
                            return EXECUTION_SUCCEEDED, new_env
                    new_env_hash = new_env.functional_hash
                    if new_env_hash not in self.explored_hashes:
                        self.env_queues[new_env.counter_turn].append(new_env)
                        self.explored_hashes.add(new_env_hash)
                    else:
                        log.debug(f"Optimization (hash): branch already explored")
                except GameLostException:
                    continue  # pick the next action
        return EXECUTION_FAILED, None

    def is_useless_game(self, env):
        return env.counter_turn >= 2 and len(env.lands) == 0

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

    def keep_and_mull(self):
        # the initial env is already enqueued and represents the keep at 7
        for i in range(6, 2, -1):  # let's *also* mull to 6, 5, 4, and 3
            self.mull_to(i)

    def start_with(self, hand_size):
        # here the initial env is already enqueued and represents the keep at 7
        if self.is_keep(hand_size):
            if hand_size != 7:
                self.mull_to(hand_size)
                self.env_queues[0].pop(0)  # remove initial env: simulation won't start
            # else: nothing do (env with 7-card hand is already enqueued)
        else:
            self.env_queues[0].pop(0)  # remove initial env: simulation won't start

    def mull_to(self, new_hand_size):
        log.debug(f"Mull to: {new_hand_size}")
        env = deepcopy(self.env_queues[0][0])  # clone the initial env
        env.kept_at = new_hand_size
        while len(env.hand) > 0:  # shuffle back initial hand
            env.engine.put_from_hand_to_library(env.hand[0])
        log.debug("Shuffling library...")
        random.shuffle(env.library)

        env.engine.draw_cards(7)
        cards_to_put_on_the_bottom = 7 - new_hand_size
        has_dead_card = True
        while cards_to_put_on_the_bottom > 0 and has_dead_card:
            dead_card = env.engine.get_dead_card_in_hand()
            if dead_card:
                env.mulled_bottom.append(dead_card)
                env.engine.put_from_hand_to_library(dead_card)
                cards_to_put_on_the_bottom -= 1
                if isinstance(dead_card, MTGLand):
                    env.known_lands_bottom += 1
            else:
                has_dead_card = False
        if cards_to_put_on_the_bottom == 0:
            self.env_queues[0].append(env)
            self.explored_hashes.add(env.functional_hash)
            return
        # create different envs, each one with a different card to mull
        for nuple in itertools.combinations(range(len(env.hand)), cards_to_put_on_the_bottom):
            new_env = deepcopy(env)
            for i in reversed(nuple):  # from right to left, to not mess up with indices
                if isinstance(new_env.hand[i], MTGLand):
                    new_env.known_lands_bottom += 1
                new_env.mulled_bottom.append(new_env.hand[i])
                new_env.engine.put_from_hand_to_library(new_env.hand[i])
            new_env_hash = new_env.functional_hash
            if new_env_hash not in self.explored_hashes:
                self.env_queues[0].append(new_env)
                self.explored_hashes.add(new_env_hash)
            else:
                log.debug(f"Optimization (hash): branch already explored")

    def is_keep(self, hand_size):
        if hand_size == 3:
            return True

        hand = self.env_queues[0][0].hand
        library = self.env_queues[0][0].library

        lands_num = sum(1 for c in hand if isinstance(c, MTGLand) or isinstance(c, LandGrant))
        free_mana_num = sum(1 for c in hand if isinstance(c, LotusPetal))
        mv1_tutor_num = sum(1 for c in hand if isinstance(c, SaguWildling) or isinstance(c, GenerousEnt) or isinstance(c, TrollOfKhazadDum))
        mv1_dork_num = sum(1 for c in hand if isinstance(c, ElvesOfDeepShadow))
        mv2_tutor_num = sum(1 for c in hand if isinstance(c, GatecreeperVine))
        mv2_draw = sum(1 for c in hand if isinstance(c, WindingWay) or isinstance(c, MalevolentRumble))
        dread_return_left = sum(1 for c in library if isinstance(c, DreadReturn))
        giant_left = sum(1 for c in library if isinstance(c, LotlethGiant))
        draw_creatures = sum(1 for c in hand if isinstance(c, WindingWay) or isinstance(c, LeadTheStampede))

        if (dread_return_left == 0 or giant_left == 0) and draw_creatures == 0:
            return False

        if lands_num >= 2:
            return True
        if lands_num == 1 and mv1_tutor_num >= 1:
            # we need to exclude the case Swamp + Sagu
            if mv1_tutor_num == 1 and any(c for c in hand if isinstance(c, Swamp)) and any(c for c in hand if isinstance(c, SaguWildling)):
                pass  # not a keep
            else:
                return True
        # TODO: fix below: if land is Swamp some plays are not possible (e.g. Elves ramp)
        # TODO: improve below: maybe some hands with Forest + Tinder Wall are keep?
        if lands_num == 1 and free_mana_num >= 1 and mv2_tutor_num >= 1:
            return True
        if lands_num == 1 and mv1_dork_num >= 1 and mv2_tutor_num >= 1:
            return True
        if lands_num == 1 and mv1_dork_num >= 1 and mv2_draw >= 1:
            return True
        if lands_num == 0 and free_mana_num >= 1 and mv1_tutor_num >= 2:
            return True
        if lands_num == 0 and free_mana_num >= 1 and mv1_dork_num >= 1 and mv1_tutor_num >= 1 and mv2_tutor_num >= 1:
            return True
        if lands_num == 0 and free_mana_num >= 2 and mv1_tutor_num >= 1 and mv2_tutor_num >= 1:
            return True

        return False
