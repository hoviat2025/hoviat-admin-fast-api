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
      - House news flow – city selection handlers
      - House news flow – description handlers
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

# Old house‑ad flow handlers (disabled)
# from app.modules.hilfen.handlers.stateful.house_add_flow_handlers import ...

from app.modules.hilfen.handlers.stateful.house_news_flow_handlers import (
    HouseCityCancelHandler,
    HouseCityAnotherCityHandler,
    HouseCityInputHandler,
    HouseCityCustomCancelHandler,
    HouseCityCustomInputHandler,
    HouseNewsDescriptionCancelHandler,
    HouseNewsDescriptionInputHandler,
)

from app.modules.hilfen.handlers.stateful.main_menu_handlers import (
    HouseButtonHandler,
    WorkAndNeedsButtonHandler,
    EuroButtonHandler,
    MyProfileButtonHandler,
    MyAdsButtonHandler,
    HelpButtonHandler,
)

STATELESS_HANDLERS = [
    IgnoreBotMessagesHandler(),
    SamCommandHandler(),
]

STATEFUL_HANDLERS = [
    # Registration flow
    CountryRegistrationHandler(),
    FirstNameRegistrationHandler(),
    LastNameRegistrationHandler(),
    PhoneRegistrationHandler(),
    InvalidPhoneInputHandler(),

    # General commands
    StartCommandHandler(),

    # Main‑menu buttons
    HouseButtonHandler(),
    WorkAndNeedsButtonHandler(),
    EuroButtonHandler(),
    MyProfileButtonHandler(),
    MyAdsButtonHandler(),
    HelpButtonHandler(),

    # House news – city selection
    HouseCityCancelHandler(),
    HouseCityAnotherCityHandler(),
    HouseCityInputHandler(),

    # Custom city flow
    HouseCityCustomCancelHandler(),
    HouseCityCustomInputHandler(),

    # House news – description input
    HouseNewsDescriptionCancelHandler(),
    HouseNewsDescriptionInputHandler(),
]

FALLBACK_HANDLERS = [
    UnhandledPrivateMessageHandler(),
]