import datetime
from unittest import mock

from bson import ObjectId
from fastapi import HTTPException
from fastapi.testclient import TestClient

mock_certificate = mock.patch('firebase_admin.credentials.Certificate').start()
mock_firebase_app = mock.patch('firebase_admin.initialize_app').start()

from routes import app
from unittest.mock import patch


client = TestClient(app)


nonexistent_meeting_id = ObjectId()
mock_meeting = {
    "_id": ObjectId(),
    "group_id": "deadbeef",
    "admin_id": "deadbeef",
    "is_finished": False,
    "title": "Mocked meeting",
    "start": datetime.datetime.now().isoformat(),
    "participants": [],
    "agenda": []
}
mock_user = {
    "_id": ObjectId(),
    "username": "user",
    "password": "password",
    "fcm_token": "notoken",
    "email": "user@mail.com",
    "meetings": [],
    "schedule": [],
    "groups": [],
}


async def mock_get_user(id):
    if id == str(mock_user["_id"]):
        return mock_user
    else:
        raise ValueError("Unknown meeting_id passed to mock_get_user")


async def mock_get_meeting(id):
    if id == str(nonexistent_meeting_id):
        raise HTTPException(status_code=404, detail=f"meeting {id} not found")
    elif id == str(mock_meeting["_id"]):
        return mock_meeting
    else:
        raise ValueError("Unknown meeting_id passed to mock_get_meeting")


async def mock_meetings_collection_find_one(query):
    id = query["_id"]
    if id == nonexistent_meeting_id:
        raise HTTPException(status_code=404, detail=f"meeting {id} not found")
    elif id == mock_meeting["_id"]:
        return mock_meeting
    else:
        raise ValueError("Unknown meeting_id passed to mock_meetings_collection_find_one")


def test_existing_meeting_is_shown():
    with (
        patch("routes.meetings_collection.find_one", side_effect=mock_meetings_collection_find_one),
        patch("routes.get_meeting", side_effect=mock_get_meeting),
    ):
        response = client.get(f"/meetings/{mock_meeting['_id']}")
    assert response.status_code == 200
    assert response.json()["id"] == str(mock_meeting['_id'])


def test_meeting_paricipants_are_returned():
    mock_meeting["participants"].append({"user_id": mock_user["_id"], "status": "needs acceptance"})
    with (
        patch("routes.meetings_collection.find_one", side_effect=mock_meetings_collection_find_one),
        patch("routes.get_meeting", side_effect=mock_get_meeting),
        patch("routes.get_user", side_effect=mock_get_user)
    ):
        response = client.get(f"/meetings/{mock_meeting['_id']}")
    assert response.status_code == 200
    assert response.json()["id"] == str(mock_meeting['_id'])
    participants = response.json()["participants"]
    assert len(participants) == 1
    user = participants[0]
    assert user["user_id"] == str(mock_user["_id"])
    assert user["username"] == mock_user["username"]
    assert user["status"] == "needs acceptance"
    mock_meeting["participants"].pop()


mock_certificate.stop()
mock_firebase_app.stop()

