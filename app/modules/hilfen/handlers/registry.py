# app\modules\hilfen\handlers\registry.py
"""
Central handler registry.

All handlers must be registered here so the dispatcher can execute them
in the correct order.

Handlers are executed in the following order:
1. Stateless handlers (no database access)
2. Stateful handlers (database session provided)
"""

from app.modules.hilfen.handlers.stateless.basic_handlers import (
    IgnoreBotMessagesHandler,
    SamCommandHandler,
)

from app.modules.hilfen.handlers.stateful.auth_handlers import (
    StartCommandHandler,
    EmailInputHandler,
)

from app.modules.hilfen.handlers.stateful.registration_handlers import (
    FirstNameRegistrationHandler,
    LastNameRegistrationHandler,
)

STATELESS_HANDLERS = [
    IgnoreBotMessagesHandler(),
    SamCommandHandler(),
]

STATEFUL_HANDLERS = [
    # Registration handlers first (they check for specific states)
    FirstNameRegistrationHandler(),
    LastNameRegistrationHandler(),
    # Then general commands (like /start)
    StartCommandHandler(),
    EmailInputHandler(),
]
