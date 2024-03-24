from typing import Optional, List
from typing_extensions import Annotated

from pydantic import ConfigDict, BaseModel, Field, EmailStr
from pydantic.functional_validators import BeforeValidator
from bson import ObjectId


PyObjectId = Annotated[str, BeforeValidator(str)]

class CreateUserModel(BaseModel):
    username: str = Field(...)
    password: str = Field(...)
    email: EmailStr = Field(...)
    
class LoginUserModel(BaseModel):
    email: EmailStr = Field(...)
    password: str = Field(...)

class UserModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    username: str = Field(...)
    password: str = Field(...)
    email: EmailStr = Field(...)
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
