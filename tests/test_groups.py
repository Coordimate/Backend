from conftest import auth_header, post, patch, delete, get
import crud_utils


def test_group_schedule_equal_to_schedule_of_admin_on_creation():
    admin_id, admin_token = crud_utils.create_user(0)
    time_slot = {"day": 0, "start": 8.0, "length": 2.0}
    post("/time_slots", time_slot, auth_header(admin_token))

    group_data = {"name": "name", "description": "description"}
    group = post("/groups", group_data, auth_header(admin_token))
    admin = get(f"/users/{admin_id}", auth_header(admin_token))

    assert group["schedule"] == admin["schedule"]

    delete(f"/groups/{group['id']}", auth_header(admin_token))
    crud_utils.delete_user(admin_id, admin_token)


def test_group_schedule_recomputed_when_new_user_joins():
    admin_id, admin_token = crud_utils.create_user(0)
    admin_time_slot_1 = {"day": 0, "start": 8.0, "length": 2.0}
    post("/time_slots", admin_time_slot_1, auth_header(admin_token))
    admin_time_slot_2 = {"day": 1, "start": 6.0, "length": 2.0}
    post("/time_slots", admin_time_slot_2, auth_header(admin_token))

    user_id, user_token = crud_utils.create_user(1)
    user_time_slot_1 = {"day": 1, "start": 7.0, "length": 2.0}
    post("/time_slots", user_time_slot_1, auth_header(user_token))
    user_time_slot_2 = {"day": 2, "start": 8.0, "length": 2.0}
    post("/time_slots", user_time_slot_2, auth_header(user_token))

    group_data = {"name": "name", "description": "description"}
    group = post("/groups", group_data, auth_header(admin_token))
    post(
        f"/groups/{group['id']}/join", headers=auth_header(user_token), status_code=200
    )

    group = get(f"/groups/{group['id']}", auth_header(admin_token))
    schedule = [(ts["day"], ts["start"], ts["length"]) for ts in group["schedule"]]
    ats1 = tuple(admin_time_slot_1.values())
    ats2 = tuple(admin_time_slot_2.values())
    uts1 = tuple(user_time_slot_1.values())
    uts2 = tuple(user_time_slot_2.values())

    assert ats1 in schedule
    assert ats2 not in schedule
    assert uts1 not in schedule
    assert uts2 in schedule
    assert (1, 6, 3) in schedule

    delete(f"/groups/{group['id']}", auth_header(admin_token))
    crud_utils.delete_user(user_id, user_token)
    crud_utils.delete_user(admin_id, admin_token)
