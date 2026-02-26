import pytest
from httpx import AsyncClient
from core.security import create_access_token

@pytest.mark.asyncio
async def test_register_user_success(async_client: AsyncClient, mock_supabase):
    # Setup mock
    table_mock = mock_supabase.table("users")
    # Simulate no existing user
    table_mock.execute.return_value.data = []
    
    # Then simulate insert success
    def side_effect(*args, **kwargs):
        if args[0] == "users" and hasattr(mock_supabase.table.call_args, 'insert'):
            m = mock_supabase._mock_children['table'].return_value
            m.execute.return_value.data = [{"id": 1, "email": "test@test.com", "role": "patient", "is_active": True}]
            return m
        return table_mock

    mock_supabase.table.side_effect = None
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": 1, "email": "test@test.com", "role": "patient", "name": "Test User"}
    ]

    response = await async_client.post(
        "/api/users/register",
        json={
            "name": "Test User",
            "email": "test@test.com",
            "mobile": "1234567890",
            "password": "password123",
            "role": "patient"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "test@test.com"

@pytest.mark.asyncio
async def test_login_user_success(async_client: AsyncClient, mock_supabase):
    from core.security import get_password_hash
    # Mock user exists
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {
            "id": 1,
            "email": "test@test.com",
            "password_hash": get_password_hash("password123"),
            "is_active": True,
            "role": "patient",
            "token_version": 1
        }
    ]
    
    response = await async_client.post(
        "/api/users/login",
        json={"email": "test@test.com", "password": "password123"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["id"] == 1

@pytest.mark.asyncio
async def test_protected_route(async_client: AsyncClient, mock_supabase):
    # Mock JWT and current user
    token = create_access_token({"sub": "1", "role": "patient", "token_version": 1})
    
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": 1, "email": "test@test.com", "is_active": True, "role": "patient", "token_version": 1}
    ]
    
    # Also mock blacklist check
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = [
        [], # Blacklist check
        [{"id": 1, "email": "test@test.com", "is_active": True, "role": "patient", "token_version": 1}] # User dict
    ]

    response = await async_client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    assert response.json()["id"] == 1
