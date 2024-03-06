import os

import motor.motor_asyncio
from fastapi import FastAPI, HTTPException, Body, status
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pymongo import ReturnDocument
from dotenv import load_dotenv
from bson import ObjectId

import models


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
student_collection = db.get_collection("students")


@app.post(
    "/students/",
    response_description="Add new student",
    response_model=models.StudentModel,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_student(student: models.StudentModel = Body(...)):
    new_student = await student_collection.insert_one(
        student.model_dump(by_alias=True, exclude={"id"})
    )
    created_student = await student_collection.find_one(
        {"_id": new_student.inserted_id}
    )
    return created_student


@app.get(
    "/students/",
    response_description="List all students",
    response_model=models.StudentCollection,
    response_model_by_alias=False,
)
async def list_students():
    return models.StudentCollection(students=await student_collection.find().to_list(1000))


@app.get(
    "/students/{id}",
    response_description="Get a single student",
    response_model=models.StudentModel,
    response_model_by_alias=False,
)
async def show_student(id: str):
    if (
        student := await student_collection.find_one({"_id": ObjectId(id)})
    ) is not None:
        return student

    raise HTTPException(status_code=404, detail=f"Student {id} not found")


@app.put(
    "/students/{id}",
    response_description="Update a student",
    response_model=models.StudentModel,
    response_model_by_alias=False,
)
async def update_student(id: str, student: models.UpdateStudentModel = Body(...)):
    student_dict = {
        k: v for k, v in student.model_dump(by_alias=True).items() if v is not None
    }

    if len(student_dict) >= 1:
        update_result = await student_collection.find_one_and_update(
            {"_id": ObjectId(id)},
            {"$set": student_dict},
            return_document=ReturnDocument.AFTER,
        )
        if update_result is not None:
            return update_result
        else:
            raise HTTPException(status_code=404, detail=f"Student {id} not found")

    if (existing_student := await student_collection.find_one({"_id": id})) is not None:
        return existing_student

    raise HTTPException(status_code=404, detail=f"Student {id} not found")


@app.delete("/students/{id}", response_description="Delete a student")
async def delete_student(id: str):
    delete_result = await student_collection.delete_one({"_id": ObjectId(id)})

    if delete_result.deleted_count == 1:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise HTTPException(status_code=404, detail=f"Student {id} not found")

