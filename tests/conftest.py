import os
import pytest
from httpx import AsyncClient
from typing import AsyncGenerator
import json
from unittest.mock import MagicMock

# Set test environment vars before importing app
os.environ["ENVIRONMENT"] = "testing"
os.environ["SUPABASE_URL"] = "http://localhost:8000"
os.environ["SUPABASE_KEY"] = "dummy"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "dummy"
os.environ["JWT_SECRET"] = "super-secret-test-key-32-chars-long"

from main import app
from core.database import get_supabase
from core.limiter import init_redis
from fastapi_limiter import FastAPILimiter
import fakeredis.aioredis

# Mock Supabase
@pytest.fixture
def mock_supabase(mocker):
    mock = mocker.patch("core.database.supabase_client")
    mock_instance = MagicMock()
    
    # Simple chain mocking setup
    def make_chain(return_val):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.insert.return_value = chain
        chain.update.return_value = chain
        chain.delete.return_value = chain
        chain.eq.return_value = chain
        chain.neq.return_value = chain
        chain.limit.return_value = chain
        chain.order.return_value = chain
        chain.execute.return_value = MagicMock(data=return_val)
        return chain
    
    # Store dynamic tables
    tables = {}
    
    def table_func(table_name):
        if table_name not in tables:
            tables[table_name] = make_chain([])
        return tables[table_name]
        
    mock_instance.table.side_effect = table_func
    
    mocker.patch("core.database.get_supabase", return_value=mock_instance)
    return mock_instance

@pytest.fixture(autouse=True)
async def setup_redis_limiter():
    """Setup Fake Redis for rate limiter in tests"""
    redis_conn = fakeredis.aioredis.FakeRedis()
    await FastAPILimiter.init(redis_conn)
    yield
    await redis_conn.close()

@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
