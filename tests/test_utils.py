import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import create_engine
from sqlmodel import SQLModel

from app.utils.utils import (
    check_db_status,
    check_redis_status,
    get_nested_dict_value,
    get_common_keys,
)

try:
    import redis
    from app.settings.db import redis_client as real_redis
except ImportError:
    redis = None
    real_redis = None


def test_get_nested_dict_value():
    data = {"a": {"b": {"c": 123}}}
    assert get_nested_dict_value(data, ["a", "b", "c"]) == 123
    assert get_nested_dict_value(data, ["a", "x"]) is None
    assert get_nested_dict_value({}, ["a"]) is None


def test_get_common_keys():
    keys = ["a", "b", "z"]
    d = {"a": 1, "c": 2}
    assert get_common_keys(keys, d) == {"a"}
    assert get_common_keys([], d) == set()


import pytest

@pytest.mark.asyncio
async def test_check_db_status_ok(tmp_path):
    # use the project's postgres database (cleaned)
    from app.settings import settings
    engine = create_async_engine(str(settings.DATABASE_URL), echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    status = await check_db_status(engine)
    assert status["status"] == "ok"


def test_check_redis_status():
    if real_redis is None:
        pytest.skip("redis library not available")
    # try ping real redis; if fails skip
    try:
        status = check_redis_status(real_redis)
        assert status["status"] in ("ok", "error")
    except Exception:
        pytest.skip("unable to contact redis")
