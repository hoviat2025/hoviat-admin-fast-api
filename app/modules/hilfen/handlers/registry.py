"""
Central handler registry.

All handlers must be registered here so the dispatcher can execute them
in the correct order.
"""

from app.modules.hilfen.handlers.stateless.basic_handlers import (
    IgnoreBotMessagesHandler,
    StartCommandHandler,
    SamCommandHandler,
)

from app.modules.hilfen.handlers.stateful.auth_handlers import (
    EmailInputHandler,
)

STATELESS_HANDLERS = [
    IgnoreBotMessagesHandler(),
    StartCommandHandler(),
    SamCommandHandler(),
]

STATEFUL_HANDLERS = [
    EmailInputHandler(),
]
