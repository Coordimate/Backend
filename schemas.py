from pydantic import BaseModel, EmailStr

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