from typing import List, Optional

from pydantic import BaseModel, EmailStr

import models

# ********* Token Schema *********


class TokenSchema(BaseModel):
    access_token: str
    refresh_token: str


class RefreshTokenSchema(BaseModel):
    refresh_token: str


# ********** Users **********


class NotificationsSchema(BaseModel):
    fcm_token: str


class AuthSchema(BaseModel):
    id: str
    is_access_token: bool


class ChangePasswordSchema(BaseModel):
    old_password: str
    new_password: str


class AccountOut(BaseModel):
    id: str
    email: EmailStr


class CreateUserSchema(BaseModel):
    username: str
    password: Optional[str] = None
    email: EmailStr
    auth_type: Optional[str] = None


class LoginUserSchema(BaseModel):
    email: EmailStr
    password: Optional[str] = None
    auth_type: Optional[str] = None


# ********** Time Slot Schema **********


class TimeSlotCollection(BaseModel):
    time_slots: List[models.TimeSlot]


class CreateTimeSlot(BaseModel):
    is_meeting: Optional[bool] = False
    day: int
    start: float
    length: float


class UpdateTimeSlot(BaseModel):
    is_meeting: Optional[bool] = False
    day: Optional[int] = None
    start: Optional[float] = None
    length: Optional[float] = None


class ShareScheduleResponse(BaseModel):
    schedule_link: str


# ********** Meeting Schema **********


class MeetingCollection(BaseModel):
    meetings: List[models.MeetingModel]


class CreateMeeting(BaseModel):
    group_id: str
    title: str
    start: str
    length: Optional[int] = 60
    description: Optional[str] = None
    meeting_link: Optional[str] = None
    google_event_id: Optional[str] = None


class UpdateMeeting(BaseModel):
    admin_id: Optional[str] = None
    group_id: Optional[str] = None
    is_finished: Optional[bool] = None
    title: Optional[str] = None
    start: Optional[str] = None
    length: Optional[int] = None
    description: Optional[str] = None
    summary: Optional[str] = None


class UpdateMeetingStatus(BaseModel):
    status: models.MeetingStatus


class MeetingTileCollection(BaseModel):
    meetings: List[models.MeetingTile]


class MeetingCardCollection(BaseModel):
    meetings: List[models.MeetingCardModel]


class ParticipantSchema(BaseModel):
    user_id: str
    user_username: str
    status: str
    # TODO: add photo


class MeetingDetails(BaseModel):
    id: str
    title: str
    start: str
    length: int
    is_finished: bool
    description: str
    summary: str
    group_id: str
    group_name: str
    admin: ParticipantSchema
    participants: List[ParticipantSchema]
    meeting_link: Optional[str]
    google_event_id: Optional[str]
    status: str


class UpdateParticipantStatus(BaseModel):
    status: str
    user_id: str


class AddParticipantSchema(BaseModel):
    id: str


class ParticipantInviteSchema(BaseModel):
    meeting_id: str
    user_id: str
    status: str


# ********** Agenda Schema **********


class AgendaPointCollection(BaseModel):
    agenda: List[models.AgendaPoint]


class CreateAgendaPoint(BaseModel):
    text: str
    level: int


# ********** Groups **********


class CreateGroupSchema(BaseModel):
    name: str
    description: str


class GroupInviteResponse(BaseModel):
    join_link: str
