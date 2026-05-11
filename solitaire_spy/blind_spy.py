import csv
import json
import os
import random
import re

from concurrent.futures import ThreadPoolExecutor

random.seed(42)


STARTING_LANDS_IN_DECK = 4  # 4L list
MIN_LANDS_IN_DECK = 1  # otherwise it's not blind
MAX_LANDS_IN_DECK = 2  # let's not consider 3 lands
MIN_DR_IN_DECK = 1  # otherwise it's useless
MAX_DR_IN_DECK = 2  # 4L and 5L lists have 2 DR (stock)
MIN_TARGET_IN_DECK = 1  # otherwise it's useless
MAX_TARGET_IN_DECK = 2  # 4L and 5L lists have 2 Giant (stock)
# With more time, we should set MAX_TARGET_IN_DECK to take into account a
# blind-Spy for another Spy (5 creatures on the board).
# This scenario is not easy, as you might not get Spy, but still win.

# 4L list has 41 creatures, but 3 are on the battlefield
MIN_CREATURES_IN_DECK = 17  # not counting the Giant to reanimate
MAX_CREATURES_IN_DECK = 37  # not counting the Giant to reanimate
# Below, blanks are all the remaining cards
MIN_BLANK_IN_DECK = 0  # virtually impossible, but hey...
MAX_BLANK_IN_DECK = 15  # 4L list has 14 spells and 1 Lotus Petal

CARDS_IN_DECK = 60
# The minimum number of cards required to win with a luck-spy is 5:
# Forest, Swamp, Elves of Deep Shadow, Overgrown Battlement, Balustrade Spy.
# For example, this could happen with a mulligan to 3 on turn 3 OTP.
MIN_CARDS_FOR_COMBO = 5
NUM_SIM = 1000000
MIN_CREATURES_TO_WIN = 3  # not counting the Giant to reanimate
MAX_CREATURES_TO_WIN = 37  # not counting the Giant to reanimate

THREADS = 6

def blind_spy(min_creatures_to_win):
    result_file = f"../resources/blind_spy/single_dr/blind_spy_{NUM_SIM}_{min_creatures_to_win + 3}.csv"
    with open(result_file, "w") as out_f:
        out_f.write(
            "lands_in_deck,"
            "drs_in_deck,"
            "targets_in_deck,"
            "creatures_in_deck,"
            "blanks_in_deck,"
            "win_%,fail_%,"
            "avg_creatures_in_gy\n"
        )
        for lands in range(MIN_LANDS_IN_DECK, MAX_LANDS_IN_DECK + 1):
            for dr in range(MIN_DR_IN_DECK, MAX_DR_IN_DECK + 1):
                for target in range(MIN_TARGET_IN_DECK, MAX_TARGET_IN_DECK + 1):
                    for creature in range(MIN_CREATURES_IN_DECK,
                                          MAX_CREATURES_IN_DECK + 1):
                        for blank in range(MIN_BLANK_IN_DECK, MAX_BLANK_IN_DECK + 1):
                            if lands + dr + target + blank + creature > CARDS_IN_DECK - MIN_CARDS_FOR_COMBO:
                                continue
                            print(
                                f"Deck: {lands} L, "
                                f"{dr} DR, "
                                f"{target} T, "
                                f"{creature} C, "
                                f"{blank} B, "
                                f"{min_creatures_to_win + 3} D"
                            )
                            deck = lands * ["L"] + dr * ["DR"] + target * [
                                "T"] + creature * ["C"] + blank * ["B"]
                            success_count, fail_count = 0, 0
                            creatures_gy = []
                            for _ in range(NUM_SIM):
                                random.shuffle(deck)
                                land_index = deck.index("L")
                                dr_index = deck.index("DR")
                                target_index = deck.index("T")
                                creatures_milled = deck[:land_index].count("C")
                                if (
                                        dr_index < land_index and
                                        target_index < land_index and
                                        creatures_milled >= min_creatures_to_win
                                ):
                                    success_count += 1
                                    creatures_gy.append(creatures_milled)
                                else:
                                    fail_count += 1
                            win = 100 * success_count / NUM_SIM
                            fail = 100 * fail_count / NUM_SIM
                            try:
                                avg = sum(creatures_gy) / success_count
                            except ZeroDivisionError:
                                avg = 0
                            print(
                                f"Success count: {win:.2f}% "
                                f"(avg creatures: {avg:.2f}), "
                                f"fail count: {fail:.2f}%."
                            )
                            out_f.write(
                                f"{lands},{dr},{target},{creature},{blank},{win:.2f},{fail:.2f},{avg:.2f}\n"
                            )
    return 0


def consolidate():
    csv_dir = "../resources/blind_spy/single_dr/"
    output_file = "../resources/blind_spy/blind_spy_consolidated.json"

    int_fields = {
        "lands_in_deck",
        "drs_in_deck",
        "targets_in_deck",
        "creatures_in_deck",
        "blanks_in_deck",
    }
    float_fields = {
        "win_%",
        "fail_%",
        "avg_creatures_in_gy",
    }

    records = []
    for filename in sorted(
            os.listdir(csv_dir),
            key=lambda f: int(re.search(r"_(\d+)\.csv$", f).group(1))
    ):
        if not filename.endswith(".csv"):
            continue
        match = re.search(r"_(\d+)\.csv$", filename)
        if not match:
            continue
        creatures_to_win = int(match.group(1))
        with open(os.path.join(csv_dir, filename), newline="") as f:
            for row in csv.DictReader(f):
                record = {"creatures_to_win": creatures_to_win}
                for key, value in row.items():
                    if key in int_fields:
                        record[key] = int(value)
                    elif key in float_fields:
                        record[key] = float(value)
                    else:
                        record[key] = value
                records.append(record)

    with open(output_file, "w") as f:
        json.dump(records, f, indent=2)


def simulate():
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        results = list(
            executor.map(
                blind_spy,
                range(MIN_CREATURES_TO_WIN, MAX_CREATURES_TO_WIN + 1)
            )
        )
    return results


if __name__ == '__main__':
    # uncomment the task you want to run
    # simulate()
    # consolidate()
    pass
