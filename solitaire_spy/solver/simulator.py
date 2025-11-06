import logging
import timeit
import multiprocessing
from collections import defaultdict
from copy import deepcopy
from concurrent.futures import ProcessPoolExecutor, as_completed

from solitaire_spy.cards.creatures import TrollOfKhazadDum, GenerousEnt, SaguWildling
from solitaire_spy.cards.mtg_cards import MTGLand
from solitaire_spy.cards.spells import LotusPetal, LandGrant
from solitaire_spy.log import get_logger
from solitaire_spy.solver.core import Solver
from solitaire_spy.spy_solitaire import MTGSolitaire

log = get_logger(__name__, stdout_level=logging.DEBUG)

class SimulationSummary:
    def __init__(self, env, solving_time):
        self.initial_hand = env.initial_hand
        self.kept_at = env.kept_at
        self.counter_turn = env.counter_turn
        self.cards_in_library = len(env.library)
        self.lands_in_deck = sum(isinstance(c, MTGLand) for c in env.library)
        self.steps_log = env.steps_log
        self.solving_time = solving_time

    def __str__(self):
        return (f"Initial hand: {self.initial_hand}\n"
                f"Kept at: {self.kept_at}\n"
                f"Win at turn: {self.counter_turn}\n"
                f"Cards in library: {self.cards_in_library}\n"
                f"Lands in deck: {self.lands_in_deck}\n"
                f"Steps log: {self.steps_log}")


class ParallelSolver:
    def __init__(self, deck):
        self.deck = deepcopy(deck)

    def run(self, i):
        log.debug(f"Running simulation #{i+1}")
        solver_start_time = timeit.default_timer()
        winning_env = Solver(MTGSolitaire(self.deck, None)).solve()
        solving_time = timeit.default_timer() - solver_start_time
        if winning_env:
            summary = SimulationSummary(winning_env, solving_time)
            log.info(summary)
            return summary
        else:
            log.warning("Weird. It looks like this deck can lose, after all...")
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

    def simulate(self):
        simulation_start_time = timeit.default_timer()
        solver = ParallelSolver(self.deck)
        task_args = [(solver, "run", i) for i in range(self.num_sim)]
        completed_tasks = 0
        with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
            futures = {
                executor.submit(run_instance_method, arg): arg
                for arg in task_args
            }
            for future in as_completed(futures):
                summary = future.result()
                completed_tasks += 1
                log.info(f"Simulations completed: {completed_tasks}")
                self.summaries.append(summary)
        elapsed = timeit.default_timer() - simulation_start_time
        log.info(f"Overall simulation time: {elapsed:.2f} s")

    def print(self):
        max_turn = max(s.counter_turn for s in self.summaries)
        for i in range(2, max_turn + 1):
            games_won_by_i = len([s for s in self.summaries if s.counter_turn == i])
            print(
                f"Games won by turn {i}: "
                f"{games_won_by_i} "
                f"({games_won_by_i / len(self.summaries) * 100:.2f}%)"
            )

        print()
        for i in range(3, 8):
            hands_kept_at_i = len([s for s in self.summaries if s.kept_at == i])
            print(
                f"Hands kept at {i}: "
                f"{hands_kept_at_i} "
                f"({hands_kept_at_i / len(self.summaries) * 100:.2f}%)"
            )

        print()
        mana_t1 = defaultdict(int)  # mana_amount : occurrences
        mana_cards = [MTGLand, LotusPetal, TrollOfKhazadDum, GenerousEnt, LandGrant, SaguWildling]
        for summary in self.summaries:
            initial_mana = sum(
                1 for c in summary.initial_hand
                if any(isinstance(c, i) for i in mana_cards)
            )
            mana_t1[initial_mana] += 1
        for i in range(0, 8):
            print(
                f"T1 (pseudo-)mana {i}: "
                f"{mana_t1[i]} "
                f"({mana_t1[i] / len(self.summaries) * 100:.2f}%)"
            )
        print()

        zero_cards_left = sum(1 for s in self.summaries if s.cards_in_library == 0)
        print(
            f"0 cards left in library: {zero_cards_left} "
            f"({zero_cards_left / len(self.summaries) * 100:.2f}%)"
        )
        print(
            f"1+ cards left in library: {len(self.summaries) - zero_cards_left} "
            f"({(len(self.summaries) - zero_cards_left) / len(self.summaries) * 100:.2f}%)"
        )
        print()

        for i in range(sum(isinstance(c, MTGLand) for c in self.deck) + 1):
            lands_left = sum(1 for s in self.summaries if s.lands_in_deck == i)
            print(
                f"Lands left in library {i}: "
                f"{lands_left} "
                f"({lands_left / len(self.summaries) * 100:.2f}%)"
            )
        print()

        print(f"Average solving time: "
              f"{sum(s.solving_time for s in self.summaries) / len(self.summaries):.2f} s")
