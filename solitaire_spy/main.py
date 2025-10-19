import threading
import os
import random
import time
import tkinter as tk

from solitaire_spy.cards.creatures import *
from solitaire_spy.cards.lands import *
from solitaire_spy.cards.spells import *
from solitaire_spy.constants import SEED
from solitaire_spy.solver import Solver
from solitaire_spy.spy_solitaire import MTGSolitaire


def seed_everything(seed):
    os.environ['PYTHONHASHSEED'] = str(seed)
    random.seed(seed)


def best_move(possible_actions):
    for i, pair in enumerate(possible_actions):
        card, action = pair
        if card and card.name == "Balustrade Spy":
            return i
        if card and card.name == "Dread Return":
            return 51
    return 0


def solitaire(env: MTGSolitaire):
    while env.opponent_counter_life > 0:
        # time.sleep(1)
        print('---')
        possible_actions = env.engine.get_possible_actions()
        card, action = possible_actions[best_move(possible_actions)]
        env.step(card, action)
        env.render()
    print("You won!")


def get_t3_deck():
    deck = [Forest(), SaruliCaretaker(), Forest(), WallOfRoots(), WindingWay(),
            BalustradeSpy(), MesmericFiend(), MesmericFiend(), TrollOfKhazadDum(),
            SaguWildling(), MesmericFiend(), MesmericFiend(), MesmericFiend(), Swamp(),
            Forest()]
    for _ in range(50):
        deck.append(MesmericFiend())
    deck.append(DreadReturn())
    deck.append(LotlethGiant())
    return deck


def get_deck():
    return 4 * [BalustradeSpy()] + \
        2 * [DreadReturn()] + \
        4 * [ElvesOfDeepShadow()] + \
        3 * [Forest()] + \
        4 * [GenerousEnt()] + \
        4 * [LandGrant()] + \
        4 * [LeadTheStampede()] + \
        2 * [LotlethGiant()] + \
        3 * [MaskedVandal()] + \
        2 * [MesmericFiend()] + \
        2 * [OrnithopterOfParadise()] + \
        4 * [OvergrownBattlement()] + \
        4 * [SaguWildling()] + \
        4 * [SaruliCaretaker()] + \
        1 * [Swamp()] + \
        4 * [TinderWall()] + \
        1 * [TrollOfKhazadDum()] + \
        4 * [WallOfRoots()] + \
        4 * [WindingWay()]
        # 1 * [HauntedMire()]


def main_with_solver():
    seed_everything(SEED)
    deck = get_deck()
    env = MTGSolitaire(deck, None)
    Solver(env).solve()


def main_no_gui():
    seed_everything(SEED)
    deck = get_t3_deck()
    env = MTGSolitaire(deck, None)
    solitaire(env)


def main_with_gui():
    root = tk.Tk()
    root.title("MTGO at home - Turn 0")
    seed_everything(SEED)
    deck = get_t3_deck()
    env = MTGSolitaire(deck, root)
    thread = threading.Thread(target=solitaire, args=[env], daemon=True)
    thread.start()
    root.geometry("1500x2000")
    root.mainloop()


if __name__ == '__main__':
    main_with_solver()
