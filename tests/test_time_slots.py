import pytest

from conftest import auth_header


@pytest.mark.anyio
async def test_crud_time_slot(client, regular_token):
    # Create
    time_slot = {"day": 3, "start": 8.0, "length": 2.0}
    post_response = await client.post(
        "http://localhost:8000/time_slots/",
        json=time_slot,
        headers=auth_header(regular_token),
    )
    assert post_response.status_code == 201
    time_slot_id = post_response.json()["id"]

    time_slot_2 = {"day": 4, "start": 7.0, "length": 3.0}
    post_response = await client.post(
        "http://localhost:8000/time_slots/",
        json=time_slot_2,
        headers=auth_header(regular_token),
    )
    assert post_response.status_code == 201
    time_slot_id_2 = post_response.json()["id"]

    # Update
    update_time_slot = {"day": 4}
    patch_response = await client.patch(
        f"http://localhost:8000/time_slots/{time_slot_id}",
        json=update_time_slot,
        headers=auth_header(regular_token),
    )
    assert patch_response.status_code == 200

    # Read
    get_response = await client.get(
        "http://localhost:8000/time_slots/", headers=auth_header(regular_token)
    )
    assert get_response.status_code == 200

    body = get_response.json()
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
    delete_response = await client.delete(
        f"http://localhost:8000/time_slots/{time_slot_id}",
        headers=auth_header(regular_token),
    )
    assert delete_response.status_code == 204
    delete_response = await client.delete(
        f"http://localhost:8000/time_slots/{time_slot_id_2}",
        headers=auth_header(regular_token),
    )
    assert delete_response.status_code == 204
