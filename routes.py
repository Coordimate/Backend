import os

import motor.motor_asyncio
from fastapi import FastAPI, HTTPException, Body, status, Depends
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pymongo import ReturnDocument#, ObjectId
from dotenv import load_dotenv
from bson import ObjectId

import models
import schemas

import bcrypt
import auth
from auth import JWTBearer


load_dotenv()


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
user_collection = db.get_collection("users")
# FIXME: once login and register are ready, time_slots are stored in user collection, not separately
time_slots_collection = db.get_collection("time_slots")
meetings_collection = db.get_collection("meetings")


# ********** Authentification **********

@app.post(
    "/login",
    response_description="Authentificate a user",
    response_model=schemas.TokenSchema,
    status_code=status.HTTP_200_OK,
    response_model_by_alias=False,
)
async def login(user: schemas.LoginUserSchema = Body(...)):
    print(user)
    # print(user.email)
    if (user_found := await user_collection.find_one({"email":user.email})) is not None:
        user_found["id"] = user_found.pop("_id")
        if bcrypt.checkpw(user.password.encode("utf-8"), user_found["password"]):
            token = auth.generateToken(user_found)
            return token
        else:
            raise HTTPException(status_code=400, detail=f"password incorrect")

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
    response_model=schemas.AccountOut
)
async def me(user: schemas.AuthSchema = Depends(JWTBearer())):
    user_found = await user_collection.find_one({"email": user.email})
    if user_found is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return user_found

# ********** Users **********

@app.post(
    "/register",
    response_description="Add new user",
    response_model=models.UserModel,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def register(user: schemas.CreateUserSchema = Body(...)):
    existing_user = await user_collection.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    user.password = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt())
    new_user = await user_collection.insert_one(
        user.model_dump(by_alias=True, exclude={"id"})
    )
    created_user = await user_collection.find_one({"_id": new_user.inserted_id})
    return created_user

@app.get(
    "/users/",
    response_description="List all users",
    response_model=models.UserCollection,
    response_model_by_alias=False,
)
async def list_users():
    return models.UserCollection(users=await user_collection.find().to_list(1000))

@app.get(
    "/users/{id}",
    response_description="Get a single user",
    response_model=models.UserModel,
    response_model_by_alias=False,
)
async def show_user(id: str):
    if (user := await user_collection.find_one({"_id": ObjectId(id)})) is not None:
        return user

    raise HTTPException(status_code=404, detail=f"user {id} not found")

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

    if len(user_dict) >= 1:
        update_result = await user_collection.find_one_and_update(
            {"_id": ObjectId(id)},
            {"$set": user_dict},
            return_document=ReturnDocument.AFTER,
        )
        if update_result is not None:
            return update_result
        else:
            raise HTTPException(status_code=404, detail=f"user {id} not found")

    if (existing_user := await user_collection.find_one({"_id": id})) is not None:
        return existing_user

    raise HTTPException(status_code=404, detail=f"user {id} not found")


@app.delete(
    "/users/{id}", 
    response_description="Delete a user"
)
async def delete_user(id: str):
    delete_result = await user_collection.delete_one({"_id": ObjectId(id)})

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
async def list_time_slots():
    return schemas.TimeSlotCollection(time_slots=await time_slots_collection.find().to_list(1000))


@app.post(
    "/time_slots/",
    response_description="Add new time slot",
    response_model=models.TimeSlotModel,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_time_slot(time_slot: schemas.CreateTimeSlot = Body(...)):
    new_time_slot = await time_slots_collection.insert_one(
        time_slot.model_dump(by_alias=True, exclude={"id"})
    )
    created_time_slot = await time_slots_collection.find_one({"_id": new_time_slot.inserted_id})
    return created_time_slot


@app.patch(
    "/time_slots/{id}",
    response_description="Update a time slot",
    response_model=models.TimeSlotModel,
    response_model_by_alias=False,
)
async def update_time_slot(id: str, time_slot: schemas.UpdateTimeSlot = Body(...)):
    time_slot_dict = {
        k: v for k, v in time_slot.model_dump(by_alias=True).items() if v is not None
    }

    if len(time_slot_dict) >= 1:
        update_result = await time_slots_collection.find_one_and_update(
            {"_id": ObjectId(id)},
            {"$set": time_slot_dict},
            return_document=ReturnDocument.AFTER,
        )
        if update_result is not None:
            return update_result
        else:
            raise HTTPException(status_code=404, detail=f"time_slot {id} not found")

    if (existing_time_slot := await time_slots_collection.find_one({"_id": id})) is not None:
        return existing_time_slot

    raise HTTPException(status_code=404, detail=f"time_slot {id} not found")


@app.delete(
    "/time_slots/{id}", 
    response_description="Delete a time slot"
)
async def delete_time_slot(id: str):
    delete_result = await time_slots_collection.delete_one({"_id": ObjectId(id)})

    if delete_result.deleted_count == 1:
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
async def create_meeting(meeting: schemas.CreateMeeting = Body(...)):
    new_meeting = await meetings_collection.insert_one(
        meeting.model_dump(by_alias=True, exclude={"id"})
    )
    created_meeting = await meetings_collection.find_one({"_id": new_meeting.inserted_id})
    return created_meeting

@app.get(
    "/meetings/",
    response_description="List all meetings",
    response_model=schemas.MeetingCollection,
    response_model_by_alias=False,
)
async def list_meetings():
    return schemas.MeetingCollection(meetings=await meetings_collection.find().to_list(1000))

@app.get(
    "/meetings/{id}",
    response_description="Get a single meeting",
    response_model=models.MeetingModel,
    response_model_by_alias=False,
)
async def show_meeting(id: str):
    if (meeting := await meetings_collection.find_one({"_id": ObjectId(id)})) is not None:
        return meeting
    
    raise HTTPException(status_code=404, detail=f"meeting {id} not found")

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
        update_result = await meetings_collection.find_one_and_update(
            {"_id": ObjectId(id)},
            {"$set": meeting_dict},
            return_document=ReturnDocument.AFTER,
        )
        if update_result is not None:
            return update_result
        else:
            raise HTTPException(status_code=404, detail=f"meeting {id} not found")

    if (existing_meeting := await meetings_collection.find_one({"_id": id})) is not None:
        return existing_meeting

    raise HTTPException(status_code=404, detail=f"meeting {id} not found")

@app.delete(
    "/meetings/{id}", 
    response_description="Delete a meeting"
)
async def delete_meeting(id: str):
    delete_result = await meetings_collection.delete_one({"_id": ObjectId(id)})

    if delete_result.deleted_count == 1:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(status_code=404, detail=f"meeting {id} not found")