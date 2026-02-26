import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_hospital_missing_payment(async_client: AsyncClient):
    response = await async_client.post(
        "/api/hospitals/register",
        json={
            "name": "City Care",
            "email": "contact@citycare.com",
            "mobile": "9876543210"
        }
    )
    assert response.status_code == 400
    assert "Payment is required" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_hospitals_public(async_client: AsyncClient, mock_supabase):
    mock_supabase.table.return_value.select.return_value.order.return_value.execute.return_value.data = [
        {"id": 1, "name": "City Care", "status": "approved"}
    ]
    
    response = await async_client.get("/api/hospitals/")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "City Care"
