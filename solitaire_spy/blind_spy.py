import csv
import json
import os
import random

from concurrent.futures import ThreadPoolExecutor

random.seed(42)

# Change this parameter if you want to try different deck builds. I've tried [39, 42].
STARTING_CREATURES_IN_DECK = 41

# SIMULATION BOARD STATE (SPY TRIGGER ON THE STACK)
MIN_LANDS_IN_DECK = 1  # otherwise it's not blind
MAX_LANDS_IN_DECK = 2  # let's not consider 3+ lands (unlikely to go blind in that spot)
MIN_CREATURES_ON_BOARD = 3  # otherwise you can't flashback anything
MAX_CREATURES_ON_BOARD = 5  # with 5 creatures you enable a double Dread Return, for extra win-cons
MIN_DR_IN_DECK = 1  # otherwise it's useless to go off
MAX_DR_IN_DECK = 2  # 4L and 5L lists have 2 DR (stock)
MIN_GIANT_IN_DECK = 1  # otherwise it's useless to go off
MAX_GIANT_IN_DECK = 2  # 4L and 5L lists have 2 Giant (stock)
MIN_SPY_IN_DECK = 0  # rare, but possible: 1 Spy on the battlefield and 3 in hand
MAX_SPY_IN_DECK = 3  # 1 is on the battlefield, triggering the simulation, and 3 more in the deck
MIN_CREATURES_IN_DECK = 17  # non-Spy, non-Giant creatures

CARDS_IN_DECK = 60
NUM_SIM = 1000000
SIM_THREADS = 8

# LEGEND:
# L = LAND [IN DECK]
# DR = DREAD RETURN [IN DECK]
# G = LOTLETH GIANT [IN DECK]
# S = BALUSTRADE SPY
# BS = BALUSTRADE SPY ON THE BATTLEFIELD
# DS = BALUSTRADE SPY IN DECK
# C = CREATURE (non-Spy, non-Giant)
# BC = CREATURE ON THE BATTLEFIELD (non-Spy, non-Giant)
# DC = CREATURE IN DECK (non-Spy, non-Giant)


def generate_configs():
    configs = []
    for lands_in_deck in range(MIN_LANDS_IN_DECK, MAX_LANDS_IN_DECK + 1):
        for creatures_on_board in range(MIN_CREATURES_ON_BOARD, MAX_CREATURES_ON_BOARD + 1):
            for drs_in_deck in range(MIN_DR_IN_DECK, MAX_DR_IN_DECK + 1):
                for giants_in_deck in range(MIN_GIANT_IN_DECK, MAX_GIANT_IN_DECK + 1):
                    for spies_in_deck in range(MIN_SPY_IN_DECK, MAX_SPY_IN_DECK + 1):
                        for creatures_in_deck in range(MIN_CREATURES_IN_DECK, STARTING_CREATURES_IN_DECK + 1):
                            if creatures_in_deck + spies_in_deck + giants_in_deck + creatures_on_board > STARTING_CREATURES_IN_DECK:
                                continue
                            configs.append((lands_in_deck, creatures_on_board, drs_in_deck, giants_in_deck, spies_in_deck, creatures_in_deck))
    return configs


def _go_blind(creatures_on_board, deck):
    land_index = deck.index("L")
    gy = deck[:land_index + 1]  # land is milled
    remaining_deck = deck[land_index + 1:]
    all_creatures_in_gy = gy.count("DC") + gy.count("G") + gy.count("DS")
    lands_remaining = remaining_deck.count("L")
    drs_milled = gy.count("DR")
    giants_milled = gy.count("G")
    spies_milled = gy.count("DS")
    giant_damage = all_creatures_in_gy - 1 + 3  # -G to reanimate +3 creatures to sac

    if drs_milled == 0:  # land milled before DR
        return False, 0

    # We have hit (at least) 1 DR before the land. Implement strategies described here:
    # https://docs.google.com/spreadsheets/d/18xDeWn4Xl49WQNfKuFoKms785DGDeiP6dfzDv0W3zTA/edit?usp=sharing

    # condition A
    if creatures_on_board < 5 and giants_milled == 0:
        return False, 0

    # condition B
    if creatures_on_board < 5 and giants_milled > 0:
        return True, giant_damage

    # condition C
    if creatures_on_board >= 5 and giants_milled == 0 and spies_milled == 0:
        return False, 0

    # condition D
    if creatures_on_board >= 5 and drs_milled == 2 and giants_milled == 2 and spies_milled == 0:
        return True, 2 * giant_damage + 2

    # condition E
    if creatures_on_board >= 5 and giants_milled > 0 and spies_milled == 0:
        return True, giant_damage

    # condition F
    if creatures_on_board >= 5 and lands_remaining == 1 and drs_milled == 1 and giants_milled > 0:
        return True, giant_damage

    # condition G
    if creatures_on_board >= 5 and lands_remaining == 0 and drs_milled == 2 and giants_milled == 2 and spies_milled > 0:
        # we are going to win anyway, but let's maximize damage
        if 2 * giant_damage + 2 > STARTING_CREATURES_IN_DECK - 1:
            return True, 2 * giant_damage + 2
        else:
            return True, deck.count("DC") + deck.count("G") + deck.count("DS") + 5 - 1

    # condition H
    if creatures_on_board >= 5 and lands_remaining == 0:
        return True, deck.count("DC") + deck.count("G") + deck.count("DS") + 5 - 1  # board is sacced, 1 creature left on the battlefield

    # condition I
    if creatures_on_board >= 5 and lands_remaining == 1 and drs_milled == 2 and giants_milled == 2 and spies_milled > 0:
        # in real life, you would count how many creatures you have in the gy and proceed as follows:
        # a) 2 Giants are lethal: DR on Giant twice (can't afford the risk of a shitty Spy)
        # b) 1 Giant is lethal: Blind-Spy + DR on Giant (no risk, maximize damage)
        # c) 2 Giants are not lethal: Blind-Spy and hope it's enough (have to take the risk)
        # For simplicity, we'll assume the opponent has 20 life and choose accordingly
        if 2 * giant_damage + 2 >= 20:  # case a
            return True, 2 * giant_damage + 2
        else:  # case b and c
            other_land_index = remaining_deck.index("L")
            expanded_gy = deck[:other_land_index + 1]  # land is milled
            return True, expanded_gy.count("DC") + expanded_gy.count("G") + expanded_gy.count("DS") + 5 - 1  # board is sacced, 1 creature left on the battlefield

    # condition L
    other_land_index = remaining_deck.index("L")
    expanded_gy = deck[:other_land_index + 1]  # land is milled
    return True, expanded_gy.count("DC") + expanded_gy.count("G") + expanded_gy.count("DS") + 5 - 1  # board is sacced, 1 creature left on the battlefield


def blind_spy_double_dr(config):
    lands_in_deck, creatures_on_board, drs_in_deck, giants_in_deck, spies_in_deck, creatures_in_deck = config
    signature = f"{creatures_on_board}BC_{lands_in_deck}L_{drs_in_deck}DR_{giants_in_deck}G_{spies_in_deck}DS_{creatures_in_deck}DC"
    result_file = f"../resources/blind_spy/double_dr/blind_spy_{signature}_{NUM_SIM}.csv"
    print(result_file)
    if os.path.isfile(result_file):  # simulation already executed, skip it
        return
    print(f"Board: 1 S, {creatures_on_board - 1} C")
    print(f"Deck: {lands_in_deck} L, {drs_in_deck} DR, {giants_in_deck} G, {spies_in_deck} S, {creatures_in_deck} C")
    print(f"Total: {lands_in_deck + drs_in_deck + giants_in_deck + spies_in_deck + creatures_in_deck} relevant cards in deck")
    print(config)
    # due to input config constraints, single-DR win is always possible (at least 1 Giant, DR, and 17 creatures in deck)
    deck = lands_in_deck * ["L"] + drs_in_deck * ["DR"] + giants_in_deck * ["G"] + spies_in_deck * ["DS"] + creatures_in_deck * ["DC"]
    with open(result_file, "w") as out_f:
        out_f.write(
            "creatures_on_board,"
            "lands_in_deck,"
            "drs_in_deck,"
            "giants_in_deck,"
            "spies_in_deck,"
            "creatures_in_deck,"
            "damage\n"
        )
        for _ in range(NUM_SIM):
            random.shuffle(deck)
            _, damage = _go_blind(creatures_on_board, deck)
            out_f.write(
                f"{creatures_on_board},"
                f"{lands_in_deck},"
                f"{drs_in_deck},"
                f"{giants_in_deck},"
                f"{spies_in_deck},"
                f"{creatures_in_deck},"
                f"{damage}\n"
            )
    # success_count, fail_count = 0, 0
    # damages = []
    # win = 100 * success_count / NUM_SIM
    # fail = 100 * fail_count / NUM_SIM
    # try:
    #     avg = sum(damages) / success_count
    #     median = damages[len(damages) // 2]
    # except ZeroDivisionError:
    #     avg, median = 0, 0
    # print(
    #     f"Success count: {win:.2f}% "
    #     f"(avg creatures: {avg:.2f}, median creatures: {median:.2f}), "
    #     f"fail count: {fail:.2f}%."
    # )


def simulate_double_dr():
    configs = generate_configs()
    print(f"Simulating {len(configs)} configs...")
    with ThreadPoolExecutor(max_workers=SIM_THREADS) as executor:
        results = list(
            executor.map(
                blind_spy_double_dr,
                configs
            )
        )
    return results


def consolidate_double_dr():
    source_dir = "../resources/blind_spy/double_dr"
    config_fields = ["creatures_on_board", "lands_in_deck", "drs_in_deck", "giants_in_deck", "spies_in_deck", "creatures_in_deck"]
    records = []
    for filename in sorted(os.listdir(source_dir)):
        if not filename.endswith(".csv"):
            continue
        with open(os.path.join(source_dir, filename)) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        total = len(rows)
        damage_values = [int(row["damage"]) for row in rows]
        config = {k: int(rows[0][k]) for k in config_fields}
        freq = {}
        for d in damage_values:
            freq[d] = freq.get(d, 0) + 1
        record = dict(config)
        for x in range(3, 2 * STARTING_CREATURES_IN_DECK + 1):
            at_least_x_damage = [d for d in damage_values if d >= x]
            record[f"damage_{x}"] = len(at_least_x_damage)
            record[f"win_{x}%"] = len(at_least_x_damage) / total
            record[f"lose_{x}%"] = 1 - record[f"win_{x}%"]
        records.append(record)
    output_file = "../resources/blind_spy/blind_spy_full_consolidated.json"
    with open(output_file, "w") as f:
        json.dump(records, f, indent=2)
    print(f"Consolidated {len(records)} records into {output_file}")


if __name__ == '__main__':
    # uncomment the task you want to run
    # simulate_double_dr()
    consolidate_double_dr()

