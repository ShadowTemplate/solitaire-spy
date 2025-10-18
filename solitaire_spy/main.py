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
    for _ in range(30):
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
    deck.append(HauntedMire())
    deck.append(Swamp())
    deck.append(SaruliCaretaker())
    deck.append(QuirionRanger())
    for _ in range(50):
        deck.append(MaskedVandal())
        deck.append(MesmericFiend())
    # deck.append(Forest())
    # deck.append(HauntedMire())
    env = MTGSolitaire(deck, root)
    thread = threading.Thread(target=solitaire, args=[env], daemon=True)
    thread.start()
    root.geometry("1500x1800")
    root.mainloop()


if __name__ == '__main__':
    main()
