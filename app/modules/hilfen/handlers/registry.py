# app/modules/hilfen/handlers/registry.py
"""
Central handler registry.

All handlers must be registered here so the dispatcher can execute them
in the correct order.

Execution order:
  1. Stateless handlers (no database access)
  2. Stateful handlers (database session provided)
      - Registration flow handlers
      - Start command handler
      - Main‑menu button handlers
  3. Fallback handlers (run only if no other handler matched)
"""

from app.modules.hilfen.handlers.stateless.basic_handlers import (
    IgnoreBotMessagesHandler,
    SamCommandHandler,
)

from app.modules.hilfen.handlers.stateless.fallback_handlers import (
    UnhandledPrivateMessageHandler,
)

from app.modules.hilfen.handlers.stateful.auth_handlers import (
    StartCommandHandler,
)

from app.modules.hilfen.handlers.stateful.registration_handlers import (
    CountryRegistrationHandler,
    FirstNameRegistrationHandler,
    LastNameRegistrationHandler,
    PhoneRegistrationHandler,
    InvalidPhoneInputHandler,
)

from app.modules.hilfen.handlers.stateful.main_menu_handlers import (
    HouseButtonHandler,
    WorkAndNeedsButtonHandler,
    EuroButtonHandler,
    MyProfileButtonHandler,
    MyAdsButtonHandler,
    HelpButtonHandler,
)

# Regular handlers – checked first
STATELESS_HANDLERS = [
    IgnoreBotMessagesHandler(),
    SamCommandHandler(),
]

STATEFUL_HANDLERS = [
    # Registration flow (must be first to catch ongoing states)
    CountryRegistrationHandler(),
    FirstNameRegistrationHandler(),
    LastNameRegistrationHandler(),
    PhoneRegistrationHandler(),
    InvalidPhoneInputHandler(),

    # General commands
    StartCommandHandler(),

    # Main‑menu buttons (only respond when user is not in registration)
    HouseButtonHandler(),
    WorkAndNeedsButtonHandler(),
    EuroButtonHandler(),
    MyProfileButtonHandler(),
    MyAdsButtonHandler(),
    HelpButtonHandler(),
]

# Fallback handlers – checked ONLY if no regular handler matched
FALLBACK_HANDLERS = [
    UnhandledPrivateMessageHandler(),
]