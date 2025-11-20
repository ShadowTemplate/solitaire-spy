import logging
import os
import pickle
import timeit
from functools import reduce
from operator import mul
from collections import defaultdict, Counter
from copy import deepcopy
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import groupby

from solitaire_spy.cards.creatures import *
from solitaire_spy.cards.mtg_cards import MTGLand
from solitaire_spy.cards.spells import LotusPetal, LandGrant
from solitaire_spy.constants import *
from solitaire_spy.deck import get_deck_diff, get_deck_hash
from solitaire_spy.log import get_logger
from solitaire_spy.solver.core import Solver
from solitaire_spy.spy_solitaire import MTGSolitaire

log = get_logger(__name__, log_format="%(message)s", stdout_level=logging.INFO)

class SimulationSummary:
    def __init__(self, env, solving_time):
        if env:
            self.initial_hand = env.initial_hand
            self.kept_at = env.kept_at
            self.counter_turn = env.counter_turn
            self.cards_in_library = len(env.library)
            self.unknown_lands_in_deck_on_combo = env.unknown_lands_in_deck_on_combo
            self.mulled_bottom = env.mulled_bottom
            self.interaction_count = env.interaction_count
            self.steps_log = env.steps_log
        else:
            self.initial_hand = []
            self.kept_at = -1
            self.counter_turn = -1
            self.cards_in_library = -1
            self.unknown_lands_in_deck_on_combo = -1
            self.mulled_bottom = []
            self.interaction_count = -1
            self.steps_log = []
        self.solving_time = solving_time

    def __str__(self):
        return (f"Initial hand: {self.initial_hand}\n"
                f"Kept at: {self.kept_at}\n"
                f"Win at turn: {self.counter_turn}\n"
                f"Cards in library: {self.cards_in_library}\n"
                f"Unknown lands in deck on combo: {self.unknown_lands_in_deck_on_combo}\n"
                f"Interaction count: {self.interaction_count}\n"
                f"Steps log: {self.steps_log}")


class ParallelSolver:
    def __init__(self, deck):
        self.deck = deepcopy(deck)

    def run(self, i, with_lucky_wins, initial_hand_size):
        log.debug(f"Running simulation #{i+1}")
        solver_start_time = timeit.default_timer()
        result, winning_env = Solver(MTGSolitaire(self.deck, None)).solve(
            early_abort=False,
            start_time=solver_start_time,
            with_lucky_wins=with_lucky_wins,
            initial_hand_size=initial_hand_size,
        )
        solving_time = timeit.default_timer() - solver_start_time
        if winning_env:
            summary = SimulationSummary(winning_env, solving_time)
            log.debug(summary)
            return summary
        else:  # no winning line
            log.debug("No winning line.")
            if (
                    initial_hand_size  # we need to track mulls here
                    and result == EXECUTION_FAILED
            ):
                summary = SimulationSummary(None, solving_time)
                log.debug(summary)
                return summary
            else:
                return None

def run_instance_method(args):
    # helper function for pickling: unwraps the instance + method call
    instance, method_name, arg = args
    method = getattr(instance, method_name)
    return method(*arg)


class Simulator:
    def __init__(self, deck, num_sim, with_lucky_wins=True, initial_hand_size=None):
        self.deck = deck
        self.num_sim = num_sim
        self.summaries = []
        self.simulation_name = get_deck_hash(self.deck)
        self.with_lucky_wins = with_lucky_wins
        self.initial_hand_size = initial_hand_size
        self.deck_file = f"{RESULTS_PATH}{self.simulation_name}_deck.txt"
        self.result_file = f"{RESULTS_PATH}{self.simulation_name}"
        self.pkl_file = f"{RESULTS_PATH}{self.simulation_name}"
        if not with_lucky_wins:
            self.result_file += "_no_lw"
            self.pkl_file += "_no_lw"
        if initial_hand_size:
            self.result_file += f"_hs{initial_hand_size}"
            self.pkl_file += f"_hs{initial_hand_size}"
        self.result_file += ".txt"
        self.pkl_file += ".pkl"

        os.makedirs(f"{RESULTS_PATH}", exist_ok=True)

    def simulate(self, load_existing=True):
        log.info(f"Simulations with initial hand size: {self.initial_hand_size}")
        if load_existing and os.path.exists(self.pkl_file):
            log.info(f"Loading past simulations: {self.pkl_file}")
            self.summaries += self.load(self.pkl_file)
            log.info(f"Loaded {len(self.summaries)} past simulations")
        log.info(50 * "-")
        log.info(get_deck_diff(self.deck))
        simulation_start_time = timeit.default_timer()
        solver = ParallelSolver(self.deck)
        task_args = [
            (solver, "run", (i, self.with_lucky_wins, self.initial_hand_size))
            for i in range(self.num_sim - len(self.summaries))
        ]
        with ProcessPoolExecutor(max_workers=EXECUTORS_NUM) as executor:
            futures = {
                executor.submit(run_instance_method, arg): arg
                for arg in task_args
            }
            for future in as_completed(futures):
                summary = future.result()
                if summary:
                    self.summaries.append(summary)
                if len(self.summaries) % CHECKPOINT_SIMULATIONS_EVERY_N == 0:
                    log.info(f"Simulations completed: {len(self.summaries)}")
                    self.save()
        elapsed = timeit.default_timer() - simulation_start_time
        log.info(f"Overall simulation time: {elapsed:.2f} s")
        self.save()
        if len(self.summaries) < self.num_sim:
            log.info("Some simulations are missing: restarting...")
            self.simulate()

    def _save_deck_if_needed(self):
        if not os.path.exists(self.deck_file):
            deck_counter = dict(Counter(c.name for c in self.deck))
            with open(self.deck_file, "w") as f:
                for k in sorted(deck_counter.keys()):
                    f.write(f"{deck_counter[k]} {k}\n")

    def _get_games_won_by_turn(self, summaries, interested_in_turn_up_to, with_log=True):
        result_lines = []
        games_won_at_turn = {}
        for i in range(MIN_TURN_WIN_POSSIBLE, interested_in_turn_up_to):
            games_won_at_i = len([s for s in summaries if s.counter_turn == i])
            line = (
                f"Games won at turn {i}: "
                f"{games_won_at_i} "
                f"({games_won_at_i / len(summaries) * 100:.2f}%)"
            )
            if with_log:
                log.info(line)
            result_lines.append(line)
            with_interaction_lines = []
            for j in range(0, MAX_INTERACTION_CARDS_IN_DECK):
                with_j_interaction = len(
                    [s for s in summaries
                     if s.counter_turn == i and s.interaction_count == j]
                )
                if with_j_interaction > 0:
                    with_interaction_lines.append(
                        f"x={j}: {with_j_interaction} "
                        f"({with_j_interaction / len(summaries) * 100:.2f}%)"
                    )
            if len(with_interaction_lines) > 0:
                line = " L with x interactions: " + ", ".join(with_interaction_lines)
                if with_log:
                    log.info(line)
                result_lines.append(line)
            games_won_at_turn[i] = games_won_at_i
        cumulatives = {}
        for i in range(MIN_TURN_WIN_POSSIBLE, interested_in_turn_up_to):
            cumulative = sum(
                games_won_at_turn[j] for j in range(MIN_TURN_WIN_POSSIBLE, i + 1))
            line = (
                f"Games won by turn <= {i}: "
                f"{cumulative} "
                f"({cumulative / len(summaries) * 100:.2f}%)"
            )
            cumulatives[i] = cumulative
            if with_log:
                log.info(line)
            result_lines.append(line)
        return result_lines, games_won_at_turn, cumulatives

    def log_stats(self):
        self._save_deck_if_needed()

        result_lines = [get_deck_diff(self.deck), ""]
        max_turn = max(s.counter_turn for s in self.summaries)
        interested_in_turn_up_to = min(
            max_turn, 7
        )  # set 'max_turn + 1' to see all turns
        new_lines, _, _ = self._get_games_won_by_turn(
            self.summaries,
            interested_in_turn_up_to,
        )
        result_lines += new_lines

        log.info("")
        result_lines.append("")
        hands_kept_by = {}
        for i in range(3, 8):
            hands_kept_at_i = len([s for s in self.summaries if s.kept_at == i])
            line = (
                f"Hands kept at {i}: "
                f"{hands_kept_at_i} "
                f"({hands_kept_at_i / len(self.summaries) * 100:.2f}%)"
            )
            log.info(line)
            result_lines.append(line)
            hands_kept_by[i] = hands_kept_at_i
        for i in range(3, 8):
            cumulative = sum(hands_kept_by[j] for j in range(i, 8))
            line = (
                f"Hands kept at {i}+: "
                f"{cumulative} "
                f"({cumulative / len(self.summaries) * 100:.2f}%)"
            )
            log.info(line)
            result_lines.append(line)

        log.info("")
        result_lines.append("")
        mana_t1 = defaultdict(int)  # mana_amount : occurrences
        mana_cards = [MTGLand, LotusPetal, TrollOfKhazadDum, GenerousEnt, LandGrant, SaguWildling]
        for summary in self.summaries:
            initial_mana = sum(
                1 for c in summary.initial_hand
                if any(isinstance(c, i) for i in mana_cards)
            )
            mana_t1[initial_mana] += 1
        mana_t1_by = {}
        for i in range(1, 8):
            line = (
                f"T1 (pseudo-)mana {i}: "
                f"{mana_t1[i]} "
                f"({mana_t1[i] / len(self.summaries) * 100:.2f}%)"
            )
            log.info(line)
            result_lines.append(line)
            mana_t1_by[i] = mana_t1[i]
        for i in range(1, 8):
            cumulative = sum(mana_t1_by[j] for j in range(i, 8))
            line = (
                f"T1 (pseudo-)mana {i}+: "
                f"{cumulative} "
                f"({cumulative / len(self.summaries) * 100:.2f}%)"

            )
            log.info(line)
            result_lines.append(line)

        log.info("")
        result_lines.append("")
        zero_cards_left = sum(1 for s in self.summaries if s.cards_in_library == 0)
        line = (
            f"0 cards left in library: {zero_cards_left} "
            f"({zero_cards_left / len(self.summaries) * 100:.2f}%)"
        )
        log.info(line)
        result_lines.append(line)

        line = (
            f"1+ cards left in library: {len(self.summaries) - zero_cards_left} "
            f"({(len(self.summaries) - zero_cards_left) / len(self.summaries) * 100:.2f}%)"
        )
        log.info(line)
        result_lines.append(line)

        log.info("")
        result_lines.append("")

        unknown_lands_in_deck_on_combo_1_plus = sum(
            1 for s in self.summaries if s.unknown_lands_in_deck_on_combo > 0 and s.kept_at > 0
        )
        not_played = sum(1 for s in self.summaries if s.kept_at == -1)
        unknown_lands_in_deck_on_combo_0 = len(self.summaries) - unknown_lands_in_deck_on_combo_1_plus - not_played
        line = (
            f"Scientific wins: "
            f"{unknown_lands_in_deck_on_combo_0} "
            f"({unknown_lands_in_deck_on_combo_0 / len(self.summaries) * 100:.2f}%)"
        )
        log.info(line)
        result_lines.append(line)
        line = (
            f"Lucky wins (1+ land in deck): "
            f"{unknown_lands_in_deck_on_combo_1_plus} "
            f"({(unknown_lands_in_deck_on_combo_1_plus) / len(self.summaries) * 100:.2f}%)"
        )
        log.info(line)
        result_lines.append(line)
        line = (
            f"Mulligan: "
            f"{not_played} "
            f"({(not_played) / len(self.summaries) * 100:.2f}%)"
        )
        log.info(line)
        result_lines.append(line)
        for i in range(MIN_TURN_WIN_POSSIBLE, interested_in_turn_up_to):
            lucky_wins_on_turn_i = sum(
                1 for s in self.summaries
                if s.unknown_lands_in_deck_on_combo > 0 and s.counter_turn == i
            )
            if lucky_wins_on_turn_i > 0:
                line = (
                    f" L on turn {i}: "
                    f"{lucky_wins_on_turn_i} "
                    f"({lucky_wins_on_turn_i / len(self.summaries) * 100:.2f}%)"
                )
                log.info(line)
                result_lines.append(line)

        log.info("")
        result_lines.append("")
        line = (
            f"Average solving time: "
            f"{sum(s.solving_time for s in self.summaries) / len(self.summaries):.2f} s"

        )
        log.info(line)
        result_lines.append(line)
        with open(self.result_file, "w") as f:
            for line in result_lines:
                f.write(line)
                f.write("\n")

        if self.initial_hand_size == 3:
            self.log_aggregated_stats()

    def log_aggregated_stats(self):
        result_lines = ["\nStats over all initial hand size:"]
        summaries = {}
        for i in range(3, 8):
            pkl_file = f"{self.pkl_file[:-5]}{i}.pkl"
            summaries[i] = self.load(pkl_file)

        def all_equal(iterable):
            g = groupby(iterable)
            return next(g, True) and not next(g, False)

        if not all_equal([len(summaries[s]) for s in summaries]):
            raise Exception("Unequal number of summaries across simulations")

        mulligan_number = {}  # k: initial hand size; v: number of hands mulligan'ed
        for i in range(3, 8):
            mulligan_number[i] = sum(1 for s in summaries[i] if s.kept_at == -1)

        max_turn = max(s.counter_turn for s in self.summaries)
        interested_in_turn_up_to = min(
            max_turn, 7
        )  # set 'max_turn + 1' to see all turns
        all_games_won_at_turn = {}  # k: initial hand size; v: dictionary of games_won_at_turn_i
        for i in range(3, 8):
            new_lines, games_won_at_turn, cumulatives = self._get_games_won_by_turn(
                summaries[i],
                interested_in_turn_up_to,
                with_log=False,
            )
            all_games_won_at_turn[i] = games_won_at_turn
        won_later = 1
        for i in range(MIN_TURN_WIN_POSSIBLE, interested_in_turn_up_to):
            prob_win_at_turn_i = 0
            prob_mulls = []
            for j in range(7, 2, -1):
                hands_kept_at_j = len(summaries[j]) - mulligan_number[j]
                p_keep_at_j = hands_kept_at_j / len(summaries[j])
                games_won_on_turn_i_at_j = all_games_won_at_turn[j][i] / hands_kept_at_j
                p_mull_before_j = reduce(mul, prob_mulls, 1)
                prob_win_at_turn_i += p_mull_before_j * p_keep_at_j * games_won_on_turn_i_at_j
                prob_mulls.append(1 - p_keep_at_j)
            line = f"P(win_at_turn_{i}) = {prob_win_at_turn_i * 100:.2f}%"
            log.info(line)
            result_lines.append(line)
            won_later -= prob_win_at_turn_i
        line = f"P(win_at_turn_{interested_in_turn_up_to}+) = {won_later * 100:.2f}%"
        log.info(line)
        result_lines.append(line)

        with open(self.result_file, "a") as f:
            for line in result_lines:
                f.write(line)
                f.write("\n")

    def save(self):
        log.debug(f"Saving simulator results to {self.pkl_file}")
        with open(self.pkl_file, "wb") as f:
            pickle.dump(self, f)

    def load(self, pkl_file):
        log.debug(f"Loading simulator results from {pkl_file}")
        with open(pkl_file, "rb") as f:
            return pickle.load(f).summaries
