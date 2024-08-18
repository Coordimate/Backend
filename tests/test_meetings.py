import datetime

from conftest import auth_header, post, patch, delete, get
import crud_utils


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


def test_meeting_update_shows_up_in_user_and_groups():
    admin_id, admin_token = crud_utils.create_user(0)
    group = crud_utils.create_group(admin_token)

    meeting_time = datetime.datetime.now().isoformat()
    meeting_data = {
        "group_id": group["id"],
        "title": "test meeting",
        "start": meeting_time,
        "description": "test meeting",
    }
    meeting = post("/meetings", meeting_data, auth_header(admin_token))

    patch(f"/meetings/{meeting['id']}", {"is_finished": True}, auth_header(admin_token))
    user_meetings = get("/meetings", auth_header(admin_token))["meetings"]
    updated_meeting = user_meetings[0]
    for k in meeting_data:
        if k in ("is_finished", "group_id", "description"):
            continue
        assert k in updated_meeting
        assert updated_meeting[k] == meeting_data[k]

    group_data = {"name": "name", "description": "description"}
    group = post("/groups", group_data, auth_header(admin_token))

    crud_utils.delete_group(admin_token, group)
    crud_utils.delete_meeting(admin_token, meeting)
    crud_utils.delete_user(admin_id, admin_token)


def test_meeting_is_set_to_finished_once_passed():
    alice_id, alice_token = crud_utils.create_user(1)
    bob_id, bob_token = crud_utils.create_user(2)

    group_data = {"name": "name", "description": "description"}
    group = post("/groups", group_data, auth_header(alice_token))
    post(f"/groups/{group['id']}/join", {}, auth_header(bob_token), status_code=200)

    meeting_data = {
        "group_id": group["id"],
        "title": "test meeting",
        "start": (datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=2)).isoformat(),
        "description": "test passed meeting",
    }
    meeting = post("/meetings", meeting_data, auth_header(alice_token))

    thrown = None
    try:
        assert meeting["is_finished"] == False
        alice_meeting = get(f"/meetings/{meeting['id']}", auth_header(alice_token))
        bob_meeting = get(f"/meetings/{meeting['id']}", auth_header(bob_token))

        assert not alice_meeting["is_finished"]
        assert not bob_meeting["is_finished"]

        for p in bob_meeting['participants']:
            if p["user_id"] == alice_id:
                assert p["status"] == "accepted"
            else:
                assert p["status"] == "needs acceptance"

        get("/meetings", auth_header(alice_token))

        alice_meeting = get(f"/meetings/{meeting['id']}", auth_header(alice_token))
        bob_meeting = get(f"/meetings/{meeting['id']}", auth_header(bob_token))

        assert alice_meeting["is_finished"]
        assert bob_meeting["is_finished"]

        for p in bob_meeting['participants']:
            if p["user_id"] == alice_id:
                assert p["status"] == "accepted"
            else:
                assert p["status"] == "declined"
    except Exception as e:
        print(e)
        thrown = e

    delete(f"/meetings/{meeting['id']}", auth_header(alice_token))
    delete(f"/groups/{group['id']}", auth_header(alice_token))

    crud_utils.delete_user(alice_id, alice_token)
    crud_utils.delete_user(bob_id, bob_token)

    if thrown:
        raise thrown

