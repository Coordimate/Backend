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


class MeetingTile(BaseModel):
    id: str
    title: str
    start: str
    group_id: str
    status: MeetingStatus


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
    description: Optional[str] = Field(None, description="Description of the meeting")
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


class TimeSlot(BaseModel):
    id: int = Field(..., alias="_id")
    day: int = Field(...)
    start: float = Field(...)
    length: float = Field(...)
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


class UserModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    username: str = Field(...)
    password: Optional[str] = Field(...)  # because google users don't have passwords
    fcm_token: str = Field("no_token")
    email: EmailStr = Field(...)
    meetings: List[MeetingInvite] = Field(
        [], description="List of meetings the user is invited to"
    )
    schedule: List[TimeSlot] = Field(
        [], description="List of busy time slots in the user's schedule"
    )
    groups: List["GroupCardModel"] = Field(
        [], description="List of groups the user belongs to"
    )
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


class GroupCardModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str = Field(...)


class GroupModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    admin: UserCardModel = Field(...)
    name: str = Field(...)
    description: str = Field(...)
    users: List[UserCardModel] = Field(
        [], description="List of users with access to the group"
    )
    meetings: List[MeetingCardModel] = Field(
        [], description="List of meetings of the group"
    )
    schedule: List[TimeSlot] = Field(
        [], description="List of busy time slots in the group's schedule"
    )


class GroupCollection(BaseModel):
    groups: List[GroupModel]


class UpdateGroupModel(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
