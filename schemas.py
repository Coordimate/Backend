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

# class LoginSchema(BaseModel):
#     email: EmailStr
#     password: str
    

# class AccountIn(BaseModel):
#     email: EmailStr
#     password: str
    
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


# ********** Token Schema **********

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

