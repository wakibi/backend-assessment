from fastapi import APIRouter

from app.models import RedisDBHealthPublic
from app.api.routes.health.service import HealthService

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=RedisDBHealthPublic)
async def check_services_health() -> RedisDBHealthPublic:
    print("Checking services health...")
    return await HealthService.check_services_health()
