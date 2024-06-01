import os

import motor.motor_asyncio
from fastapi import FastAPI, HTTPException, Body, status, Depends
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


load_dotenv()


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


# ********** Authentification **********


@app.post(
    "/login",
    response_description="Authentificate a user",
    response_model=schemas.TokenSchema,
    status_code=status.HTTP_200_OK,
    response_model_by_alias=False,
)
async def login(user: schemas.LoginUserSchema = Body(...)):
    if (
        user_found := await users_collection.find_one({"email": user.email})
    ) is not None:
        user_found["id"] = user_found.pop("_id")
        if user.auth_type is None:
            if user_found.get("password") is None:
                raise HTTPException(
                    status_code=409, detail=f"user regisered through external service"
                )
            if user.password is not None:
                if bcrypt.checkpw(
                    user.password.encode("utf-8"), user_found["password"]
                ):
                    token = auth.generateToken(user_found)
                    return token
                else:
                    raise HTTPException(status_code=400, detail=f"password incorrect")
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"No password specified, our Google/Facebook Auth got us",
                )
        else:
            token = auth.generateToken(user_found)
            return token

    raise HTTPException(status_code=404, detail=f"user {user.email} not found")


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
    if user.auth_type is None:
        if user.password is not None:
            user.password = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt())
        else:
            raise HTTPException(
                status_code=400,
                detail=f"No password specified, our Google/Facebook Auth got us",
            )
    new_user = await users_collection.insert_one(
        user.model_dump(by_alias=True, exclude={"id"})
    )
    created_user = await users_collection.find_one({"_id": new_user.inserted_id})
    return created_user


@app.get(
    "/users/",
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
    return user


@app.put(
    "/users/{id}",
    response_description="Update a user",
    response_model=models.UserModel,
    response_model_by_alias=False,
)
async def update_user(id: str, user: models.UpdateUserModel = Body(...)):
    user_dict = {
        k: v for k, v in user.model_dump(by_alias=True).items() if v is not None
    }
    if "password" in user_dict:
        user_dict["password"] = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt())

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
    return existing_user


@app.delete("/users/{id}", response_description="Delete a user")
async def delete_user(id: str):
    user = await get_user(id)
    user_meetings = user.get("meetings", [])
    for meeting in user_meetings:
        for participant in meeting.get("participants", []):
            delete_res = await meetings_collection.update_one(
                {"_id": ObjectId(meeting["meeting_id"])},
                {"$pull": {"participants": {"user_id": participant["user_id"]}}},
            )
            print(delete_res.modified_count)
    delete_result = await users_collection.delete_one({"_id": ObjectId(id)})
    if delete_result.deleted_count == 1:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(status_code=404, detail=f"user {id} not found")


# ********** Time Slots **********


@app.get(
    "/time_slots/",
    response_description="List all time slots",
    response_model=schemas.TimeSlotCollection,
    response_model_by_alias=False,
)
async def list_time_slots(user: schemas.AuthSchema = Depends(JWTBearer())):
    user_found = await get_user(user.id)
    schedule = user_found.get("schedule")
    if schedule is None:
        return schemas.TimeSlotCollection(time_slots=[])
    return schemas.TimeSlotCollection(time_slots=schedule)


@app.post(
    "/time_slots/",
    response_description="Add new time slot",
    response_model=models.TimeSlot,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_time_slot(
    time_slot: schemas.CreateTimeSlot = Body(...),
    user: schemas.AuthSchema = Depends(JWTBearer()),
):
    user_found = await get_user(user.id)
    if not user_found.get("schedule"):
        user_found["schedule"] = []
        new_id = -1
    else:
        new_id = user_found["schedule"][-1]["_id"]

    new_time_slot = time_slot.model_dump(by_alias=True)
    new_time_slot["_id"] = new_id + 1
    user_found["schedule"].append(new_time_slot)

    await users_collection.update_one(
        {"_id": user_found["_id"]}, {"$set": {"schedule": user_found["schedule"]}}
    )
    return new_time_slot


@app.patch(
    "/time_slots/{slot_id}",
    response_description="Update a time slot",
    response_model=models.TimeSlot,
    response_model_by_alias=False,
)
async def update_time_slot(
    slot_id: int,
    time_slot: schemas.UpdateTimeSlot = Body(...),
    user: schemas.AuthSchema = Depends(JWTBearer()),
):
    user_found = await get_user(user.id)
    time_slot_dict = {
        k: v for k, v in time_slot.model_dump(by_alias=True).items() if v is not None
    }
    schedule = user_found["schedule"]
    for i in range(len(schedule)):
        if schedule[i]["_id"] == slot_id:
            schedule[i].update(time_slot_dict)
            break

    update_result = await users_collection.update_one(
        {"_id": ObjectId(user_found["_id"])}, {"$set": {"schedule": schedule}}
    )
    if update_result.modified_count != 1:
        raise HTTPException(status_code=404, detail=f"time_slot {slot_id} not found")

    user_found = await get_user(user.id)
    for i in range(len(schedule)):
        if schedule[i]["_id"] == slot_id:
            return schedule[i]


@app.delete("/time_slots/{slot_id}", response_description="Delete a time slot")
async def delete_time_slot(
    slot_id: int, user: schemas.AuthSchema = Depends(JWTBearer())
):
    user_found = await get_user(user.id)

    delete_result = await users_collection.update_one(
        {"_id": ObjectId(user_found["_id"])}, {"$pull": {"schedule": {"_id": slot_id}}}
    )
    if delete_result.modified_count == 1:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(status_code=404, detail=f"time_slot {id} not found")


# ********** Meetings **********


@app.post(
    "/meetings/",
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
    return schemas.MeetingCollection(
        meetings=await meetings_collection.find().to_list(1000)
    )


@app.get(
    "/meetings/",
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
            meeting_tile = models.MeetingTile(
                id=str(meeting["_id"]),
                title=meeting["title"],
                start=meeting["start"],
                group_id=str(
                    meeting["group_id"]
                ),  # Assuming group_id is stored as ObjectId
                status=invite["status"],
            )
            meetings.append(meeting_tile)

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
    # meeting = MeetingModel
    meeting_participants = meeting.get("participants", [])
    participants = []
    # meeting_participants = List[Participant]
    for meeting_participant in meeting_participants:
        # meeting_participant = Participant
        participant_user = await get_user(str(meeting_participant["user_id"]))
        # participant_user = UserModel
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
                group_id=str(group["_id"]),
                group_name=group["name"],
                admin=admin,
                description=meeting["description"],
                participants=participants,
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
    # user here is the admin
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
        group = await get_group(meeting_dict["group_id"])
        for i, m in enumerate(group["meetings"]):
            if m["_id"] == id:
                m.update(meeting_dict)
                group["meetings"][i] = m
                break
        await groups_collection.find_one_and_update(
            {"_id": group["_id"]}, {"$set": group}
        )

        meeting_found = await get_meeting(id)
        updated_meeting = meeting_found.copy()
        updated_meeting.update(meeting_dict)
        for u in meeting_found["participants"]:
            user = await get_user(u["user_id"])
            meetings = []
            for i, m in enumerate(user["meetings"]):
                if m["_id"] != id:
                    m.update(meeting_dict)
                    user["meetings"][i] = m
                    break
            user["meetings"] = meetings
            await users_collection.find_one_and_update(
                {"_id": user["_id"]}, {"$set": user}
            )
            notify_single_user(
                user["fcm_token"],
                "Meeting Update",
                f"The meeting {updated_meeting['title']} with group {group['name']}, time: {updated_meeting['start']}, just got updated.",
            )

        update_result = await meetings_collection.find_one_and_update(
            {"_id": ObjectId(id)},
            {"$set": meeting_dict},
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
        if m["id"] != id:
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

    if delete_result.deleted_count == 1:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(status_code=404, detail=f"meeting {id} not found")


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
    "/groups/",
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

    new_group = await groups_collection.insert_one(group_dict)
    created_group = await groups_collection.find_one({"_id": new_group.inserted_id})

    group_card = get_group_card(created_group)
    if "groups" not in user_found:
        user_found["groups"] = []
    user_found["groups"].append(group_card)

    await users_collection.update_one({"_id": user_found["_id"]}, {"$set": user_found})
    return created_group


@app.get(
    "/groups/",
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
        return group

    raise HTTPException(status_code=404, detail=f"group {id} not found")


@app.put(
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
        meetings_ids_to_delete = [ObjectId(m["_id"]) for m in group["meetings"]]
        # TODO: when deleting a meeting it should be removed from all users (invitations)
        await meetings_collection.delete_many({"_id": {"$in": meetings_ids_to_delete}})

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


@app.get(
    "/groups/{id}/invite",
    response_description="Get a link to invite user to a group",
    response_model=schemas.GroupInviteResponse,
    response_model_by_alias=False,
)
async def group_invite(id: str, user: schemas.AuthSchema = Depends(JWTBearer())):
    _ = await get_user(user.id)
    _ = await get_group(id)

    link = f"coordimate://coordimate.com/groups/join/{id}"
    return schemas.GroupInviteResponse(join_link=link)


@app.post(
    "/groups/{id}/join",
    response_description="Join a group using the invite link",
)
async def group_join(id: str, user: schemas.AuthSchema = Depends(JWTBearer())):
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

    await users_collection.find_one_and_update(
        {"_id": user_found["_id"]}, {"$set": user_found}
    )
    await groups_collection.find_one_and_update(
        {"_id": group_found["_id"]}, {"$set": group_found}
    )

    return {"result": "ok"}


@app.get(
    "/groups/{id}/meetings",
    response_description="List all meetings of the group",
    response_model=schemas.MeetingCardCollection,
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
        meeting_found = await get_meeting(meeting["_id"])
        meeting_tile = models.MeetingCardModel(
            _id=str(meeting_found["_id"]),
            title=meeting_found["title"],
            start=meeting_found["start"],
        )
        response_meetings.append(meeting_tile)

    return schemas.MeetingCardCollection(meetings=response_meetings)


# ********** Share Schedule ***********


@app.get(
    "/share_schedule",
    response_description="Get link to share personal schedule",
    response_model=schemas.ShareScheduleResponse,
    response_model_by_alias=False,
)
async def share_personal_schedule(id, user: schemas.AuthSchema = Depends(JWTBearer())):
    _ = await get_user(user.id)
    link = f"coordimate://coordimate.com/users/{id}/schedule"
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
    schedule = other_user.get("schedule", [])
    return schemas.TimeSlotCollection(time_slots=schedule)


# ********** Utils **********


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
        _id=str(meeting["_id"]), title=meeting["title"], start=meeting["start"]
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
