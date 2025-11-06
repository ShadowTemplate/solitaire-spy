from solitaire_spy.cards.creatures import *
from solitaire_spy.cards.lands import *
from solitaire_spy.cards.mtg_cards import *
from solitaire_spy.cards.spells import *


def play_unique_action(env, possible_actions):
    # only one possible action, do it
    if len(possible_actions) == 1:
        return possible_actions[0]
    return None, None

def play_only_a_land(env, possible_actions):
    # if the only non-system action is to play a land, do it
    non_system_actions = [
        action for _, action in possible_actions
        if not action.startswith("system_")
    ]
    if len(non_system_actions) == 1 and "play" in non_system_actions[0]:
        return possible_actions[0]
    return None, None

def tap_basic_land_for_mana(env, possible_actions):
    # if a basic land can be tapped for mana, do it
    for card, action in possible_actions:
        if isinstance(card, Forest) and action == "tap_for_mana_G":
            return card, action
        if isinstance(card, Swamp) and action == "tap_for_mana_B":
            return card, action
    return None, None

def cast_land_grant_for_free(env, possible_actions):
    # if Land Grant in hand can be used to freely get only one type of land, do it
    free_land_grant = 0
    free_land_grant_card, free_land_grant_action = None, None
    for card, action in possible_actions:
        if isinstance(card, LandGrant) and "for_free" in action:
            free_land_grant += 1
            free_land_grant_card, free_land_grant_action = card, action
    if free_land_grant == 1:
        return free_land_grant_card, free_land_grant_action
    return None, None

def cast_lotus_petal(env, possible_actions):
    # if Lotus Petal in hand can be cast, do it
    lotus_petal_card, lotus_petal_action = None, None
    for card, action in possible_actions:
        if isinstance(card, LotusPetal) and "cast" in action:
            lotus_petal_card, lotus_petal_action = card, action
    if lotus_petal_action:
        return lotus_petal_card, lotus_petal_action
    return None, None

def mill_deck_with_spy(env, possible_actions):
    # if Spy in hand can be cast to 100% mill the deck and win, do it
    can_cast_spy = False
    spy_card, spy_action = None, None
    for card, action in possible_actions:
        if isinstance(card, BalustradeSpy):
            can_cast_spy = True
            spy_card, spy_action = card, action
    lands_in_play = len(env.lands)
    lands_in_hand = sum(isinstance(c, MTGLand) for c in env.hand)
    lands_in_graveyard = sum(isinstance(c, MTGLand) for c in env.graveyard)
    all_lands_ready = (lands_in_play + lands_in_hand + lands_in_graveyard +
                       env.known_lands_bottom == env.lands_in_deck)
    dread_return_in_deck = any(isinstance(c, DreadReturn) for c in env.library)
    giant_in_deck = any(isinstance(c, LotlethGiant) for c in env.library)
    creatures_on_the_battlefield = sum(isinstance(c, MTGCreatureSpell) for c in env.battlefield)
    if can_cast_spy and creatures_on_the_battlefield >= 2 and all_lands_ready and dread_return_in_deck and giant_in_deck:
        return spy_card, spy_action
    return None, None

def flashback_giant_for_lethal(env, possible_actions):
    # if Dread Return can be flashed-back for lethal, do it
    can_flashback_dread_return = False
    for card, action in possible_actions:
        if isinstance(card, DreadReturn) and "flashback" in action:
            can_flashback_dread_return = True
    giant_in_graveyard = any(isinstance(c, LotlethGiant) for c in env.graveyard)
    damage_giant_will_do = sum(
        isinstance(c, MTGCreatureSpell) for c in env.graveyard
    ) + 2  # -1 Giant itself + 3 creatures sacrificed
    if can_flashback_dread_return and giant_in_graveyard and damage_giant_will_do >= env.opponent_counter_life:
        for i, gy_card in enumerate(env.graveyard):
            if gy_card.name == "Lotleth Giant":
                # we don't care which creatures we'll sacrifice: pick the first 3
                return next(
                    p for p in possible_actions if f"flashback_with_target@{i}" in p[1])
    # no obvious play
    return None, None

def cast_saruli_before_tapping_battlement(env, possible_actions):
    # if Saruli is in hand and can be cast, and Battlement is on the battlefield with no
    # evocation weakness, then cast Saruli
    can_cast_saruli = False
    saruli_card, saruli_action = None, None
    can_tap_battlement = False
    for card, action in possible_actions:
        if isinstance(card, SaruliCaretaker) and "cast" in action:
            can_cast_saruli = True
            saruli_card, saruli_action = card, action
        if isinstance(card, OvergrownBattlement) and "tap" in action:
            can_tap_battlement = True
    if can_cast_saruli and can_tap_battlement:
        return saruli_card, saruli_action
    return None, None

def cast_spell_if_only_option(env, possible_actions):
    # if you can only cast spell or pass, cast the spell
    can_pass = False
    castable_card, castable_action = None, None
    for card, action in possible_actions:
        if "cast" in action:
            castable_card, castable_action = card, action
        if action == "system_pass":
            can_pass = True
    if len(possible_actions) == 2 and can_pass:
        return castable_card, castable_action
    return None, None

def tutor_land_if_only_option(env, possible_actions):
    # if you can only tutor for a land or pass, tutor for the land
    can_pass_or_start_new_turn = False
    tutorable_card, tutorable_action = None, None
    for card, action in possible_actions:
        if "cycling" in action or "roost_seek" in action:
            tutorable_card, tutorable_action = card, action
        if action == "system_pass" or action == "system_start_new_turn":
            can_pass_or_start_new_turn = True
    if len(possible_actions) == 2 and can_pass_or_start_new_turn:
        return tutorable_card, tutorable_action
    return None, None

def no_useless_mana_switch_strategy(env, possible_actions):
    # do not make a useless mana switch strategy before passing
    can_switch_mana_strategy = False
    can_pass = False
    can_start_new_turn = False
    target_action = None
    for card, action in possible_actions:
        if action == "system_switch_mana_strategy":
            can_switch_mana_strategy = True
        if action == "system_pass":
            can_pass = True
            target_action = action
        if action == "system_start_new_turn":
            can_start_new_turn = True
            target_action = action
    if len(possible_actions) == 2 and can_switch_mana_strategy and (can_pass or can_start_new_turn):
        return None, target_action
    return None, None
