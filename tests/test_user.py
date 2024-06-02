import pytest

from conftest import auth_header, post, get, patch, delete
import crud_utils


def test_username_updates_shows_in_groups_and_meetings(token):
    u_id, u_token = crud_utils.create_user(0)
    group = crud_utils.create_group(u_token)
    meeting = crud_utils.create_meeting(u_token, group)

    patch(f"/users/{u_id}", {"username": "new_name"}, auth_header(u_token))

    group = get(f"/groups/{group['id']}", auth_header(u_token))
    meeting = get(f"/meetings/{meeting['id']}", auth_header(u_token))

    assert "new_name" in [p["username"] for p in meeting["participants"]]
    assert "new_name" in [u["username"] for u in group["users"]]
    assert "new_name" == group["admin"]["username"]

    crud_utils.delete_meeting(token, meeting)
    crud_utils.delete_group(token, group)
    crud_utils.delete_user(u_id, u_token)


@pytest.mark.skip(reason="implement this logic later")
def test_user_deletion_cleans_up_owned_meetings_and_groups(token):
    group = crud_utils.create_group(token)
    meeting = crud_utils.create_meeting(token, group)

    user = get("/me", auth_header(token))
    delete(f"/users/{user['id']}", auth_header(token))

    group = get(f"/groups/{group['id']}", auth_header(token), 404)
    meeting = get(f"/meetings/{meeting['id']}", auth_header(token), 404)


@pytest.mark.skip(reason="implement this logic later")
def test_user_deletion_passes_admin_priviliges(token):
    group = crud_utils.create_group(token)

    u_id, u_token = crud_utils.create_user(0)
    post(f"/groups/{group['id']}/join", auth_header(u_token))

    user = get("/me", auth_header(token))
    delete(f"/users/{user['id']}", auth_header(token))

    group = get(f"/groups/{group['id']}", auth_header(token))

    assert u_id == group["admin"]["id"]

    crud_utils.delete_group(token, group)
    crud_utils.delete_user(u_id, u_token)


def test_user_not_in_meetings_or_groups_after_deletion(token):
    u_id, u_token = crud_utils.create_user(0)
    group = crud_utils.create_group(token)
    post(f"/groups/{group['id']}/join", {}, auth_header(u_token), 200)
    meeting = crud_utils.create_meeting(token, group)

    user = get(f"/users/{u_id}", auth_header(token))
    delete(f"/users/{u_id}", auth_header(token))

    group = get(f"/groups/{group['id']}", auth_header(token), 200)
    meeting = get(f"/meetings/{meeting['id']}", auth_header(token), 200)

    assert user["username"] not in [u["username"] for u in group["users"]]
    assert user["username"] not in [u["username"] for u in meeting["participants"]]

    crud_utils.delete_meeting(token, meeting)
    crud_utils.delete_group(token, group)
