from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    analytics,
    chat,
    conversations,
    health,
    knowledge,
    settings as settings_routes,
    widget,
)
from app.core.auth import EdgeSecretMiddleware, require_admin
from app.core.config import settings

app = FastAPI(title="Plug & Play")

# Allow the admin app plus any customer domains that embed the widget. When the
# allow-list contains "*", reflect all origins (the site key authorizes the
# tenant); credentials are disabled in that case since "*" forbids them.
_origins = settings.allowed_origins
_allow_any = "*" in _origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allow_any else _origins,
    allow_credentials=not _allow_any,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Added after CORS so it is the OUTER middleware and rejects non-edge traffic
# before anything else runs (it exempts OPTIONS preflight and /health).
app.add_middleware(EdgeSecretMiddleware)

# Public routes: widget bootstrap is origin-bound; chat uses signed sessions.
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(widget.router)

# Admin routes: require a valid Supabase JWT (no-op when auth is disabled in
# local dev). See app.core.auth.require_admin.
_admin = [Depends(require_admin)]
app.include_router(knowledge.router, dependencies=_admin)
app.include_router(settings_routes.router, dependencies=_admin)
app.include_router(conversations.router, dependencies=_admin)
app.include_router(analytics.router, dependencies=_admin)
