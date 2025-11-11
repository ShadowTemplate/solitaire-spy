import difflib
import hashlib
import importlib
import inspect
import logging

from collections import Counter
from copy import deepcopy

from solitaire_spy.cards.creatures import *
from solitaire_spy.cards.lands import *
from solitaire_spy.cards.spells import *


from solitaire_spy.constants import *
from solitaire_spy.log import get_logger

log = get_logger(__name__, stdout_level=logging.WARNING)


def get_supported_cards_classes():
    instances = {}
    for m in ["creatures", "lands", "spells"]:
        module_name = f"{SOLITAIRE_SPY_CARDS_MODULE}.{m}"
        module = importlib.import_module(module_name)
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # only include classes defined in *this* module, not imported ones
            if obj.__module__ == module_name:
                try:
                    new_obj = obj()  # instantiate without args
                    instances[new_obj.name.lower()] = obj
                except Exception as e:
                    log.warning(f"Skipping {name}: {e}")
    return instances

def load_deck(deck_file=STOCK_DECK_PATH):
    log.info(f"Loading deck from {deck_file}...")
    instances = get_supported_cards_classes()
    deck = []
    with open(deck_file, "r") as f:
        for line in f.readlines():
            qty, card = line.rstrip("\n").split(" ", maxsplit=1)
            if card.lower() not in instances:
                raise Exception(f"Unsupported card: {card}")
            else:
                for _ in range(int(qty)):
                    deck.append(instances[card.lower()]())
    return deck


def get_deck_diff(deck, base_deck=BASE_DECK_PATH):
    if not isinstance(base_deck, list):
        base_deck = load_deck(base_deck)

    deck_counter = dict(Counter(c.name for c in deck))
    deck_text = "\n".join(sorted(f"{k}: {v}" for k, v in deck_counter.items()))
    base_deck_counter = dict(Counter(c.name for c in base_deck))
    base_deck_text = "\n".join(sorted(f"{k}: {v}" for k, v in base_deck_counter.items()))
    diff = difflib.unified_diff(
        base_deck_text.splitlines(),
        deck_text.splitlines(),
        n=0,
        lineterm=''
    )
    return '\n'.join(l for l in diff if not l.startswith(('---', '+++', '@@')))


def get_deck_hash(deck):
    s = ",".join(sorted(c.name for c in deck))
    return hashlib.sha1(s.encode()).hexdigest()


def deck_generator():
    # TODO:
    decks = []
    base_deck = load_deck()

    # 1 Troll of Khazad-dum
    # 4 Elves Of Deep Shadow
    # 2 Ornithopter Of Paradise
    # 2 Mesmeric Fiend
    # 1 Saruli Caretaker
    # 4 Tinder Wall

    for petal_number in range(0, 1):
        for troll_number in range(1, 2):
            for quirion_number in range(2, 3):
                for tinder_wall_number in range(4, 5):
                    for bird_number in range(0, 1):
                        if petal_number + troll_number + quirion_number + tinder_wall_number + bird_number <= 60 - len(base_deck):
                            new_deck = deepcopy(base_deck)
                            new_deck += petal_number * [LotusPetal()]
                            new_deck += troll_number * [TrollOfKhazadDum()]
                            new_deck += quirion_number * [QuirionRanger()]
                            new_deck += tinder_wall_number * [TinderWall()]
                            new_deck += bird_number * [OrnithopterOfParadise()]
                            while len(new_deck) < 60:
                                new_deck.append(MesmericFiend())
                            decks.append(new_deck)
    return decks
