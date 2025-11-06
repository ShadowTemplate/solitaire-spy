import random
from collections import Counter

SAMPLES = 100000

# F: Forest
# S: Swamp
# M: Haunted Mire
# G: Land Grant
# P: Lotus Petal
# W: Sagu Wildling
# E: Generous Ent
# T: Troll of Khazad-dûm
# D: Elves of Deep Shadow
# V: Gatekeeper Vine

# LL: Lands (F, S, G)
# FM: Free_Mana (P)
# 1T: MV1_Tutor (E, T, W)
# 1D: MV1_Dork (D)
# 2T: MV2_Tutor (V)


def is_keep(deck, hand):
    drawn_lands = list((Counter(hand) & Counter(deck.lands)).elements())
    drawn_free_mana = list((Counter(hand) & Counter(deck.free_mana)).elements())
    drawn_mv1_tutor = list((Counter(hand) & Counter(deck.mv1_tutor)).elements())
    drawn_mv1_dork = list((Counter(hand) & Counter(deck.mv1_dork)).elements())
    drawn_mv2_tutor = list((Counter(hand) & Counter(deck.mv2_tutor)).elements())

    if len(drawn_lands) >= 2:
        return True, "2xLL"
    if len(drawn_lands) == 1 and len(drawn_mv1_tutor) >= 1:
        # we need to exclude the case Swamp + Sagu
        if "S" in hand and len(drawn_mv1_tutor) == 1 and "W" in hand:
            pass  # not a keep
        else:
            return True, "1xLL + 1x1T"
    if len(drawn_lands) == 1 and len(drawn_free_mana) >= 1 and len(drawn_mv2_tutor) >= 1:
        return True, "1xLL + 1xFM + 1x2T"
    if len(drawn_lands) == 1 and len(drawn_mv1_dork) >= 1 and len(drawn_mv2_tutor) >= 1:
        return True, "1xLL + 1x1D + 1x2T"
    if len(drawn_lands) == 0 and len(drawn_free_mana) >= 1 and len(drawn_mv1_tutor) >= 2:
        return True, "0xLL + 1xFM + 2x1T"
    if len(drawn_lands) == 0 and len(drawn_free_mana) >= 1 and len(drawn_mv1_dork) >= 1 and len(drawn_mv1_tutor) >= 1 and len(drawn_mv2_tutor) >= 1:
        return True, "0xLL + 1xFM + 1x1D + 1x1T + 1x2T"
    if len(drawn_lands) == 0 and len(drawn_free_mana) >= 2 and len(drawn_mv1_tutor) >= 1 and len(drawn_mv2_tutor) >= 1:
        return True, "0xLL + 2xFM + 1x1T + 1x2T"
    # elif len(drawn_lands) == 0 and len(drawn_free_mana) >= 2 and len(drawn_mv1_dork) >= 1 and len(drawn_mv2_tutor) >= 2:
    #     return True, "0 Lands + 2 Free_Mana + 1 MV1_Dork + 2 MV2_Tutor"
    # elif len(drawn_lands) == 0 and len(drawn_free_mana) >= 3 and len(drawn_mv2_tutor) >= 2:
    #     return True, "0 Lands + 3 Free_Mana + 2 MV2_Tutor"

    return False, "Autoloss"


def sample_hand(deck, initial_hand):
    if initial_hand < 3:
        return initial_hand, "Autoloss"
    hand = [deck.deck[i] for i in random.sample(range(0, len(deck.deck)), 7)]
    keep, keep_type = is_keep(deck, hand)
    if keep:
        return initial_hand, keep_type
    return sample_hand(deck, initial_hand - 1)


def collect_stats(deck):
    keep_types = {
        "2xLL": 0,
        "1xLL + 1x1T": 0,
        "1xLL + 1xFM + 1x2T": 0,
        "1xLL + 1x1D + 1x2T": 0,
        "0xLL + 1xFM + 2x1T": 0,
        "0xLL + 1xFM + 1x1D + 1x1T + 1x2T": 0,
        "0xLL + 2xFM + 1x1T + 1x2T": 0,
        # "0 Lands + 2 Free_Mana + 1 MV1_Dork + 2 MV2_Tutor": 0,
        # "0 Lands + 3 Free_Mana + 2 MV2_Tutor": 0,
        "Autoloss": 0,
    }
    results = {i: 0 for i in range(2, 8)}
    print(f"Deck:\n{deck}")

    for _ in range(SAMPLES):
        keep_at, keep_type = sample_hand(deck, 7)
        results[keep_at] += 1
        keep_types[keep_type] += 1

    print("\nKeeps:")
    for k in sorted(results.keys(), reverse=True):
        if k == 2:
            print(f"Autoloss: {results[k] / SAMPLES:.2%}")
        else:
            print(f"@{k}: {results[k]/SAMPLES:.2%}")
    print("---")
    h_plus = {}
    for h in range(4, 7):
        h_plus[h] = sum(results[i] for i in range(h, 8))
        print(f"@{h}+: {h_plus[h]/SAMPLES:.2%}")
    print("---")
    five_plus_over_cards = h_plus[5] / (len(deck.deck) - len(deck.rest))
    print(f"@5+/cards: {five_plus_over_cards}")
    four_plus_over_cards = h_plus[4] / (len(deck.deck) - len(deck.rest))
    print(f"@4+/cards: {four_plus_over_cards}")

    # print("\nType:")
    # for k, v in keep_types.items():
    #     if len(deck.free_mana) < 1 and "Free" in k:
    #         continue
    #     if len(deck.mv1_dork) < 1 and "Dork" in k:
    #         continue
    #     print(f"{k}: {v} ({v/SAMPLES:.2%})")

    print()
    return keep_types, five_plus_over_cards, four_plus_over_cards


class SpyDeck:
    def __init__(self, lands, free_mana, mv1_tutor, mv1_dork, mv2_tutor):
        self.lands = lands
        self.free_mana = free_mana
        self.mv1_tutor = mv1_tutor
        self.mv1_dork = mv1_dork
        self.mv2_tutor = mv2_tutor
        self.rest = (60 - len(lands) - len(free_mana) - len(mv1_tutor) - len(mv1_dork)
                     - len(mv2_tutor)) * ["Other"]
        self.deck = lands + free_mana + mv1_tutor + mv1_dork + mv2_tutor + self.rest

    def __str__(self):
        return (f"{len(self.lands)}xLL: {' '.join(f'{v}{k}' for k, v in Counter(self.lands).items())} | " +
                f"{len(self.free_mana)}xFM: {' '.join(f'{v}{k}' for k, v in Counter(self.free_mana).items())} | " +
                f"{len(self.mv1_tutor)}x1T: {' '.join(f'{v}{k}' for k, v in Counter(self.mv1_tutor).items())} | " +
                f"{len(self.mv1_dork)}x1D: {' '.join(f'{v}{k}' for k, v in Counter(self.mv1_dork).items())} | " +
                f"{len(self.mv2_tutor)}x2T: {' '.join(f'{v}{k}' for k, v in Counter(self.mv2_tutor).items())}")

        return (f"{len(self.lands)} Lands: {list(Counter(self.lands).items())}\n" +
                f"{len(self.free_mana)} Free_Mana: {list(Counter(self.free_mana).items())}\n" +
                f"{len(self.mv1_tutor)} MV1_Tutor: {list(Counter(self.mv1_tutor).items())}\n" +
                f"{len(self.mv1_dork)} MV1_Dork: {list(Counter(self.mv1_dork).items())}\n" +
                f"{len(self.mv2_tutor)} MV2_Tutor: {list(Counter(self.mv2_tutor).items())}")


def main():
    target_metric1, target_metric2 = 0, 0
    best_deck1, best_deck2 = None, None
    for forest_number in range(5, 6):
        for swamp_number in range(0, 1):
            for petal_number in range(0, 1):
                for troll_number in range(0, 1):
                    for elf_number in range(4, 5):
                        for vine_number in range(0, 1):
                            lands = forest_number * ["F"] + swamp_number * ["S"] + 4 * ["G"]
                            free_mana = petal_number * ["P"]
                            mv1_tutor = 4 * ["W"] + 4 * ["E"] + troll_number * ["T"]
                            mv1_dork = elf_number * ["D"]
                            mv2_tutor = vine_number * ["V"]
                            deck = SpyDeck(lands, free_mana, mv1_tutor, mv1_dork, mv2_tutor)
                            keep_types, five_plus_over_cards, four_plus_over_cards = collect_stats(deck)
                            if five_plus_over_cards > target_metric1:
                                best_deck1 = deck
                                target_metric1 = five_plus_over_cards
                            if four_plus_over_cards > target_metric2:
                                best_deck2 = deck
                                target_metric2 = four_plus_over_cards

    print(25 * "-")
    print(f"Best @5: {target_metric1}\n{best_deck1}\n")
    print(f"Best @4: {target_metric2}\n{best_deck2}\n\n")


if __name__ == '__main__':
    main()
