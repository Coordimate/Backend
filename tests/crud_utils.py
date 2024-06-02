import datetime

from conftest import get, post, delete, auth_header


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
     

def create_group(token):
    group_data = {"name": "name", "description": "description"}
    group = post("/groups", group_data, auth_header(token))
    return group


def delete_group(token, group):
    delete(f"/groups/{group['id']}", auth_header(token))


def create_meeting(token, group):
    meeting_data = {
        "group_id": group["id"],
        "title": "test meeting",
        "start": datetime.datetime.now().isoformat(),
        "description": "test meeting",
    }
    meeting = post("/meetings", meeting_data, auth_header(token))
    return meeting


def delete_meeting(token, meeting):
    delete(f"/meetings/{meeting['id']}", auth_header(token))
