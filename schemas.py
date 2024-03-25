from typing import List, Optional

from pydantic import BaseModel, EmailStr

import models


class AuthSchema(BaseModel):
    account_id: int
    is_access_token: bool
    

class LoginSchema(BaseModel):
    email: EmailStr
    password: str


class TokenSchema(BaseModel):
    access_token: str
    refresh_token: str


class RefreshTokenSchema(BaseModel):
    refresh_token: str
    

class AccountIn(BaseModel):
    email: EmailStr
    password: str
    
class AccountOut(BaseModel):
    id_account: int
    email: EmailStr


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

