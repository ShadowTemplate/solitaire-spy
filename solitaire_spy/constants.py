import multiprocessing

SEED = 42
DECK_SIZE = 60
MTG_MAX_CARDS_IN_HAND = DECK_SIZE  # TODO: change to 7
STARTING_LIFE = 20
MANA_TYPES = ["W", "U", "B", "R", "G", "C"]
MAX_TURN = 8
RESULTS_PATH = "../resources/results/"
CARD_IMAGES_PATH = "../resources/images"
STOCK_DECK_PATH = "../resources/stock_main_no_initiative.txt"
BASE_DECK_PATH = "../resources/base_deck_rumble.txt"

MANA_STRATEGY_SCRBG = "CRBG"  # Specific, Colorless, Red, Black, Green
MANA_STRATEGY_SCRGB = "CRGB"  # Specific, Colorless, Red, Green, Black
MAX_SOLVER_RUNTIME = 10 * 60  # 15 minutes
MAX_INTERACTION_CARDS_IN_DECK = 8  # e.g. 4 Masked Vandal and 4 Mesmeric Fiend

SOLITAIRE_SPY_CARDS_MODULE = "solitaire_spy.cards"
CHECKPOINT_SIMULATIONS_EVERY_N = 10
MIN_TURN_WIN_POSSIBLE = 3
EXECUTORS_NUM = multiprocessing.cpu_count()

EXECUTION_SUCCEEDED = 0
EXECUTION_FAILED = -1
EXECUTION_TIMEOUT = -2
