from collections import defaultdict
import json

import pytest
from httpx import AsyncClient

from routes import app


BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
async def client():
    async with AsyncClient(app=app, base_url=BASE_URL) as client:
        yield client


@pytest.fixture(scope="module")
async def regular_token():
    register_details = {
        "username": "user",
        "email": "user@mail.com",
        "password": "user"
    }
    login_details = {
        "email": "user@mail.com",
        "password": "user"
    }
    response = await post("/login", login_details, status_code=0)
    if "detail" in response:
        await post("/register", register_details)
        response = await post("/login", login_details)
    access_token = response["access_token"]
    yield access_token


def auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


async def post(uri, body={}, headers={}, status_code=201):
    async with AsyncClient(app=app, base_url=BASE_URL) as ac:
        resp = await ac.post(BASE_URL + uri, json=body, headers=headers)
    if status_code:
        try:
            assert resp.status_code == status_code
        except Exception as e:
            print("POST failed:", resp.status_code, json.dumps(resp.json(), indent=2))
            raise e
    return resp.json()


async def patch(uri, body={}, headers={}, status_code=200):
    async with AsyncClient(app=app, base_url=BASE_URL) as ac:
        resp = await ac.patch(BASE_URL + uri, json=body, headers=headers)
    if status_code:
        try:
            assert resp.status_code == status_code
        except Exception as e:
            print("PATCH failed:", resp.status_code, json.dumps(resp.json(), indent=2))
            raise e
    return resp.json()


async def get(uri, headers={}, status_code=200):
    async with AsyncClient(app=app, base_url=BASE_URL) as ac:
        resp = await ac.get(BASE_URL + uri, headers=headers)
    if status_code:
        try:
            assert resp.status_code == status_code
        except Exception as e:
            print("GET failed:", resp.status_code, json.dumps(resp.json(), indent=2))
            raise e
    return resp.json()


async def delete(uri, headers={}, status_code=204):
    async with AsyncClient(app=app, base_url=BASE_URL) as ac:
        resp = await ac.delete(BASE_URL + uri, headers=headers)
    if status_code:
        try:
            assert resp.status_code == status_code
        except Exception as e:
            print("DELETE failed:", resp.status_code, json.dumps(resp.json(), indent=2))
            raise e

