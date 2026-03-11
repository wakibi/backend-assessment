from fastapi import FastAPI

from app.api.main import api_router
from app.settings import settings

app = FastAPI(
    title="Market Events Service",
    version="0.1.0",
)


app.include_router(api_router, prefix=settings.API_V1_STR)
