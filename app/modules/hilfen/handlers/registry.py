# app/modules/hilfen/handlers/registry.py
"""
Central handler registry.

Handlers are executed in the order listed below.
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
from app.modules.hilfen.handlers.stateful.house_news_flow_handlers import (
    HouseCityCancelHandler,
    HouseCityAnotherCityHandler,
    HouseCityInputHandler,
    HouseCityCustomCancelHandler,
    HouseCityCustomInputHandler,
    # Role step
    HouseNewsRoleCancelHandler,
    HouseNewsRoleRentHandler,
    HouseNewsRolePublishHandler,
    HouseNewsRoleInvalidHandler,
    # Description step
    HouseNewsDescriptionCancelHandler,
    HouseNewsDescriptionInputHandler,
    # Photos step
    HouseNewsPhotosCancelHandler,
    HouseNewsPhotosSkipHandler,
    HouseNewsPhotosMediaHandler,
    HouseNewsPhotosInvalidHandler,
    # Preview step
    HouseNewsPreviewConfirmHandler,
    HouseNewsPreviewDeclineHandler,
    HouseNewsPreviewFallbackHandler,
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
    # Registration
    CountryRegistrationHandler(),
    FirstNameRegistrationHandler(),
    LastNameRegistrationHandler(),
    PhoneRegistrationHandler(),
    InvalidPhoneInputHandler(),

    # General
    StartCommandHandler(),

    # Main menu
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

    # Custom city
    HouseCityCustomCancelHandler(),
    HouseCityCustomInputHandler(),

    # House news – role selection
    HouseNewsRoleCancelHandler(),
    HouseNewsRoleRentHandler(),
    HouseNewsRolePublishHandler(),
    HouseNewsRoleInvalidHandler(),

    # House news – description
    HouseNewsDescriptionCancelHandler(),
    HouseNewsDescriptionInputHandler(),

    # House news – photos
    HouseNewsPhotosCancelHandler(),
    HouseNewsPhotosSkipHandler(),
    HouseNewsPhotosMediaHandler(),
    HouseNewsPhotosInvalidHandler(),

    # House news – preview
    HouseNewsPreviewConfirmHandler(),
    HouseNewsPreviewDeclineHandler(),
    HouseNewsPreviewFallbackHandler(),
]

FALLBACK_HANDLERS = [
    UnhandledPrivateMessageHandler(),
]