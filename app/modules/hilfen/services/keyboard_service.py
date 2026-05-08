# app/modules/hilfen/services/keyboard_service.py
"""
Keyboard factory for the Hilfen bot.

All reusable keyboards are defined here as pure functions so handlers and
other services can obtain a keyboard without repeating its layout.
"""


def get_main_menu_keyboard() -> list[list[dict]]:
    """
    Return the main menu keyboard that is shown after registration is complete.

    Layout:
        [ house ]  [ work and needs ]  [ euro ]
        [ my profile ]  [ my ads ]  [ help ]
    """
    return [
        [
            {"text": " house "},
            {"text": " work and needs "},
            {"text": " euro "},
        ],
        [
            {"text": " my profile "},
            {"text": " my ads "},
            {"text": " help "},
        ],
    ]