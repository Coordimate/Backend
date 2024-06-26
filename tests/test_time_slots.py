from conftest import auth_header, post, patch, delete, get


def test_crud_time_slot(token):
    # Create
    time_slot = {"day": 3, "start": 8.0, "length": 2.0}
    post_response = post("/time_slots", time_slot, auth_header(token))
    time_slot_id = post_response["id"]

    time_slot_2 = {"day": 4, "start": 7.0, "length": 3.0}
    post_response = post("/time_slots", time_slot_2, auth_header(token))
    time_slot_id_2 = post_response["id"]

    # Update
    update_time_slot = {"day": 4}
    patch(f"/time_slots/{time_slot_id}", update_time_slot, auth_header(token))

    # Read
    body = get("/time_slots", auth_header(token))
    created_first = None
    created_second = None
    for ts in body["time_slots"]:
        if (
            ts["day"] == update_time_slot["day"]
            and ts["start"] == time_slot["start"]
            and ts["length"] == time_slot["length"]
        ):
            created_first = ts
        elif (
            ts["day"] == time_slot_2["day"]
            and ts["start"] == time_slot_2["start"]
            and ts["length"] == time_slot_2["length"]
        ):
            created_second = ts
    assert created_first is not None
    assert created_second is not None

    # Delete
    delete(f"/time_slots/{time_slot_id}", auth_header(token))
    delete(f"/time_slots/{time_slot_id_2}", auth_header(token))
