import requests
import json

import pytest
import requests


BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="session")
def token():
    register_details = {
        "username": "user",
        "email": "user@mail.com",
        "password": "user",
    }
    login_details = {"email": "user@mail.com", "password": "user"}
    response = post("/login", login_details, status_code=0)
    if "detail" in response:
        post("/register", register_details)
        response = post("/login", login_details, status_code=200)
    access_token = response["access_token"]
    return access_token


def create_user(id):
    user_data = {
        "username": f"user{id}",
        "email": f"user{id}@mail.com",
        "password": f"password",
    }
    post("/register", user_data)
    resp = post("/login", user_data, status_code=200)
    access_token = resp["access_token"]
    resp = get("/me", auth_header(access_token))
    return resp["id"], access_token


def delete_user(id, token):
    delete(f"/users/{id}", auth_header(token))


def auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


def post(uri, body={}, headers={}, status_code=201):
    resp = requests.post(BASE_URL + uri, json=body, headers=headers)
    if status_code:
        try:
            assert resp.status_code == status_code
        except Exception as e:
            print("POST failed:", resp.status_code)
            try:
                print(json.dumps(resp.json(), indent=2))
            except:
                pass
            raise e
    return resp.json()


def patch(uri, body={}, headers={}, status_code=200):
    resp = requests.patch(BASE_URL + uri, json=body, headers=headers)
    if status_code:
        try:
            assert resp.status_code == status_code
        except Exception as e:
            print("PATCH failed:", resp.status_code, json.dumps(resp.json(), indent=2))
            raise e
    return resp.json()


def get(uri, headers={}, status_code=200):
    resp = requests.get(BASE_URL + uri, headers=headers)
    if status_code:
        try:
            assert resp.status_code == status_code
        except Exception as e:
            print("GET failed:", resp.status_code, json.dumps(resp.json(), indent=2))
            raise e
    return resp.json()


def delete(uri, headers={}, status_code=204):
    resp = requests.delete(BASE_URL + uri, headers=headers)
    if status_code:
        try:
            assert resp.status_code == status_code
        except Exception as e:
            print("DELETE failed:", resp.status_code, json.dumps(resp.json(), indent=2))
            raise e
