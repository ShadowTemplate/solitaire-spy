import logging
import os
import pickle
import timeit
import multiprocessing
from collections import defaultdict, Counter
from copy import deepcopy
from concurrent.futures import ProcessPoolExecutor, as_completed

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
        self.initial_hand = env.initial_hand
        self.kept_at = env.kept_at
        self.counter_turn = env.counter_turn
        self.cards_in_library = len(env.library)
        self.lands_in_deck = sum(isinstance(c, MTGLand) for c in env.library)
        self.unknown_lands_in_deck_on_combo = env.unknown_lands_in_deck_on_combo  # added later
        self.interaction_count = env.interaction_count
        self.steps_log = env.steps_log
        self.solving_time = solving_time

    def __str__(self):
        return (f"Initial hand: {self.initial_hand}\n"
                f"Kept at: {self.kept_at}\n"
                f"Win at turn: {self.counter_turn}\n"
                f"Cards in library: {self.cards_in_library}\n"
                f"Lands in deck: {self.lands_in_deck}\n"
                f"Unknown lands in deck on combo: {self.unknown_lands_in_deck_on_combo}\n"
                f"Interaction count: {self.interaction_count}\n"
                f"Steps log: {self.steps_log}")


class ParallelSolver:
    def __init__(self, deck):
        self.deck = deepcopy(deck)

    def run(self, i):
        log.debug(f"Running simulation #{i+1}")
        solver_start_time = timeit.default_timer()
        winning_env = Solver(MTGSolitaire(self.deck, None)).solve(solver_start_time)
        solving_time = timeit.default_timer() - solver_start_time
        if winning_env:
            summary = SimulationSummary(winning_env, solving_time)
            log.debug(summary)
            return summary
        else:
            log.debug("No winning line.")
            return None


def run_instance_method(args):
    # helper function for pickling: unwraps the instance + method call
    instance, method_name, arg = args
    method = getattr(instance, method_name)
    return method(arg)


class Simulator:
    def __init__(self, deck, num_sim):
        self.deck = deck
        self.num_sim = num_sim
        self.summaries = []
        self.simulation_name = get_deck_hash(self.deck)
        self.result_file = f"{RESULTS_PATH}{self.simulation_name}.txt"
        self.deck_file = f"{RESULTS_PATH}{self.simulation_name}_deck.txt"
        self.pkl_file = f"{RESULTS_PATH}{self.simulation_name}.pkl"
        os.makedirs(f"{RESULTS_PATH}", exist_ok=True)

    def simulate(self, load_existing=True):
        if load_existing and os.path.exists(self.pkl_file):
            log.info(f"Loading past simulations: {self.pkl_file}")
            self.load()
            log.info(f"Loaded {len(self.summaries)} past simulations")
        log.info(50 * "-")
        log.info(get_deck_diff(self.deck))
        simulation_start_time = timeit.default_timer()
        solver = ParallelSolver(self.deck)
        task_args = [(solver, "run", i) for i in range(self.num_sim - len(self.summaries))]
        with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
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

    def log_stats(self):
        if not os.path.exists(self.deck_file):
            deck_counter = dict(Counter(c.name for c in self.deck))
            with open(self.deck_file, "w") as f:
                for k in sorted(deck_counter.keys()):
                    f.write(f"{deck_counter[k]} {k}\n")

        result_lines = [get_deck_diff(self.deck), ""]
        games_won_by_turn = {}
        max_turn = max(s.counter_turn for s in self.summaries)
        for i in range(2, max_turn + 1):
            games_won_by_i = len([s for s in self.summaries if s.counter_turn == i])
            line = (
                f"Games won by turn {i}: "
                f"{games_won_by_i} "
                f"({games_won_by_i / len(self.summaries) * 100:.2f}%)"
            )
            log.info(line)
            result_lines.append(line)
            with_interaction_lines = []
            for j in range(0, MAX_INTERACTION_CARDS_IN_DECK):
                with_j_interaction = len(
                    [s for s in self.summaries
                     if s.counter_turn == i and s.interaction_count == j]
                )
                if with_j_interaction > 0:
                    with_interaction_lines.append(
                        f"x={j}: {with_j_interaction} "
                        f"({with_j_interaction / len(self.summaries) * 100:.2f}%)"
                    )
            if len(with_interaction_lines) > 0:
                line = " L with x interactions: " + ", ".join(with_interaction_lines)
                log.info(line)
                result_lines.append(line)
            games_won_by_turn[i] = games_won_by_i
        for i in range(2, 7):  # set 'max_turn + 1' if you want to see all turns
            cumulative = sum(games_won_by_turn[j] for j in range(2, i + 1))
            line = (
                f"Games won by turn <= {i}: "
                f"{cumulative} "
                f"({cumulative / len(self.summaries) * 100:.2f}%)"
            )
            log.info(line)
            result_lines.append(line)

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
        for i in range(0, 8):
            line = (
                f"T1 (pseudo-)mana {i}: "
                f"{mana_t1[i]} "
                f"({mana_t1[i] / len(self.summaries) * 100:.2f}%)"
            )
            log.info(line)
            result_lines.append(line)
            mana_t1_by[i] = mana_t1[i]
        for i in range(0, 8):
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

        try:
            unknown_lands_in_deck_on_combo_1_plus = sum(
                1 for s in self.summaries if s.unknown_lands_in_deck_on_combo > 0
            )
            unknown_lands_in_deck_on_combo_0 = len(self.summaries) - unknown_lands_in_deck_on_combo_1_plus
            line = (
                f"Lands left in library 0: "
                f"{unknown_lands_in_deck_on_combo_0} "
                f"({unknown_lands_in_deck_on_combo_0 / len(self.summaries) * 100:.2f}%)"
            )
            log.info(line)
            result_lines.append(line)
            line = (
                f"Lands left in library 1+ (lucky win): "
                f"{unknown_lands_in_deck_on_combo_1_plus} "
                f"({unknown_lands_in_deck_on_combo_1_plus / len(self.summaries) * 100:.2f}%)"
            )
            log.info(line)
            result_lines.append(line)
        except AttributeError:
            # 'unknown_lands_in_deck_on_combo' was added later and may not be present
            pass

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

    def save(self):
        log.debug(f"Saving simulator results to {self.pkl_file}")
        with open(self.pkl_file, "wb") as f:
            pickle.dump(self, f)

    def load(self):
        log.debug(f"Loading simulator results from {self.pkl_file}")
        with open(self.pkl_file, "rb") as f:
            for s in pickle.load(f).summaries:
                self.summaries.append(s)
