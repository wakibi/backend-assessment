from app.models import RedisDBHealthPublic
from app.utils.utils import check_db_status, check_redis_status
from app.settings.db import engine, redis_client


class HealthService:
    @staticmethod
    async def check_services_health() -> RedisDBHealthPublic:
        db_status = await check_db_status(engine)
        redis_status = check_redis_status(redis_client)
        return RedisDBHealthPublic(redis=redis_status, db=db_status)
