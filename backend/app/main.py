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
)
from app.core.config import settings

app = FastAPI(title="AI Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
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
