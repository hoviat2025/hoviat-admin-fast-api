# app\modules\hilfen\handlers\registry.py
"""
Central handler registry.

All handlers must be registered here so the dispatcher can execute them
in the correct order.

Handlers are executed in the following order:
1. Stateless handlers (no database access)
2. Stateful handlers (database session provided)
3. Fallback handlers (run only if no other handler matched)

Registration flow order:
1. Country input (waiting_for_country)
2. First name input (waiting_for_first_name)  
3. Last name input (waiting_for_last_name)
4. Phone contact (waiting_for_phone)
5. Invalid phone input handler (text when expecting contact)
6. Start command (initiates registration)
7. Unhandled private message fallback (LAST - catches everything else)
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

# Regular handlers - checked first
STATELESS_HANDLERS = [
    IgnoreBotMessagesHandler(),
    SamCommandHandler(),
]

STATEFUL_HANDLERS = [
    # Registration handlers in order of state progression
    CountryRegistrationHandler(),
    FirstNameRegistrationHandler(),
    LastNameRegistrationHandler(),
    PhoneRegistrationHandler(),
    InvalidPhoneInputHandler(),
    
    # General commands (like /start) - processed last
    StartCommandHandler(),
]

# Fallback handlers - checked ONLY if no regular handler matched
FALLBACK_HANDLERS = [
    UnhandledPrivateMessageHandler(),
]
