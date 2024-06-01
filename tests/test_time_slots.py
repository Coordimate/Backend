import pytest

from conftest import auth_header, post, patch, delete, get


async def create_time_slot(token, day, start, length):
    time_slot = {"day": day, "start": start, "length": length}
    resp = await post("/time_slots", time_slot, auth_header(token))
    yield resp
    await delete(f"/time_slots/{resp['id']}", auth_header(token))


@pytest.mark.anyio
async def test_crud_time_slot(regular_token):
    # Create
    time_slot = {"day": 3, "start": 8.0, "length": 2.0}
    post_response = await post("/time_slots", time_slot, auth_header(regular_token))
    time_slot_id = post_response["id"]

    time_slot_2 = {"day": 4, "start": 7.0, "length": 3.0}
    post_response = await post("/time_slots", time_slot_2, auth_header(regular_token))
    time_slot_id_2 = post_response["id"]

    # Update
    update_time_slot = {"day": 4}
    await patch(f"/time_slots/{time_slot_id}", update_time_slot, auth_header(regular_token))

    # Read
    body = await get("/time_slots", auth_header(regular_token))
    created_first = None
    created_second = None
    print(body)
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
    await delete(f"/time_slots/{time_slot_id}", auth_header(regular_token))
    await delete(f"/time_slots/{time_slot_id_2}", auth_header(regular_token))

