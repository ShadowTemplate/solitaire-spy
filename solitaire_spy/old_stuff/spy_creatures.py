import csv
import math

# SCORE_FILE_PATH = "/home/gianvito/personal/pauperformance-bot/dev/spy_creatures.csv"
SCORE_FILE_PATH = "/home/gianvito/personal/pauperformance-bot/dev/nerfed_carataker.csv"

MAX_COPIES_YELLOW_CREATURES = 18

def copies_in_deck(creature, tinder_wall, quirion_ranger, saruli_caretaker, portcullis_vine, elves_of_deep_shadow, wall_of_roots):
    if creature == "Tinder Wall":
        return tinder_wall
    elif creature == "Quirion Ranger":
        return quirion_ranger
    elif creature == "Saruli Caretaker":
        return saruli_caretaker
    elif creature == "Portcullis Vine":
        return portcullis_vine
    elif creature == "Elves of Deep Shadow":
        return elves_of_deep_shadow
    elif creature == "Wall of Roots":
        return wall_of_roots
    elif creature == "Gatekeeper Vine":
        return 0
    elif creature == "Overgrown Battlement":
        return 4
    elif creature == "Masked Vandal":
        return 3
    elif creature == "Mesmeric Fiend":
        return 3
    elif creature == "Troll of Khazad-dûm":
        return 1
    elif creature == "Sagu Wildling":
        return 1
    elif creature == "Generous Ent":
        return 1
    elif creature == "Avenging Hunter":
        return 0
    elif creature == "Scattershot Archer":
        return 0
    elif creature == "Fang Dragon":
        return 0
    elif creature == "Faerie Macabre":
        return 0
    elif creature == "Healer of the Glade":
        return 0
    elif creature == "Nylea's Disciple":
        return 0
    else:
        print(f"Error: missing {creature}...")
        exit(-1)


def main():
    score_map = {}
    creature_list = []
    with open(SCORE_FILE_PATH, encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        for i, row in enumerate(reader):
            if i == 0:
                continue
            if i == 1:
                creature_list = row[2:]
                # print(f"Analyzing {len(creature_list)} creatures...\n")
                continue
            scores = row[2:]
            assert len(scores) == len(creature_list)
            score_map[row[1]] = {
                creature_list[i]: scores[i] for i in range(len(scores))
            }
            if i >= len(creature_list) + 1:
                break

    best_deck_value = 0
    for tinder_wall in range(0, 5):
        for quirion_ranger in range(0, 5):
            for saruli_caretaker in range(0, 5):
                for portcullis_vine in range(0, 5):  # cap at 2?
                    for elves_of_deep_shadow in range(4, 5):
                        for wall_of_roots in range(0, 5):
                            if tinder_wall + quirion_ranger + saruli_caretaker + portcullis_vine + elves_of_deep_shadow + wall_of_roots > MAX_COPIES_YELLOW_CREATURES:
                                continue
                            deck_value = 0
                            for creature1 in creature_list:
                                for creature2 in creature_list:
                                    deck_value += (
                                            math.log(1 + copies_in_deck(creature1, tinder_wall, quirion_ranger, saruli_caretaker, portcullis_vine, elves_of_deep_shadow, wall_of_roots) *
                                            copies_in_deck(creature2, tinder_wall, quirion_ranger, saruli_caretaker, portcullis_vine, elves_of_deep_shadow, wall_of_roots)) *
                                            float(score_map[creature1][creature2])
                                    )
                            if deck_value > best_deck_value:
                                print(
                                    f"{tinder_wall}x Tinder Wall, "
                                    f"{quirion_ranger}x Quirion Ranger, "
                                    f"{saruli_caretaker}x Saruli Caretaker, "
                                    f"{portcullis_vine}x Portcullis Vine, "
                                    f"{elves_of_deep_shadow}x Elves of Deep Shadow, "
                                    f"{wall_of_roots}x Wall of Roots"
                                )
                                best_deck_value = deck_value


if __name__ == '__main__':
    main()
