import pytest
from httpx import AsyncClient

from routes import app


@pytest.fixture(scope="module")
async def client():
    async with AsyncClient(app=app, base_url="http://localhost:8000") as client:
        yield client


@pytest.fixture(scope="module")
async def regular_token():
    account_details = {"email": "user@mail.com", "password": "user"}
    async with AsyncClient(app=app, base_url="http://0.0.0.0:8000") as ac:
        response = await ac.post("http://localhost:8000/login", json=account_details)
        assert response.status_code == 200
        if "detail" in response.json():
            response = await ac.post("http://localhost:8000/register", json=account_details)
            assert response.status_code == 200
            response = await ac.post("http://localhost:8000/login", json=account_details)
            assert response.status_code == 200
        access_token = response.json()["access_token"]
    yield access_token


def auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}

