import datetime

from conftest import auth_header, post, patch, delete, get


def test_meeting_is_not_finished_on_creation(token):
    group_data = {"name": "n", "description": "d"}
    group = post("/groups", group_data, auth_header(token))
    meeting_data = {
        "group_id": group["id"],
        "title": "test meeting",
        "start": datetime.datetime.now().isoformat(),
        "description": "test meeting",
    }
    meeting = post("/meetings", meeting_data, auth_header(token))

    assert meeting["is_finished"] == False

    delete(f"/meetings/{meeting['id']}", auth_header(token))
    delete(f"/groups/{group['id']}", auth_header(token))


def test_marking_meeting_as_finished(token):
    group_data = {"name": "n", "description": "d"}
    group = post("/groups", group_data, auth_header(token))
    meeting_data = {
        "group_id": group["id"],
        "title": "test meeting",
        "start": datetime.datetime.now().isoformat(),
        "description": "test meeting",
    }
    meeting = post("/meetings", meeting_data, auth_header(token))

    assert meeting["is_finished"] == False
    patch(f"/meetings/{meeting['id']}", {"is_finished": True}, auth_header(token))
    updated_meeting = get(f"/meetings/{meeting['id']}", auth_header(token))
    assert updated_meeting["is_finished"] == True

    delete(f"/meetings/{meeting['id']}", auth_header(token))
    delete(f"/groups/{group['id']}", auth_header(token))
