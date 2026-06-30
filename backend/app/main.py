from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    analytics,
    chat,
    conversations,
    health,
    knowledge,
    settings as settings_routes,
    speech,
    voice,
    widget,
)
from app.core.config import settings

app = FastAPI(title="AI Assistant")

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

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(knowledge.router)
app.include_router(settings_routes.router)
app.include_router(conversations.router)
app.include_router(analytics.router)
app.include_router(speech.router)
app.include_router(voice.router)
app.include_router(widget.router)
