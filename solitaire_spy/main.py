import threading
import os
import random
import tkinter as tk

from solitaire_spy.cards.creatures import *
from solitaire_spy.cards.lands import *
from solitaire_spy.cards.spells import *
from solitaire_spy.constants import SEED
from solitaire_spy.spy_solitaire import MTGSolitaire


def seed_everything(seed):
    os.environ['PYTHONHASHSEED'] = str(seed)
    random.seed(seed)


def solitaire(env: MTGSolitaire):
    for _ in range(40):
        # time.sleep(3)
        print('---')
        possible_actions = env.engine.get_possible_actions()
        print('---')
        card, action = possible_actions[0]
        env.step(card, action)
        env.render()


def main():
    root = tk.Tk()
    root.title("MTGO at home - Turn 0")
    seed_everything(SEED)
    deck = []
    deck.append(Forest())
    deck.append(TinderWall())
    deck.append(TinderWall())
    deck.append(LotlethGiant())
    for _ in range(7):
        deck.append(Swamp())
    for _ in range(10):
        deck.append(MaskedVandal())
    # deck.append(Forest())
    # deck.append(HauntedMire())
    env = MTGSolitaire(deck, root)
    thread = threading.Thread(target=solitaire, args=[env], daemon=True)
    thread.start()
    root.geometry("1500x1800")
    root.mainloop()


if __name__ == '__main__':
    main()
