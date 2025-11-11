import timeit
import threading
import os
import random
import time
import tkinter as tk

from solitaire_spy.constants import SEED
from solitaire_spy.deck import load_deck, deck_generator
from solitaire_spy.solver.core import Solver
from solitaire_spy.solver.simulator import Simulator
from solitaire_spy.spy_solitaire import MTGSolitaire


def seed_everything(seed):
    os.environ['PYTHONHASHSEED'] = str(seed)
    random.seed(seed)


def solitaire(env: MTGSolitaire):
    def next_move(actions):
        for i, pair in enumerate(actions):
            c, _ = pair
            if c and c.name == "Balustrade Spy":
                return i
            if c and c.name == "Dread Return":
                return i
        return 0

    while env.opponent_counter_life > 0:
        # time.sleep(1)
        print('---')
        possible_actions = env.engine.get_possible_actions()
        card, action = possible_actions[next_move(possible_actions)]
        env.step(card, action)
        env.render()
    print("You won!")


def main_with_simulator():
    seed_everything(SEED)
    deck = load_deck()
    simulator = Simulator(deck, 1000)
    if simulator.simulate():
        simulator.log_stats()


def multi_deck_simulator():
    seed_everything(SEED)
    all_decks = deck_generator()
    for i, deck in enumerate(all_decks):
        simulator = Simulator(deck, 1000)
        if simulator.simulate():
            simulator.log_stats()


def main_with_solver():
    seed_everything(SEED)
    deck = load_deck()
    env = MTGSolitaire(deck, None)
    start_time = timeit.default_timer()
    env = Solver(env).solve()
    if env:
        print(env.steps_log)
    else:
        print("No solution found")
    elapsed = timeit.default_timer() - start_time
    print(f"Computation time: {elapsed:.2f} sec")


def main_no_gui():
    seed_everything(SEED)
    deck = load_deck()
    env = MTGSolitaire(deck, None)
    solitaire(env)


def main_with_gui():
    root = tk.Tk()
    root.title("MTGO at home - Turn 0")
    seed_everything(SEED)
    deck = load_deck()
    env = MTGSolitaire(deck, root)
    thread = threading.Thread(target=solitaire, args=[env], daemon=True)
    thread.start()
    root.geometry("1500x2000")
    root.mainloop()


if __name__ == '__main__':
    main_with_simulator()
    # multi_deck_simulator()
