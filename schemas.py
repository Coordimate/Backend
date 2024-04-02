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

class AuthSchema(BaseModel):
    id: str
    is_access_token: bool
    
class AccountOut(BaseModel):
    id: str
    email: EmailStr
    
class CreateUserSchema(BaseModel):
    username: str
    password: str
    email: EmailStr
    
class LoginUserSchema(BaseModel):
    email: EmailStr
    password: str

# ********** Time Slot Schema **********

class TimeSlotCollection(BaseModel):
    time_slots: List[models.TimeSlotModel]


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


# ********** Meeting Schema **********

class MeetingCollection(BaseModel):
    meetings: List[models.MeetingModel]

class CreateMeeting(BaseModel):
    admin_id: Optional[str] = None
    group_id: str
    title: str
    start: str
    description: Optional[str] = None
    needs_acceptance: bool = True
    is_accepted: bool = False
    
class UpdateMeeting(BaseModel):
    admin_id: Optional[str] = None
    group_id: Optional[str] = None
    title: Optional[str] = None
    start: Optional[str] = None
    description: Optional[str] = None
    needs_acceptance: Optional[bool] = None
    is_accepted: Optional[bool] = None
    
class MeetingTile(BaseModel):
    id: str
    title: str
    start: str
    group_id: str
    status: str
    
class MeetingTileCollection(BaseModel):
    meetings: List[MeetingTile]