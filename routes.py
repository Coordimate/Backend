import os
import json
import random
import datetime
from pathlib import Path
from typing import Any

import motor.motor_asyncio
from fastapi import FastAPI, HTTPException, Body, status, Depends, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pymongo import ReturnDocument  # , ObjectId
from dotenv import load_dotenv
from bson import ObjectId

import models
import schemas
import firebase_admin

import bcrypt
import auth
from auth import JWTBearer
from firebase_utils import notify_single_user
from src.group_schedule_manager import GroupsScheduleManager
from ws_manager import ConnectionManager


load_dotenv()


manager = ConnectionManager()
credentials = firebase_admin.credentials.Certificate(
    os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
)
firebase_app = firebase_admin.initialize_app(credentials)
app = FastAPI(
    title="Coordimate Backend API",
    summary="Backend of the Coordimate mobile application that fascilitates group meetings",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGODB_URL"])
db = client.coordimate
users_collection = db.get_collection("users")
meetings_collection = db.get_collection("meetings")
groups_collection = db.get_collection("groups")
time_slots_collection = db.get_collection("time_slots")


# ********** Authentification **********


def cmp_ids(l, r):
    if type(l) == type(r):
        return l == r
    return ObjectId(l) == ObjectId(r)


@app.post(
    "/login",
    response_description="Authentificate a user",
    response_model=schemas.TokenSchema,
    status_code=status.HTTP_200_OK,
    response_model_by_alias=False,
)
async def login(user: schemas.LoginUserSchema = Body(...)):
    if (user.auth_type == 'google'):
        if (user_found := await users_collection.find_one({"email": user.email.lower()})) is None:
            new_user = await users_collection.insert_one({'username': user.email.lower().split('@')[0], 'email': user.email})
            user_found = await get_user(new_user.inserted_id)
        token = auth.generateToken(schemas.AccountOut(id=str(user_found['_id']), email=user.email))
        await random_coffee(user_found["_id"])
        return token
    if (
        user_found := await users_collection.find_one({"email": user.email.lower()})
    ) is not None:
        user_found["id"] = user_found.pop("_id")
        await random_coffee(user_found["id"])
        if user.auth_type == "email":
            if user_found.get("password") is None:
                raise HTTPException(
                    status_code=409, detail=f"user regisered through external service"
                )
            if user.password is not None:
                if bcrypt.checkpw(user.password.encode("utf-8"), user_found["password"]):
                    token = auth.generateToken(schemas.AccountOut(id=str(user_found['id']), email=user.email.lower()))
                    return token
                else:
                    raise HTTPException(status_code=400, detail=f"password incorrect")
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"No password specified, our Google/Facebook Auth got us",
                )
        else:
            token = auth.generateToken(schemas.AccountOut(id=str(user_found['id']), email=user.email.lower()))
            return token

    raise HTTPException(status_code=404, detail=f"user {user.email.lower()} not found")


@app.post(
    "/refresh",
    response_description="Refresh a token",
    response_model=schemas.TokenSchema,
    status_code=status.HTTP_200_OK,
    response_model_by_alias=False,
)
async def refresh_token(token: schemas.RefreshTokenSchema = Body(...)):
    decoded_token = auth.decodeJWT(token.refresh_token)
    if (decoded_token is None) or (decoded_token.is_access_token != False):
        raise HTTPException(status_code=401, detail="Invalid token or expired token.")
    new_token = auth.generate_refresh_token(token.refresh_token, decoded_token)
    return new_token


@app.get(
    "/me",
    response_description="Get account information",
    response_model=schemas.AccountOut,
)
async def me(user: schemas.AuthSchema = Depends(JWTBearer())):
    user_found = await get_user(user.id)
    return schemas.AccountOut(id=str(user_found["_id"]), email=user_found["email"])


@app.post(
    "/enable_notifications",
    response_description="Enable notifications for user",
    response_model_by_alias=False,
)
async def enable_notifications(
    notifications: schemas.NotificationsSchema,
    user: schemas.AuthSchema = Depends(JWTBearer()),
):
    user_found = await get_user(user.id)
    user_found["fcm_token"] = notifications.fcm_token
    await users_collection.find_one_and_update(
        {"_id": user_found["_id"]}, {"$set": user_found}
    )
    return {"result": "ok"}


# ********** Users **********


@app.post(
    "/register",
    response_description="Add new user",
    response_model=models.UserModel,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def register(user: schemas.CreateUserSchema = Body(...)):
    existing_user = await users_collection.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=409, detail="User already exists")
    if user.auth_type == "email":
        if user.password is not None:
            user.password = bcrypt.hashpw(
                user.password.encode("utf-8"), bcrypt.gensalt()
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"No password specified, our Google/Facebook Auth got us",
            )
    user_dict = user.model_dump(by_alias=True, exclude={"id"})
    user_dict["email"] = user_dict["email"].lower()
    user_dict["fcm_token"] = "notoken"
    new_user = await users_collection.insert_one(user_dict)
    created_user = await users_collection.find_one({"_id": new_user.inserted_id})
    return created_user


@app.post(
    "/change_password",
    response_description="Change user password",
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def change_password(
    request: schemas.ChangePasswordSchema,
    user: schemas.AuthSchema = Depends(JWTBearer()),
):
    user_found = await get_user(user.id)

    if not bcrypt.checkpw(request.old_password.encode("utf-8"), user_found["password"]):
        raise HTTPException(status_code=403, detail="Could not change password")

    user_found["password"] = bcrypt.hashpw(
        request.new_password.encode("utf-8"), bcrypt.gensalt()
    )
    await users_collection.find_one_and_update(
        {"_id": user_found["_id"]}, {"$set": user_found}
    )
    return {"result": "ok"}


@app.get(
    "/users",
    response_description="List all users",
    response_model=models.UserCollection,
    response_model_by_alias=False,
)
async def list_users():
    return models.UserCollection(users=await users_collection.find().to_list(1000))


@app.get(
    "/users/{id}",
    response_description="Get a single user",
    response_model=models.UserModel,
    response_model_by_alias=False,
)
async def show_user(id: str):
    user = await get_user(id)
    if 'password' not in user:
        user["password"] = ''
    return user


@app.patch(
    "/users/{id}",
    response_description="Update a user",
    response_model=models.UserModel,
    response_model_by_alias=False,
)
async def update_user(id: str, user: models.UpdateUserModel = Body(...)):
    user_dict = {
        k: v for k, v in user.model_dump(by_alias=True).items() if v is not None
    }
    if user.random_coffee == {}:
        user_dict['random_coffee'] = None

    if len(user_dict) >= 1:
        update_result = await users_collection.find_one_and_update(
            {"_id": ObjectId(id)},
            {"$set": user_dict},
            return_document=ReturnDocument.AFTER,
        )
        if update_result is not None:
            return update_result
        else:
            raise HTTPException(status_code=404, detail=f"user {id} not found")
    existing_user = await get_user(id)
    if "password" not in existing_user:
        existing_user["password"] = ""
    return existing_user


@app.delete("/users/{id}", response_description="Delete a user")
async def delete_user(id: str):
    user = await get_user(id)

    user_meetings = user.get("meetings", [])
    for meeting in user_meetings:
        await meetings_collection.update_one(
            {"_id": ObjectId(meeting["meeting_id"])},
            {"$pull": {"participants": {"user_id": str(user["_id"])}}},
        )

    for group in user.get("groups", []):
        await groups_collection.update_one(
            {"_id": ObjectId(group["_id"])},
            {"$pull": {"users": {"_id": str(user["_id"])}}}
        )

    await users_collection.delete_one({"_id": ObjectId(id)})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ********** Time Slots **********


@app.get(
    "/time_slots",
    response_description="List all time slots",
    response_model=schemas.TimeSlotCollection,
    response_model_by_alias=False,
)
async def list_time_slots(user: schemas.AuthSchema = Depends(JWTBearer())):
    user_found = await get_user(user.id)
    schedule = user_found.get("schedule")
    if schedule is None:
        return schemas.TimeSlotCollection(time_slots=[])
    return schemas.TimeSlotCollection(time_slots=await time_slots_collection.find({"_id": {"$in": schedule}}).to_list(100))


@app.post(
    "/time_slots",
    response_description="Add new time slot",
    response_model=models.TimeSlot,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_time_slot(
    time_slot: models.TimeSlot = Body(...),
    user: schemas.AuthSchema = Depends(JWTBearer()),
):
    user_found = await get_user(user.id)
    if not user_found.get("schedule"):
        user_found["schedule"] = []

    time_slot_created = await time_slots_collection.insert_one(time_slot.model_dump(by_alias=True, exclude={"id"}))
    user_found["schedule"].append(time_slot_created.inserted_id)

    await users_collection.update_one(
        {"_id": user_found["_id"]}, {"$set": {"schedule": user_found["schedule"]}}
    )
    new_time_slot = await time_slots_collection.find_one({"_id": time_slot_created.inserted_id})
    return new_time_slot


@app.patch(
    "/time_slots/{slot_id}",
    response_description="Update a time slot",
    response_model=models.TimeSlot,
    response_model_by_alias=False,
)
async def update_time_slot(
    slot_id: str,
    time_slot: schemas.UpdateTimeSlot = Body(...),
    user: schemas.AuthSchema = Depends(JWTBearer()),
):
    _ = await get_user(user.id)
    time_slot_dict = {
        k: v for k, v in time_slot.model_dump(by_alias=True, exclude={"_id"}).items() if v is not None
    }

    updated_time_slot = await get_time_slot(slot_id)
    updated_time_slot.update(time_slot_dict)
    await time_slots_collection.update_one(
        {"_id": ObjectId(slot_id)}, {"$set": updated_time_slot}
    )
    return updated_time_slot


@app.delete("/time_slots/{slot_id}", response_description="Delete a time slot")
async def delete_time_slot(
    slot_id: str, user: schemas.AuthSchema = Depends(JWTBearer())
):
    user_found = await get_user(user.id)

    await time_slots_collection.delete_one({"_id": ObjectId(slot_id)})

    await users_collection.update_one(
        {"_id": ObjectId(user_found["_id"])}, {"$pull": {"schedule": {"_id": ObjectId(slot_id)}}}
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ********** Meetings **********


@app.post(
    "/meetings",
    response_description="Add new meeting",
    response_model=models.MeetingModel,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_meeting(
    meeting: schemas.CreateMeeting = Body(...),
    user: schemas.AuthSchema = Depends(JWTBearer()),
):
    user_found = await get_user(user.id)
    meeting_dict = meeting.model_dump(by_alias=True, exclude={"id"})
    meeting_dict["admin_id"] = str(user_found["_id"])
    meeting_dict["is_finished"] = False
    length = meeting.length if meeting.length is not None else 60
    meeting_dict["time_slot_id"] = await isoformat_to_timeslot(meeting.start, length)
    new_meeting = await meetings_collection.insert_one(meeting_dict)
    created_meeting = await meetings_collection.find_one(
        {"_id": new_meeting.inserted_id}
    )
    if created_meeting is None:
        raise HTTPException(status_code=500, detail="Error creating a meeting")

    group = await get_group(meeting.group_id)
    if "meetings" not in group:
        group["meetings"] = []
    group["meetings"].append(get_meeting_card(created_meeting))
    await groups_collection.find_one_and_update({"_id": group["_id"]}, {"$set": group})

    created_meeting["participants"] = []
    for group_user in group["users"]:
        user_found = await get_user(group_user["_id"])
        if user_found.get("meetings") is None:
            user_found["meetings"] = []
        user_found["meetings"].append(
            {
                "meeting_id": str(created_meeting["_id"]),
                "status": (
                    models.MeetingStatus.needs_acceptance.value
                    if str(user_found["_id"]) != user.id
                    else models.MeetingStatus.accepted.value
                ),
            }
        )
        await users_collection.update_one(
            {"_id": user_found["_id"]}, {"$set": {"meetings": user_found["meetings"]}}
        )

        created_meeting["participants"].append(
            {
                "user_id": str(user_found["_id"]),
                "username": user_found["username"],
                "status": (
                    models.MeetingStatus.needs_acceptance.value
                    if str(user_found["_id"]) != user.id
                    else models.MeetingStatus.accepted.value
                ),
            }
        )
        notify_single_user(
            user_found["fcm_token"],
            "Meeting Invitation",
            f"Join the meeting {created_meeting['title']} with group {group['name']}, time: {created_meeting['start']}",
        )

    await meetings_collection.update_one(
        {"_id": created_meeting["_id"]},
        {"$set": {"participants": created_meeting["participants"]}},
    )
    return created_meeting


@app.get(
    "/meetings/all",
    response_description="List all meetings",
    response_model=schemas.MeetingCollection,
    response_model_by_alias=False,
)
async def list_meetings():
    meetings = await meetings_collection.find().to_list(1000)

    updated_meetings = []
    for meeting in meetings:
        participants = []
        for meeting_participant in meeting["participants"]:
            participant_user = await get_user(str(meeting_participant["user_id"]))
            participant = models.Participant(
                user_id=str(participant_user["_id"]),
                username=participant_user["username"],
                status=meeting_participant["status"],
            )
            participants.append(participant)
        meeting["participants"] = participants
        updated_meetings.append(meeting)
    return schemas.MeetingCollection(meetings=updated_meetings)


@app.get(
    "/meetings",
    response_description="List all meetings of a user",
    response_model=schemas.MeetingTileCollection,
    response_model_by_alias=False,
)
async def list_user_meetings(user: schemas.AuthSchema = Depends(JWTBearer())):
    user_found = await get_user(user.id)
    meeting_invites = user_found.get("meetings", [])
    meetings = []
    for invite in meeting_invites:
        meeting = await meetings_collection.find_one(
            {"_id": ObjectId(invite["meeting_id"])}
        )
        if meeting is not None:
            group = await get_group(meeting["group_id"])
            meeting_tile = models.MeetingTile(
                id=str(meeting["_id"]),
                title=meeting["title"],
                start=meeting["start"],
                length=meeting["length"],
                group=models.GroupCardModel(_id=group["_id"], name=group["name"]),
                status=invite["status"],
                is_finished=meeting["is_finished"],
            )
            meetings.append(meeting_tile)
            await try_finish_meeting(meeting)

    return schemas.MeetingTileCollection(meetings=meetings)


@app.get(
    "/meetings/{id}",
    response_description="Get a single meeting",
    response_model=models.MeetingModel,
    response_model_by_alias=False,
)
async def show_meeting(id: str):
    if (
        meeting := await meetings_collection.find_one({"_id": ObjectId(id)})
    ) is not None:

        participants = []
        for meeting_participant in meeting["participants"]:
            participant_user = await get_user(str(meeting_participant["user_id"]))
            participant = models.Participant(
                user_id=str(participant_user["_id"]),
                username=participant_user["username"],
                status=meeting_participant["status"],
            )
            participants.append(participant)
        meeting["participants"] = participants
        return meeting

    raise HTTPException(status_code=404, detail=f"meeting {id} not found")


@app.get(
    "/meetings/{id}/details",
    response_description="Get details of a single meeting",
    response_model=schemas.MeetingDetails,
    response_model_by_alias=False,
)
async def show_meeting_details(
    id: str, user: schemas.AuthSchema = Depends(JWTBearer())
):
    user_found = await get_user(user.id)
    meeting = await get_meeting(id)

    meeting_participants = meeting.get("participants", [])
    participants = []
    for meeting_participant in meeting_participants:
        participant_user = await get_user(str(meeting_participant["user_id"]))
        participant = schemas.ParticipantSchema(
            user_id=str(participant_user["_id"]),
            user_username=participant_user["username"],
            status=meeting_participant["status"],
        )
        participants.append(participant)

    admin_user = await get_user(str(meeting["admin_id"]))
    admin = schemas.ParticipantSchema(
        user_id=str(admin_user["_id"]),
        user_username=admin_user["username"],
        status=models.MeetingStatus.accepted.value,
    )

    group = await get_group(meeting["group_id"])
    meeting_invites = user_found.get("meetings", [])
    for invite in meeting_invites:
        if invite["meeting_id"] == id:
            meeting_tile = schemas.MeetingDetails(
                id=str(meeting["_id"]),
                title=meeting["title"],
                start=meeting["start"],
                length=meeting["length"],
                summary=meeting.get("summary", ""),
                is_finished=meeting.get("is_finished", False),
                group_id=str(group["_id"]),
                group_name=group["name"],
                admin=admin,
                description=meeting["description"],
                participants=participants,
                meeting_link=meeting.get("meeting_link", None),
                google_event_id=meeting.get("google_event_id", None),
                status=invite["status"],
            )
            return meeting_tile


@app.patch(
    "/meetings/{id}/change_participant_status",
    response_description="Change status of participant in a meeting",
    response_model=schemas.ParticipantInviteSchema,
    response_model_by_alias=False,
)
async def change_participant_status(
    id: str,
    participant: schemas.UpdateParticipantStatus = Body(...),
    user: schemas.AuthSchema = Depends(JWTBearer()),
):
    _ = await get_user(user.id)
    await get_user(participant.user_id)
    await get_meeting(id)

    check_status(participant.status)
    await meeting_in_user(participant.user_id, id, participant.status)
    await participant_in_meeting(participant.user_id, id, participant.status)
    return schemas.ParticipantInviteSchema(
        meeting_id=id, user_id=participant.user_id, status=participant.status
    )


@app.post(
    "/meetings/{id}/invite",
    response_description="Invite user to a meeting",
    response_model=schemas.ParticipantInviteSchema,
    response_model_by_alias=False,
)
async def invite(id: str, user: schemas.AuthSchema = Depends(JWTBearer())):
    await get_user(user.id)
    await get_meeting(id)
    await participant_in_meeting(
        user.id, id, models.MeetingStatus.needs_acceptance.value
    )
    await meeting_in_user(user.id, id, models.MeetingStatus.needs_acceptance.value)
    return schemas.ParticipantInviteSchema(
        meeting_id=id,
        user_id=user.id,
        status=models.MeetingStatus.needs_acceptance.value,
    )


@app.patch(
    "/invites/{id}",
    response_description="Change status of invitation",
    response_model=models.MeetingInvite,
    response_model_by_alias=False,
)
async def change_invite_status(
    id: str,
    status: schemas.UpdateMeetingStatus = Body(...),
    user: schemas.AuthSchema = Depends(JWTBearer()),
):
    check_status(status.status)
    await get_user(user.id)
    await get_meeting(id)
    await meeting_in_user(user.id, id, status.status)
    await participant_in_meeting(user.id, id, status.status)
    return models.MeetingInvite(meeting_id=id, status=status.status)


@app.patch(
    "/meetings/{id}",
    response_description="Update a meeting",
    response_model=models.MeetingModel,
    response_model_by_alias=False,
)
async def update_meeting(id: str, meeting: schemas.UpdateMeeting = Body(...)):
    meeting_dict = {
        k: v for k, v in meeting.model_dump(by_alias=True).items() if v is not None
    }

    if len(meeting_dict) >= 1:
        meeting_found = await get_meeting(id)
        group = await get_group(meeting_found["group_id"])
        for i, invite in enumerate(group["meetings"]):
            if invite["_id"] == id:
                invite.update(meeting_dict)
                group["meetings"][i] = invite
                break
        await groups_collection.find_one_and_update(
            {"_id": group["_id"]}, {"$set": group}
        )

        updated_meeting = meeting_found.copy()
        updated_meeting.update(meeting_dict)
        for i, u in enumerate(meeting_found["participants"]):
            user = await get_user(u["user_id"])
            for j, invite in enumerate(user["meetings"]):
                if cmp_ids(invite["meeting_id"], id):
                    invite.update(meeting_dict)
                    user["meetings"][j] = invite
                    if meeting_dict.get('is_finished', False) and meeting_found["participants"][i]["status"] == models.MeetingStatus.needs_acceptance:
                        user["meetings"][j]["status"] = models.MeetingStatus.declined
                    break
            await users_collection.find_one_and_update(
                {"_id": user["_id"]}, {"$set": user}
            )

            if meeting_dict.get('is_finished', False) and meeting_found["participants"][i]["status"] == models.MeetingStatus.needs_acceptance:
                updated_meeting["participants"][i]["status"] = models.MeetingStatus.declined
            notify_single_user(
                user["fcm_token"],
                "Meeting Update",
                f"The meeting {updated_meeting['title']} with group {group['name']}, time: {updated_meeting['start']}, just got updated.",
            )

        length = meeting.length if meeting.length is not None else meeting_found['length']
        start = meeting.start if meeting.start else meeting_found['start']
        await time_slots_collection.find_one_and_delete({"_id": ObjectId(meeting_found['time_slot_id'])})
        updated_meeting["time_slot_id"] = await isoformat_to_timeslot(start, length)

        update_result = await meetings_collection.find_one_and_update(
            {"_id": ObjectId(id)},
            {"$set": updated_meeting},
            return_document=ReturnDocument.AFTER,
        )
        if update_result is not None:
            return update_result
        else:
            raise HTTPException(status_code=404, detail=f"meeting {id} not found")

    if (
        existing_meeting := await meetings_collection.find_one({"_id": id})
    ) is not None:
        return existing_meeting

    raise HTTPException(status_code=404, detail=f"meeting {id} not found")


@app.delete("/meetings/{id}", response_description="Delete a meeting")
async def delete_meeting(id: str):
    meeting = await get_meeting(id)
    group = await get_group(meeting["group_id"])

    meetings = []
    for m in group["meetings"]:
        if m["_id"] != id:
            meetings.append(m)
    group["meetings"] = meetings
    await groups_collection.find_one_and_update({"_id": group["_id"]}, {"$set": group})

    for u in meeting["participants"]:
        user = await get_user(u["user_id"])
        meetings = []
        for invite in user["meetings"]:
            if invite["meeting_id"] != id:
                meetings.append(invite)
        user["meetings"] = meetings
        await users_collection.find_one_and_update({"_id": user["_id"]}, {"$set": user})
        notify_single_user(
            user["fcm_token"],
            "Meeting Cancelled",
            f"The meeting {meeting['title']} with group {group['name']}, time: {meeting['start']}, was cancelled.",
        )

    delete_result = await meetings_collection.delete_one({"_id": ObjectId(id)})
    await time_slots_collection.find_one_and_delete({"_id": ObjectId(meeting["time_slot_id"])})

    if delete_result.deleted_count == 1:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(status_code=404, detail=f"meeting {id} not found")


@app.post("/meetings/{id}/suggest_location", response_description="Suggestion offline location for a meeting")
async def suggest_meeting_location(id: str):
    locations = []
    meeting = await get_meeting(id)

    for u in meeting["participants"]:
        user = await get_user(u["user_id"])
        if "last_location" in user:
            lat, lon = map(float, user["last_location"].split(","))
            locations.append((lat, lon))
    if len(locations) == 0:
        raise HTTPException(status_code=404, detail=f"No user locations available to pick a meeting spot")
    point = ','.join(map(str, [sum(x)/len(x) for x in zip(*locations)]))
    return {"link": f"https://www.google.com/maps/search/cafe/@{point},16z"}


# ********* Agenda Points ********


@app.get(
    "/meetings/{id}/agenda",
    response_description="List all agenda points for a meeting",
    response_model=schemas.AgendaPointCollection,
    response_model_by_alias=False,
)
async def list_agenda(id: str, user: schemas.AuthSchema = Depends(JWTBearer())):
    _ = await get_user(user.id)
    meeting = await get_meeting(id)

    if "agenda" not in meeting:
        return schemas.AgendaPointCollection(agenda=[])
    return schemas.AgendaPointCollection(agenda=meeting["agenda"])


@app.post(
    "/meetings/{id}/agenda",
    response_description="Add a new agenda point",
    response_model=models.AgendaPoint,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_agenda_point(
    id: str,
    agenda_point: schemas.CreateAgendaPoint = Body(...),
    user: schemas.AuthSchema = Depends(JWTBearer()),
):
    _ = await get_user(user.id)
    meeting = await get_meeting(id)

    if "agenda" not in meeting:
        meeting["agenda"] = []

    new_agenda_point = agenda_point.model_dump(by_alias=True)
    meeting["agenda"].append(new_agenda_point)

    await meetings_collection.update_one(
        {"_id": meeting["_id"]}, {"$set": {"agenda": meeting["agenda"]}}
    )
    return new_agenda_point


@app.patch(
    "/meetings/{id}/agenda",
    response_description="Update meeting agenda",
    response_model=schemas.AgendaPointCollection,
    response_model_by_alias=False,
)
async def update_agenda(
    id: str,
    agenda: schemas.AgendaPointCollection = Body(...),
    user: schemas.AuthSchema = Depends(JWTBearer()),
):
    _ = await get_user(user.id)
    meeting = await get_meeting(id)

    _ = await meetings_collection.update_one(
        {"_id": ObjectId(meeting["_id"])},
        {"$set": {"agenda": agenda.model_dump()["agenda"]}},
    )

    meeting = await get_meeting(id)
    return schemas.AgendaPointCollection(agenda=meeting["agenda"])


@app.delete(
    "/meetings/{id}/agenda/{point_id}", response_description="Delete an agenda point"
)
async def delete_agenda_point(
    id: str, point_id: int, user: schemas.AuthSchema = Depends(JWTBearer())
):
    _ = await get_user(user.id)
    meeting = await get_meeting(id)

    if point_id < 0 or point_id >= len(meeting["agenda"]):
        raise HTTPException(status_code=404, detail=f"agenda_point {id} not found")
    agenda = meeting["agenda"]
    agenda.pop(point_id)

    _ = await meetings_collection.update_one(
        {"_id": ObjectId(meeting["_id"])}, {"$set": {"agenda": agenda}}
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ********** Groups **********


@app.post(
    "/groups",
    response_description="Create new group",
    response_model=models.GroupModel,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_group(
    group: schemas.CreateGroupSchema = Body(...),
    user: schemas.AuthSchema = Depends(JWTBearer()),
):
    user_found = await get_user(user.id)
    user_card = get_user_card(user_found)

    group_dict = group.model_dump(by_alias=True, exclude={"id"})
    group_dict["admin"] = user_card
    group_dict["users"] = [user_card]
    group_dict["chat_messages"] = "[]"

    new_group = await groups_collection.insert_one(group_dict)
    created_group = await groups_collection.find_one({"_id": new_group.inserted_id})

    group_card = get_group_card(created_group)
    if "groups" not in user_found:
        user_found["groups"] = []
    user_found["groups"].append(group_card)

    await users_collection.update_one({"_id": user_found["_id"]}, {"$set": user_found})
    return created_group


@app.get(
    "/groups",
    response_description="List all groups",
    response_model=models.GroupCollection,
    response_model_by_alias=False,
)
async def list_groups(user: schemas.AuthSchema = Depends(JWTBearer())):
    user_found = await get_user(user.id)
    user_groups = user_found.get("groups", [])
    if not user_groups:
        return models.GroupCollection(groups=[])

    group_ids = [ObjectId(group["_id"]) for group in user_groups]
    return models.GroupCollection(
        groups=await groups_collection.find({"_id": {"$in": group_ids}}).to_list(100)
    )


@app.get(
    "/groups/{id}",
    response_description="Get a single group",
    response_model=models.GroupModel,
    response_model_by_alias=False,
)
async def show_group(id: str, user: schemas.AuthSchema = Depends(JWTBearer())):
    _ = await get_user(user.id)
    if (group := await groups_collection.find_one({"_id": ObjectId(id)})) is not None:
        group["admin"] = get_user_card(await get_user(group["admin"]["_id"]))
        group["users"] = [get_user_card(await get_user(u["_id"])) for u in group["users"]]
        group["meetings"] = [get_meeting_card(await get_meeting(m["_id"])) for m in group.get("meetings", [])]
        return group

    raise HTTPException(status_code=404, detail=f"group {id} not found")


@app.patch(
    "/groups/{id}",
    response_description="Update a group",
    response_model=models.GroupModel,
    response_model_by_alias=False,
)
async def update_group(
    id: str,
    group: models.UpdateGroupModel = Body(...),
    user: schemas.AuthSchema = Depends(JWTBearer()),
):
    _ = await get_user(user.id)
    group_dict = {
        k: v for k, v in group.model_dump(by_alias=True).items() if v is not None
    }

    if len(group_dict) >= 1:
        update_result = await groups_collection.find_one_and_update(
            {"_id": ObjectId(id)},
            {"$set": group_dict},
            return_document=ReturnDocument.AFTER,
        )
        if update_result is not None:
            return update_result
        else:
            raise HTTPException(status_code=404, detail=f"group {id} not found")

    if (existing_group := await groups_collection.find_one({"_id": id})) is not None:
        return existing_group

    raise HTTPException(status_code=404, detail=f"group {id} not found")


@app.delete("/groups/{id}", response_description="Delete a group")
async def delete_group(id: str, user: schemas.AuthSchema = Depends(JWTBearer())):
    _ = await get_user(user.id)
    group = await get_group(id)

    if "meetings" in group:
        meeting_ids_to_delete = [m["_id"] for m in await meetings_collection.find({"group_id": id}, {"_id"}).to_list(1000)]
        await meetings_collection.delete_many({"_id": {"$in": meeting_ids_to_delete}})

        meeting_ids_to_delete = set(meeting_ids_to_delete)
        for u in group["users"]:
            found_user = await get_user(u["_id"])
            new_meetings = []
            for invite in found_user["meetings"]:
                if ObjectId(invite["meeting_id"]) in meeting_ids_to_delete:
                    continue
                new_meetings.append(invite)
            found_user["meetings"] = new_meetings
            await users_collection.find_one_and_update({"_id": found_user["_id"]}, {"$set": found_user})

    user_ids_to_cleanup = [ObjectId(u["_id"]) for u in group["users"]]
    for user_id in user_ids_to_cleanup:
        user_found = await get_user(str(user_id))
        user_found["groups"] = [g for g in user_found["groups"] if g["_id"] != id]
        await users_collection.find_one_and_update(
            {"_id": user_id}, {"$set": user_found}
        )

    delete_result = await groups_collection.delete_one({"_id": ObjectId(id)})
    if delete_result.deleted_count == 1:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(status_code=404, detail=f"group {id} not found")


@app.post("/groups/{id}/leave", response_description="Leave the group as a user")
async def leave_group(id: str, user: schemas.AuthSchema = Depends(JWTBearer())):
    user_found = await get_user(user.id)
    group_found = await get_group(id)
    if ObjectId(group_found["admin"]["_id"]) == user_found["_id"]:
        raise HTTPException(status_code=400, detail="Can't leave group as the group admin")

    user_found['groups'] = [
        group_card for group_card in user_found['groups']
        if ObjectId(group_card['_id']) != group_found['_id']
    ]
    group_found['users'] = [
        user_card for user_card in group_found['users']
        if ObjectId(user_card['_id']) != user_found['_id']
    ]

    chat = group_found.get("chat_messages")
    cleaned_chat = []
    if chat is not None:
        msgs = json.loads(chat)
        for msg in msgs:
            if ObjectId(msg['user_id']) != user_found['_id']:
                cleaned_chat.append(msg)
        group_found['chat_messages'] = json.dumps(cleaned_chat)

    poll = group_found.get("poll")
    if poll is not None:
        for opt in poll["votes"]:
            if user.id in poll["votes"][opt]:
                poll["votes"][opt].remove(user.id)

    await users_collection.find_one_and_update({"_id": user_found["_id"]}, {"$set": user_found})
    await groups_collection.find_one_and_update({"_id": group_found["_id"]}, {"$set": group_found})
    return "ok"


@app.delete("/groups/{id}/poll", response_description="Delete a group poll")
async def delete_poll(id: str, user: schemas.AuthSchema = Depends(JWTBearer())):
    _ = await get_user(user.id)
    _ = await get_group(id)
    await groups_collection.find_one_and_update({"_id": ObjectId(id)}, {"$set": {"poll": None}})
    return "ok"


@app.post("/groups/{id}/poll/{option_index}", response_description="Vote on a group poll")
async def vote_on_poll(id: str, option_index: str, user: schemas.AuthSchema = Depends(JWTBearer())):
    _ = await get_user(user.id)
    group_found = await get_group(id)

    poll = group_found["poll"]
    if "votes" not in poll or poll["votes"] is None:
        poll["votes"] = {str(i): [] for i in range(len(poll["options"]))}

    for opt in poll["votes"]:
        if user.id in poll["votes"][opt]:
            poll["votes"][opt].remove(user.id)
    poll["votes"][option_index].append(user.id)

    await groups_collection.find_one_and_update({"_id": ObjectId(id)}, {
        "$set": {
            "poll": poll
        }
    })
    return "ok"


@app.get(
    "/groups/{id}/invite",
    response_description="Get a link to invite user to a group",
    response_model=schemas.GroupInviteResponse,
    response_model_by_alias=False,
)
async def group_invite(id: str, user: schemas.AuthSchema = Depends(JWTBearer())):
    _ = await get_user(user.id)
    _ = await get_group(id)

    link = f"coordimate://coordimate.com/groups/{id}/join"
    return schemas.GroupInviteResponse(join_link=link)


@app.post(
    "/groups/{id}/join",
    response_description="Join a group using the invite link",
)
async def join_group(id: str, user: schemas.AuthSchema = Depends(JWTBearer())):
    user_found = await get_user(user.id)
    group_found = await get_group(id)

    for group_user in group_found["users"]:
        if ObjectId(group_user["_id"]) == user_found["_id"]:
            return {"result": "ok"}

    user_card = get_user_card(user_found)
    group_card = get_group_card(group_found)

    group_found["users"].append(user_card)
    if "groups" not in user_found:
        user_found["groups"] = []
    user_found["groups"].append(group_card)

    if 'meetings' not in user_found:
        user_found['meetings'] = []
    if 'meetings' not in group_found:
        group_found['meetings'] = []
    for meeting in group_found['meetings']:
        meeting_found = await meetings_collection.find_one({"_id": ObjectId(meeting["_id"])})
        if meeting_found is None:
            continue

        now = datetime.datetime.now(datetime.UTC)
        meeting_time = datetime.datetime.fromisoformat(meeting_found["start"])
        if meeting_time + datetime.timedelta(minutes=meeting_found["length"]) < now:
            continue

        user_found["meetings"].append(
            {
                "meeting_id": str(meeting["_id"]),
                "status": models.MeetingStatus.needs_acceptance.value,
            }
        )
        meeting_found["participants"].append(
            {
                "user_id": str(user_found["_id"]),
                "username": user_found["username"],
                "status": models.MeetingStatus.needs_acceptance.value,
            }
        )
        await meetings_collection.find_one_and_update(
            {"_id": ObjectId(meeting["_id"])},
            {"$set": meeting_found},
            return_document=ReturnDocument.AFTER
        )

    await users_collection.find_one_and_update(
        {"_id": user_found["_id"]}, {"$set": user_found}
    )
    await groups_collection.find_one_and_update(
        {"_id": group_found["_id"]}, {"$set": group_found}
    )

    return {"result": "ok"}


@app.get(
    "/groups/{id}/time_slots",
    response_description="View schedule of a user",
    response_model=schemas.TimeSlotCollection,
    response_model_by_alias=False,
)
async def group_schedule(id, user: schemas.AuthSchema = Depends(JWTBearer())):
    _ = await get_user(user.id)
    group = await get_group(id)

    schedule = []
    for user_card in group['users']:
        user_found = await get_user(user_card['_id'])
        assert user_found is not None
        schedule += await time_slots_collection.find({"_id": {"$in": user_found.get("schedule", [])}}).to_list(1000)

    for i in range(len(schedule)):
        schedule[i]["_id"] = str(schedule[i]["_id"])

    gsm = GroupsScheduleManager([schedule], schedule)
    group_schedule = [models.TimeSlot(**params) for params in gsm.compute_group_schedule()]

    for meeting_card in group.get('meetings', []):
        meeting = await get_meeting(meeting_card["_id"])
        meeting_time_slot = await time_slots_collection.find_one({"_id": meeting["time_slot_id"]})
        if meeting_time_slot is not None:
            if (datetime.datetime.fromisoformat(meeting_time_slot['start']) >= datetime.datetime.now(datetime.UTC)):
                group_schedule.append(meeting_time_slot)
    return schemas.TimeSlotCollection(time_slots=group_schedule)


@app.get(
    "/groups/{id}/meetings",
    response_description="List all meetings of the group",
    response_model=schemas.MeetingTileCollection,
    response_model_by_alias=False,
)
async def list_group_meetings(
    id: str,
    user: schemas.AuthSchema = Depends(JWTBearer()),
):
    _ = await get_user(user.id)
    group = await get_group(id)
    meetings = group.get("meetings", [])
    response_meetings = []
    for meeting in meetings:
        meeting_found = await meetings_collection.find_one(
            {"_id": ObjectId(meeting["_id"])}
        )
        if meeting_found is not None:
            meeting_tile = models.MeetingTile(
                id=str(meeting["_id"]),
                title=meeting_found["title"],
                start=meeting_found["start"],
                length=meeting["length"],
                group=models.GroupCardModel(_id=group["_id"], name=group["name"]),
                status=models.MeetingStatus.accepted,
                is_finished=meeting_found["is_finished"],
            )
            response_meetings.append(meeting_tile)

    return schemas.MeetingTileCollection(meetings=response_meetings)


# ********** Share Schedule ***********


@app.get(
    "/share_schedule",
    response_description="Get link to share personal schedule",
    response_model=schemas.ShareScheduleResponse,
    response_model_by_alias=False,
)
async def share_personal_schedule(user: schemas.AuthSchema = Depends(JWTBearer())):
    user_found = await get_user(user.id)
    link = f"coordimate://coordimate.com/users/{user_found['_id']}/time_slots"
    return schemas.ShareScheduleResponse(schedule_link=link)


@app.get(
    "/users/{id}/time_slots",
    response_description="View schedule of a user",
    response_model=schemas.TimeSlotCollection,
    response_model_by_alias=False,
)
async def list_user_time_slots(id, user: schemas.AuthSchema = Depends(JWTBearer())):
    _ = await get_user(user.id)
    other_user = await get_user(id)

    schedule = await time_slots_collection.find({"_id": {"$in": other_user.get("schedule", [])}}).to_list(1000)
    for i in range(len(schedule)):
        schedule[i]["_id"] = str(schedule[i]["_id"])

    return schemas.TimeSlotCollection(time_slots=schedule)


# ********** Utils **********


async def get_time_slot(time_slot_id: str) -> dict:
    time_slot = await time_slots_collection.find_one({"_id": ObjectId(time_slot_id)})
    if time_slot is None:
        raise HTTPException(status_code=404, detail=f"time slot {time_slot_id} not found")
    return time_slot


async def get_user(user_id: str) -> dict:
    user_found = await users_collection.find_one({"_id": ObjectId(user_id)})
    if user_found is None:
        raise HTTPException(status_code=404, detail=f"user {user_id} not found")
    return user_found


async def get_meeting(meeting_id: str) -> dict:
    meeting_found = await meetings_collection.find_one({"_id": ObjectId(meeting_id)})
    if meeting_found is None:
        raise HTTPException(status_code=404, detail=f"meeting {meeting_id} not found")
    return meeting_found


async def get_group(group_id: str) -> dict:
    group_found = await groups_collection.find_one({"_id": ObjectId(group_id)})
    if group_found is None:
        raise HTTPException(status_code=404, detail=f"group {group_id} not found")
    return group_found


def get_user_card(user):
    return models.UserCardModel(_id=user["_id"], username=user["username"]).model_dump(
        by_alias=True
    )


def get_group_card(group):
    return models.GroupCardModel(_id=group["_id"], name=group["name"]).model_dump(
        by_alias=True
    )


def get_meeting_card(meeting):
    return models.MeetingCardModel(
        _id=str(meeting["_id"]), title=meeting["title"], start=meeting["start"], length=meeting["length"]
    ).model_dump(by_alias=True)


async def meeting_in_user(user_id: str, meeting_id: str, status: str) -> dict:
    user_found = await get_user(user_id)
    await get_meeting(meeting_id)
    if user_found.get("meetings") is None:
        user_found["meetings"] = []
    if status == models.MeetingStatus.needs_acceptance.value:
        user_found["meetings"].append({"meeting_id": meeting_id, "status": status})
    else:
        for meeting in user_found["meetings"]:
            if meeting["meeting_id"] == meeting_id:
                meeting["status"] = status
                break
    await users_collection.update_one(
        {"_id": user_found["_id"]}, {"$set": {"meetings": user_found["meetings"]}}
    )
    return user_found


async def participant_in_meeting(user_id: str, meeting_id: str, status: str) -> dict:
    meeting_found = await get_meeting(meeting_id)
    await get_user(user_id)
    if meeting_found.get("participants") is None:
        meeting_found["participants"] = []
    if status == models.MeetingStatus.needs_acceptance.value:
        meeting_found["participants"].append({"user_id": user_id, "status": status})
    else:
        for participant in meeting_found["participants"]:
            if participant["user_id"] == user_id:
                participant["status"] = status
                break
    await meetings_collection.update_one(
        {"_id": meeting_found["_id"]},
        {"$set": {"participants": meeting_found["participants"]}},
    )
    return meeting_found


def check_status(status: str) -> bool:
    if status not in models.MeetingStatus.__members__:
        raise HTTPException(status_code=400, detail="Invalid status")
    return True


async def isoformat_to_timeslot(time_string: str, length: int):
    date = datetime.datetime.fromisoformat(time_string)
    time_slot = models.TimeSlot(day=date.weekday(), start=time_string, length=length, is_meeting=True).model_dump(by_alias=True, exclude={"id"})
    res = await time_slots_collection.insert_one(time_slot)
    return res.inserted_id


async def try_finish_meeting(meeting: Any):
    """ Checks if the meeting is not yet marked as finished, but already passed.
        Declines invitations for users who didn't accept. Marks the meeting as finished.
    """
    if meeting is None or meeting["is_finished"]:
        return

    now = datetime.datetime.now(datetime.UTC)
    meeting_time = datetime.datetime.fromisoformat(meeting["start"])
    if meeting_time + datetime.timedelta(minutes=meeting["length"]) < now:
        await meetings_collection.find_one_and_update(
            {"_id": meeting["_id"]},
            {"$set": {"is_finished": True}},
            return_document=ReturnDocument.AFTER
        )

        for participant in meeting["participants"]:
            if participant["status"] != models.MeetingStatus.needs_acceptance.value:
                continue
            await meeting_in_user(participant["user_id"], meeting["_id"], models.MeetingStatus.declined.value)
            await participant_in_meeting(participant["user_id"], meeting["_id"], models.MeetingStatus.declined.value)


@app.post("/upload_avatar/{avatar_id}")
async def create_upload_file(file: UploadFile, avatar_id: str):
    path = Path('avatars')
    if not path.exists():
        path.mkdir()

    avatar_bytes = await file.read()
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Filename not set for upload file")
    file_extension = file.filename.split(".")[-1]

    with open(f'avatars/{avatar_id}.{file_extension}', 'wb') as f:
        f.write(avatar_bytes)

    await users_collection.find_one_and_update(
        {"_id": ObjectId(avatar_id)},
        {"$set": {
            "avatar_extension": file_extension
        }}
    )
    await groups_collection.find_one_and_update(
        {"_id": ObjectId(avatar_id)},
        {"$set": {
            "avatar_extension": file_extension
        }}
    )
    return {"ok": True}


@app.get("/users/{user_id}/avatar")
async def get_user_avatar(user_id: str):
    user = await get_user(user_id)
    if "avatar_extension" not in user or not user["avatar_extension"]:
        filepath = "avatars/user.png"
    else:
        filepath = f'avatars/{user_id}.{user["avatar_extension"]}'

    with open(filepath, 'rb') as f:
        avatar_bytes = f.read()
    return Response(content=avatar_bytes, media_type="image/png")


@app.get("/groups/{group_id}/avatar")
async def get_group_avatar(group_id: str):
    group = await get_group(group_id)
    if "avatar_extension" not in group or not group["avatar_extension"]:
        filepath = "avatars/group.png"
    else:
        filepath = f'avatars/{group_id}.{group["avatar_extension"]}'

    with open(filepath, 'rb') as f:
        avatar_bytes = f.read()
    return Response(content=avatar_bytes, media_type="image/png")


@app.websocket("/websocket/{group_id}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, group_id: str, user_id: str):
    await manager.connect(group_id, user_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(group_id, data)
    except WebSocketDisconnect:
        manager.disconnect(group_id, user_id)


async def create_random_coffee_meeting(user_id: str, mate_id: str, group_id: str, title: str, start: str, length: int):
    user_found = await get_user(user_id)

    meeting_dict = schemas.CreateMeeting(
        group_id=group_id,
        title=title,
        description="This event was automatically generated",
        start=start,
        length=length,
    ).model_dump(by_alias=True, exclude={"id"})
    meeting_dict["admin_id"] = str(user_found["_id"])
    meeting_dict["is_finished"] = False
    new_meeting = await meetings_collection.insert_one(meeting_dict)
    created_meeting = await meetings_collection.find_one(
        {"_id": new_meeting.inserted_id}
    )
    if created_meeting is None:
        raise HTTPException(status_code=500, detail="Error creating a meeting")

    created_meeting["participants"] = []
    for _id in [user_id, mate_id]:
        user_found = await get_user(_id)
        if user_found.get("meetings") is None:
            user_found["meetings"] = []
        user_found["meetings"].append(
            {
                "meeting_id": str(created_meeting["_id"]),
                "status": models.MeetingStatus.needs_acceptance.value,
            }
        )
        await users_collection.update_one(
            {"_id": user_found["_id"]}, {"$set": {"meetings": user_found["meetings"]}}
        )

        created_meeting["participants"].append(
            {
                "user_id": str(user_found["_id"]),
                "username": user_found["username"],
                "status": models.MeetingStatus.needs_acceptance.value,
            }
        )
        # notify_single_user(
        #     user_found["fcm_token"],
        #     "Meeting Invitation",
        #     f"Join the meeting {created_meeting['title']} with group {group['name']}, time: {created_meeting['start']}",
        # )

    await meetings_collection.update_one(
        {"_id": created_meeting["_id"]},
        {"$set": {"participants": created_meeting["participants"]}},
    )
    return created_meeting


@app.delete("/groups/{group_id}/users/{user_id}")
async def kick_user(group_id: str, user_id: str):
    user_found = await get_user(user_id)
    group_found = await get_group(group_id)

    group_meeting_ids = set()
    for meeting_card in group_found.get("meetings", []):
        group_meeting_ids.add(meeting_card["_id"])
        meeting = await get_meeting(meeting_card["_id"])

        new_meeting_participants = []
        for participant in meeting.get("participants", []):
            assert type(ObjectId(participant["user_id"])) == type(ObjectId(user_id))
            if ObjectId(participant["user_id"]) != ObjectId(user_id):
                new_meeting_participants.append(participant)
        meeting["participants"] = new_meeting_participants

        await meetings_collection.find_one_and_update(
            {"_id": ObjectId(meeting["_id"])},
            {"$set": meeting},
            return_document=ReturnDocument.AFTER
        )

    new_user_meetings = []
    for meeting in user_found.get("meetings", []):
        if group_meeting_ids:
            assert type(meeting["meeting_id"]) == type(group_meeting_ids.copy().pop())
        if meeting["meeting_id"] not in group_meeting_ids:
            new_user_meetings.append(meeting)
    user_found["meetings"] = new_user_meetings

    new_user_groups = []
    for group in user_found.get("groups", []):
        if not cmp_ids(group["_id"], group_id):
            new_user_groups.append(group)
    user_found["groups"] = new_user_groups

    await users_collection.find_one_and_update(
        {"_id": user_found["_id"]}, {"$set": user_found}
    )

    new_group_users = []
    for user in group_found.get("users", []):
        if not cmp_ids(user["_id"], user_id):
            new_group_users.append(user)
    group_found["users"] = new_group_users

    await groups_collection.find_one_and_update(
        {"_id": group_found["_id"]}, {"$set": group_found}
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def random_coffee(user_id: str):
    INVITE_COOLDOWN_DAYS = 3
    INVITE_IN_COUNT_DAYS = 2

    user_found = await get_user(user_id)
    if not user_found.get('random_coffee') or not user_found['random_coffee']['is_enabled']:
        print(f"Random coffee disabled for user {user_id}")
        return

    if user_found['random_coffee'].get('last_invite_time'):
        last_invite_time = datetime.datetime.fromisoformat(user_found['random_coffee']['last_invite_time'])
        now = datetime.datetime.now(datetime.UTC)
        if (now - last_invite_time).days < INVITE_COOLDOWN_DAYS:
            print(f"Invite cooldown not passed for user {user_id}")
            return

    h, m = map(int, user_found['random_coffee']['start_time'].split(':'))
    # Add a whole day in minutes to support negative timezone offsets
    user_start = 60*h+m + 24*60 + int(user_found['random_coffee']['timezone'])
    h, m = map(int, user_found['random_coffee']['end_time'].split(':'))
    user_end = 60*h+m + 24*60 + int(user_found['random_coffee']['timezone'])

    mates = []
    mate_groups = []
    mate_intervals = []

    for group in user_found["groups"]:
        group_found = await get_group(group["_id"])
        mate_cards = [user for user in group_found["users"] if (user['username'] != user_found['username'])]

        for mate_card in mate_cards:
            mate = await get_user(mate_card["_id"])
            if not mate.get('random_coffee') or not mate['random_coffee']['is_enabled']:
                continue

            if mate['random_coffee'].get('last_invite_time'):
                last_invite_time = datetime.datetime.fromisoformat(mate['random_coffee']['last_invite_time'])
                now = datetime.datetime.now(datetime.UTC)
                if (now - last_invite_time).days < INVITE_COOLDOWN_DAYS:
                    continue

            h, m = map(int, mate['random_coffee']['start_time'].split(':'))
            mate_start = 60*h+m + 24*60 + int(mate['random_coffee']['timezone'])
            h, m = map(int, mate['random_coffee']['end_time'].split(':'))
            mate_end = 60*h+m + 24*60 + int(mate['random_coffee']['timezone'])

            if (mate_start <= user_start < mate_end):
                mates.append(mate)
                mate_groups.append(group)
                mate_intervals.append((user_start - 24*60, min(mate_end, user_end) - user_start))
            elif (mate_start < user_end <= mate_end):
                mates.append(mate)
                mate_groups.append(group)
                mate_intervals.append((mate_start - 24*60, user_end - max(mate_start, user_start)))

    if not mates:
        print(f"No possible matches for user {user_id}")
        return

    index = random.randint(0, len(mates) - 1)
    random_mate = mates[index]

    start, length = mate_intervals[index]
    now = datetime.datetime.now()
    start_date = datetime.datetime(now.year, now.month, now.day + INVITE_IN_COUNT_DAYS, start // 60, start % 60, tzinfo=datetime.UTC)
    meeting = await create_random_coffee_meeting(
        user_id,
        random_mate["_id"],
        mate_groups[index]["_id"],
        "RandomCoffee event",
        start_date.isoformat(),
        length
    )

    # The user that just logged in will see the created event on their meeting page,
    # but the invited user may not be in the app, so we send a push
    notify_single_user(
        random_mate['fcm_token'],
        'RandomCoffee event!',
        f"You matched with {user_found['username']}",
        link=f"coordimate://coordimate.com/meetings/{meeting['_id']}/join"
    )

    await users_collection.find_one_and_update(
        {"_id": user_found["_id"]},
        {
            "$set": {
                "random_coffee.last_invite_time": datetime.datetime.now(datetime.UTC).isoformat() 
            }
        }
    )
    await users_collection.find_one_and_update(
        {"_id": random_mate["_id"]},
        {
            "$set": {
                "random_coffee.last_invite_time": datetime.datetime.now(datetime.UTC).isoformat() 
            }
        }
    )

