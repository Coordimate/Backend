from typing import Optional, List
from typing_extensions import Annotated

from pydantic import ConfigDict, BaseModel, Field, EmailStr
from pydantic.functional_validators import BeforeValidator
# from pymongo.objectid import ObjectId
from bson import ObjectId
from enum import Enum

PyObjectId = Annotated[str, BeforeValidator(str)]

class MeetingStatus(str, Enum):
    accepted = "accepted"
    declined = "declined"
    needs_acceptance = "needs acceptance"

class Participant(BaseModel): #TODO: user_id as PyObjectId
    user_id: PyObjectId = Field(..., description="ID of the user")
    status: MeetingStatus = Field(..., description="Status of the user for the meeting (accepted / needs acceptance / declined)")

class MeetingModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    group_id: PyObjectId = Field(..., description="ID of the group associated with the meeting")
    admin_id: PyObjectId = Field(..., description="ID of the user who created the meeting")
    title: str = Field(..., description="Title of the meeting")
    start: str = Field(..., description="Start date and time of the meeting")
    description: Optional[str] = Field(None, description="Description of the meeting")
    participants: List[Participant] = Field([], description="List of participants in the meeting")
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "admin_id": "12345",
            "group_id": "12345",
            "title": "first group meeting",
            "start": "2022-01-01T12:00:00",
            "description": "This is the first group meeting."
        },
    )


class TimeSlot(BaseModel):
    id: int = Field(..., alias="_id") #Optional[PyObjectId] = Field(alias="_id", default=None)
    day: int = Field(...)
    start: float = Field(...)
    length: float = Field(...)
    
class MeetingInvite(BaseModel):
    meeting_id: PyObjectId = Field(..., description="ID of the meeting")
    status: MeetingStatus = Field(..., description="Status of the user for the meeting (accepted / needs acceptance / declined)")

class UserModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    username: str = Field(...)
    password: str = Field(...)
    email: EmailStr = Field(...)
    meetings: List[MeetingInvite] = Field([], description="List of meetings the user is invited to")
    schedule: List[TimeSlot] = Field([], description="List of busy time slots in the user's schedule")
    # schedule_link: str = Field(...)
    # allow_location_link: bool = Field(...)
    # model_config = ConfigDict(
    #     arbitrary_types_allowed=True,
    #     json_encoders={ObjectId: str},
    #     json_schema_extra={
    #         "username": "casual_meeter",
    #         "email": "meeter@gmail.com",
    #         "password": "iLikeMeetingUp",
    #         "schedule_link": "https://coordimate.com/schedules/john_doe",
    #         "allow_location_access": False,
    #         "groups": [
    #             {
    #                 "name": "kittens",
    #                 "notify_chat": True,
    #                 "notify_polls": True,
    #                 "notify_meetings": True,
    #                 "notify_changes": True,
    #                 "is_admin": False,
    #             }
    #         ],
    #         "external_calendars": [
    #             {
    #                 "name": "my uni calendar",
    #                 "type": "Outlook",
    #                 "link": "https://outlook.office365.com/owa/calendar/blah-blah",
    #             }
    #         ],
    #         "meetings": [
    #             {"name": "first group meeting", "accepted": False, "refused": False}
    #         ],
    #         "meeting_constraints": [
    #             {
    #                 "type": "before_time",
    #                 "hours": "18",
    #                 "minutes": "00",
    #                 "timezone": "UTC+3",
    #             },
    #             {"type": "not_on_weekends", "value": True},
    #         ],
    #         "schedule": [{"is_meeting": False, "day": 1, "start": 9.0, "length": 2.5}],
    #     },
    # )


class UpdateUserModel(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    # model_config = ConfigDict(
    #     arbitrary_types_allowed=True,
    #     json_encoders={ObjectId: str},
    #     json_schema_extra={
    #         "username": "casual_meeter",
    #         "email": "meeter@gmail.com",
    #         "password": "iLikeMeetingUp",
    #         "schedule_link": "https://coordimate.com/schedules/john_doe",
    #         "allow_location_access": False,
    #         "groups": [
    #             {
    #                 "name": "kittens",
    #                 "notify_chat": True,
    #                 "notify_polls": True,
    #                 "notify_meetings": True,
    #                 "notify_changes": True,
    #                 "is_admin": False,
    #             }
    #         ],
    #         "external_calendars": [
    #             {
    #                 "name": "my uni calendar",
    #                 "type": "Outlook",
    #                 "link": "https://outlook.office365.com/owa/calendar/blah-blah",
    #             }
    #         ],
    #         "meetings": [
    #             {"name": "first group meeting", "accepted": False, "refused": False}
    #         ],
    #         "meeting_constraints": [
    #             {
    #                 "type": "before_time",
    #                 "hours": "18",
    #                 "minutes": "00",
    #                 "timezone": "UTC+3",
    #             },
    #             {"type": "not_on_weekends", "value": True},
    #         ],
    #         "schedule": [{"is_meeting": False, "day": 1, "start": 9.0, "length": 2.5}],
    #     },
    # )


class UserCollection(BaseModel):
    users: List[UserModel]


class GroupModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str = Field(...)
    description: str = Field(...)

#to list groups for each particular user. needs more by working with user ID's
class GroupCollection(BaseModel):
    groups: List[GroupModel]

class UpdateGroupModel(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None