from fastapi import APIRouter

from app.api.routes.events import views as events_views

api_router = APIRouter()
api_router.include_router(events_views.router)
