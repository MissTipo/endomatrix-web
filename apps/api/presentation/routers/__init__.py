"""presentation.routers"""

from .baseline import router as baseline_router
from .home import router as home_router
from .insights import router as insights_router
from .logs import router as logs_router

__all__ = ["baseline_router", "home_router", "insights_router", "logs_router"]
