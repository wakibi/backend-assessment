import logging
from functools import reduce

from redis.client import Redis
from redis.exceptions import ConnectionError
from sqlalchemy import Engine
from sqlmodel import Session, select


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_db_status(db_engine: Engine) -> dict[str, str]:
    try:
        with Session(db_engine) as session:
            # Try to create session to check if DB is awake
            session.exec(select(1))
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
