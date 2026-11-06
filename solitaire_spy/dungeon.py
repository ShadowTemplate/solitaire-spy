import logging

from solitaire_spy.cards.creatures import SkeletonToken, WallOfRoots
from solitaire_spy.cards.mtg_cards import MTGCreatureSpell, MTGLand
from solitaire_spy.cards.spells import TreasureToken
from solitaire_spy.log import get_logger

log = get_logger(__name__, stdout_level=logging.WARNING)

# Undercity (CLB) is the only dungeon with a dungeon type (CR 205.3p). It can only be
# entered by "venturing into Undercity" (CR 701.49d), which is exactly what the
# initiative does, so it is the only dungeon this deck can ever be in.
UNDERCITY_ENTRANCE = "Secret Entrance"
UNDERCITY_THRONE = "Throne of the Dead Three"

# Room graph: each room maps to the rooms its arrows point to (CR 309.4/309.5a).
# Every path from the entrance to the throne is exactly 4 ventures long, and there are
# 6 distinct paths.
UNDERCITY_ROOMS = {
    UNDERCITY_ENTRANCE: ["Forge", "Lost Well"],
    "Forge": ["Trap!", "Arena"],
    "Lost Well": ["Arena", "Stash"],
    "Trap!": ["Archives"],
    "Arena": ["Archives", "Catacombs"],
    "Stash": ["Catacombs"],
    "Archives": [UNDERCITY_THRONE],
    "Catacombs": [UNDERCITY_THRONE],
    UNDERCITY_THRONE: [],
}

THRONE_REVEALED_CARDS = 10
THRONE_COUNTERS = 3
TRAP_LIFE_LOSS = 5
LOST_WELL_SCRY = 2
FORGE_COUNTERS = 2


def get_next_rooms(current_room):
    # CR 701.49a: no dungeon in the command zone -> start Undercity at its topmost room
    if current_room is None:
        return [UNDERCITY_ENTRANCE]
    next_rooms = UNDERCITY_ROOMS[current_room]
    # CR 701.49c: venturing from the bottommost room completes the dungeon and starts a
    # new Undercity. In practice we never get here, because the dungeon is removed as a
    # state-based action as soon as the throne ability resolves (CR 309.6).
    return next_rooms if next_rooms else [UNDERCITY_ENTRANCE]


def get_room_choices(env, room):
    # Sub-choices a room ability offers, encoded as action-string parameters.
    # An empty string means the ability takes no choice at all.
    if room == UNDERCITY_ENTRANCE:
        basics = sorted({
            c.name for c in env.library if isinstance(c, MTGLand) and c.is_basic
        })
        return basics if basics else [""]
    if room == UNDERCITY_THRONE:
        creatures = sorted({
            c.name for c in env.library[:THRONE_REVEALED_CARDS]
            if isinstance(c, MTGCreatureSpell)
        })
        return creatures if creatures else [""]
    return [""]


def _scry(env, num_cards):
    # This deck wants lands *out* of the library: Balustrade Spy only stops milling when
    # it hits one. So bottom every land we see and keep everything else on top, in order.
    top = [env.library.pop(0) for _ in range(min(num_cards, len(env.library)))]
    kept_on_top = [c for c in top if not isinstance(c, MTGLand)]
    put_on_bottom = [c for c in top if isinstance(c, MTGLand)]
    for card in reversed(kept_on_top):
        log.info(f"Keeping on top {card}")
        env.library.insert(0, card)
    for card in put_on_bottom:
        log.info(f"Putting on the bottom {card}")
        env.library.append(card)
        env.known_lands_bottom += 1


def _secret_entrance(env, choice):
    # "Search your library for a basic land card, reveal it, put it into your hand,
    # then shuffle."
    if choice:
        log.info(f"Searching for {choice}")
        env.engine.search_library_for(choice)
    # The shuffle happens whether or not we found something, and it resets
    # known_lands_bottom: entering this room throws away any Elven Farsight setup.
    env.engine.shuffle_library()


def _forge(env, choice):
    # "Put two +1/+1 counters on target creature."
    # The counters are dead weight on almost every creature here: we never attack, and
    # the kill comes from Lotleth Giant's trigger, which counts bodies in the graveyard
    # rather than power. The exception is Wall of Roots, which pays for its mana ability
    # with -0/-1 counters and dies once its toughness reaches 0, so +2 toughness is
    # worth exactly 2 extra mana over the game. Always prefer it as the target.
    walls_of_roots = [c for c in env.battlefield if isinstance(c, WallOfRoots)]
    creatures = [c for c in env.battlefield if isinstance(c, MTGCreatureSpell)]
    if walls_of_roots:
        target = walls_of_roots[0]
    elif creatures:
        # no creature other than Wall of Roots does anything with the counters, so there
        # is nothing to branch on: just pick one
        target = creatures[0]
    else:
        log.info("No creature to target: Forge does nothing")
        return
    log.info(f"Putting {FORGE_COUNTERS} +1/+1 counters on {target}")
    target.plus_counters += FORGE_COUNTERS


def _lost_well(env, choice):
    # "Scry 2."
    _scry(env, LOST_WELL_SCRY)


def _trap(env, choice):
    # "Target player loses 5 life."
    log.info(f"Opponent loses {TRAP_LIFE_LOSS} life")
    env.opponent_counter_life -= TRAP_LIFE_LOSS


def _arena(env, choice):
    # "Goad target creature." No-op: the opponent never has creatures here.
    pass


def _stash(env, choice):
    # "Create a Treasure token."
    log.debug("Creating Treasure token")
    env.battlefield.append(TreasureToken())


def _archives(env, choice):
    # "Draw a card."
    env.engine.draw_cards(1)


def _catacombs(env, choice):
    # "Create a 4/1 black Skeleton creature token with menace."
    log.debug("Creating Skeleton creature token 4/1")
    env.battlefield.append(SkeletonToken())


def _throne_of_the_dead_three(env, choice):
    # "Reveal the top ten cards of your library. Put a creature card from among them
    # onto the battlefield with three +1/+1 counters on it. It gains hexproof until your
    # next turn. Then shuffle."
    # Hexproof is irrelevant here. Putting the creature into play is not, since it
    # triggers its enter-the-battlefield ability (a free Balustrade Spy, for instance),
    # and neither are the counters when the creature is a Wall of Roots.
    if choice:
        for i, card in enumerate(env.library[:THRONE_REVEALED_CARDS]):
            if card.name == choice:
                log.info(f"Putting {card} onto the battlefield")
                env.library.pop(i)
                env.battlefield.append(card)
                card.plus_counters += THRONE_COUNTERS
                card.enters_the_battlefield(env)
                break
    env.engine.shuffle_library()


ROOM_ABILITIES = {
    UNDERCITY_ENTRANCE: _secret_entrance,
    "Forge": _forge,
    "Lost Well": _lost_well,
    "Trap!": _trap,
    "Arena": _arena,
    "Stash": _stash,
    "Archives": _archives,
    "Catacombs": _catacombs,
    UNDERCITY_THRONE: _throne_of_the_dead_three,
}


def enter_room(env, room, choice):
    # CR 309.4c: every room ability reads "When you move your venture marker into this
    # room, [effect]". Move the marker first, then resolve the effect.
    log.info(f"Venturing into {room}")
    env.dungeon_room = room
    ROOM_ABILITIES[room](env, choice)
    if room == UNDERCITY_THRONE:
        # CR 309.6/309.7: once the throne ability has left the stack, the marker is on
        # the bottommost room, so the dungeon is removed from the game as a state-based
        # action and we complete it. The next venture starts a brand new Undercity.
        log.info("Undercity completed")
        env.dungeon_room = None
        env.dungeons_completed += 1
