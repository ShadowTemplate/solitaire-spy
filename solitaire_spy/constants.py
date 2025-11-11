SEED = 42
DECK_SIZE = 60
MTG_MAX_CARDS_IN_HAND = DECK_SIZE  # TODO: change to 7
STARTING_LIFE = 20
MANA_TYPES = ["W", "U", "B", "R", "G", "C"]
MAX_TURN = 8
CARD_IMAGES_PATH = "../resources/images"

MANA_STRATEGY_SCRBG = "CRBG"  # Specific, Colorless, Red, Black, Green
MANA_STRATEGY_SCRGB = "CRGB"  # Specific, Colorless, Red, Green, Black
MAX_SOLVER_RUNTIME = 10 * 60  # 10 minutes
MAX_INTERACTION_CARDS_IN_DECK = 8  # e.g. 4 Masked Vandal and 4 Mesmeric Fiend
