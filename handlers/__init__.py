from .command_handlers import router as command_router
from .plugin_handlers import router as plugin_router
from .approval_handlers import router as approval_router
from .demo_handlers import router as demo_router
from .backup_handlers import router as backup_router, setup_backup_scheduler
from .inline_handlers import router as inline_router

__all__ = [
    "command_router",
    "plugin_router",
    "approval_router",
    "demo_router",
    "backup_router",
    "inline_router",
    "setup_backup_scheduler",
]
