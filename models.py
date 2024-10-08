from typing import Any, Optional, List
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


class MeetingTile(BaseModel):
    id: str
    title: str
    start: str
    length: int  # Length of the meeting in minutes
    group: "GroupCardModel"
    status: MeetingStatus
    is_finished: Optional[bool] = None


class Participant(BaseModel):  # TODO: user_id as PyObjectId
    user_id: PyObjectId = Field(..., description="ID of the user")
    username: str
    status: MeetingStatus = Field(
        ...,
        description="Status of the user for the meeting (accepted / needs acceptance / declined)",
    )


class AgendaPoint(BaseModel):
    text: str = Field(...)
    level: int = Field(
        ..., description="Level of indentation of the agenda point in the list"
    )


class MeetingCardModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    title: str = Field(...)
    start: str = Field(...)
    length: int = Field(...)


class MeetingModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    group_id: PyObjectId = Field(
        ..., description="ID of the group associated with the meeting"
    )
    admin_id: PyObjectId = Field(
        ..., description="ID of the user who created the meeting"
    )
    is_finished: bool = Field(False, description="Marks the meeting as compeleted")
    title: str = Field(..., description="Title of the meeting")
    start: str = Field(..., description="Start date and time of the meeting")
    length: int = Field(default=60, description="Length of the meeting in minutes")
    time_slot_id: Optional[PyObjectId] = Field(...)
    description: Optional[str] = Field(None, description="Description of the meeting")
    summary: Optional[str] = Field("", description="Summary of a finished meeting")
    participants: List[Participant] = Field(
        [], description="List of participants in the meeting"
    )
    agenda: List[AgendaPoint] = Field(
        [], description="List of text points - agenda for the meeting"
    )
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "admin_id": "12345",
            "group_id": "12345",
            "title": "first group meeting",
            "start": "2022-01-01T12:00:00",
            "description": "This is the first group meeting.",
        },
    )
    google_event_id: Optional[str] = Field(None, description="Google Calendar Event Id")
    meeting_link: Optional[str] = Field(None, description="Online meeting room link")


class TimeSlot(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    day: int = Field(...)
    start: str = Field(..., description="Start date and time of the timeSlot" )
    length: int = Field(..., description="Duration of the timeSlot in minutes")
    is_meeting: bool = Field(False)


class MeetingInvite(BaseModel):
    meeting_id: PyObjectId = Field(..., description="ID of the meeting")
    status: MeetingStatus = Field(
        ...,
        description="Status of the user for the meeting (accepted / needs acceptance / declined)",
    )


class UserCardModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    username: str = Field(...)


class RandomCoffee(BaseModel):
    is_enabled: bool = Field(default=False)
    start_time: Optional[str] = Field(..., description="Start of the open to participation interval of the user")
    end_time: Optional[str] = Field(..., description="End of the open to participation interval of the user")
    timezone: Optional[str] = Field(..., description="TimeZone offset of the user in minutes")
    last_invite_time: Optional[str] = Field(default=None, description="UTC string with datetime of the last invitation the user received")


class UserModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    username: str = Field(...)
    password: Optional[str] = Field(default=None)  # because google users don't have passwords
    fcm_token: str = Field("no_token")
    email: EmailStr = Field(...)
    avatar_extension: Optional[str] = Field(default=None)
    meetings: List[MeetingInvite] = Field(
        [], description="List of meetings the user is invited to"
    )
    schedule: List[PyObjectId] = Field(
        [], description="List of busy time slots in the user's schedule"
    )
    groups: List["GroupCardModel"] = Field(
        [], description="List of groups the user belongs to"
    )
    last_location: Optional[str] = Field(default=None, description="Last location of the user")
    random_coffee: Optional[RandomCoffee] = Field(default=None)


class UpdateUserModel(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    last_location: Optional[str] = None
    random_coffee: Optional[RandomCoffee] = None


class UserCollection(BaseModel):
    users: List[UserModel]


class GroupCardModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str = Field(...)


class GroupPoll(BaseModel):
    question: str = Field(...)
    options: List[str] = Field(default=[])
    votes: Optional[Any] = Field(default=None)


class GroupModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    admin: UserCardModel = Field(...)
    name: str = Field(...)
    description: str = Field(...)
    avatar_extension: Optional[str] = Field(default=None)
    users: List[UserCardModel] = Field(
        [], description="List of users with access to the group"
    )
    meetings: List[MeetingCardModel] = Field(
        [], description="List of meetings of the group"
    )
    schedule: List[PyObjectId] = Field(
        [], description="List of busy time slots in the group's schedule"
    )
    chat_messages: str = Field(default='[]')
    poll: Optional[GroupPoll] = Field(default=None)
    meeting_link: Optional[str] = Field(default=None)


class GroupCollection(BaseModel):
    groups: List[GroupModel]


class UpdateGroupModel(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    poll: Optional[GroupPoll] = None
    meeting_link: Optional[str] = None

