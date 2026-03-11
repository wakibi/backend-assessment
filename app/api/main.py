from fastapi import APIRouter

from app.api.routes.events import views as events_views
from app.api.routes.health import views as health_views

api_router = APIRouter()
api_router.include_router(events_views.router)
api_router.include_router(health_views.router)
