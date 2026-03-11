import logging
from functools import reduce

from redis.client import Redis
from redis.exceptions import ConnectionError
from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine
from sqlmodel import select


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_db_status(db_engine: AsyncEngine) -> dict[str, str]:
    """Asynchronously verify the database connection is healthy.

    The function opens an ``AsyncSession`` against the provided engine and
    executes a minimal ``SELECT 1``.  It returns ``{'status': 'ok'}`` on
    success, otherwise ``{'status': 'error'}`` and logs the exception.
    """
    try:
        async with AsyncSession(db_engine) as session:
            await session.execute(select(1))
            return {'status': 'ok'}
    except Exception as e:
        logger.error(e)
    return {'status': 'error'}

def check_redis_status(redis_client: Redis) -> dict[str, str]:
    try:
        # Check Redis connectivity
        if redis_client.ping():
            return {'status': 'ok'}
    except ConnectionError as e:
        logger.error(e)
    return {'status': 'error'}


def get_nested_dict_value(data: dict, keys: list[str]):
    return reduce(lambda d, key: d.get(key) if isinstance(d, dict) else None, keys, data)

def get_common_keys(keys: list[str], dict_to_search: dict) -> set:
    return set(keys) & set(dict_to_search.keys())
