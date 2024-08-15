import os
import time
from typing import Type

import jwt
import bcrypt
from dotenv import load_dotenv
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import models
import schemas


load_dotenv()

JWT_VALID_TIME_ACCESS = int(os.environ["JWT_VALID_TIME_ACCESS"])
JWT_VALID_TIME_REFRESH = int(os.environ["JWT_VALID_TIME_REFRESH"])
JWT_VALID_TIME_PWD_RESET = int(os.environ["JWT_VALID_TIME_PWD_RESET"])
JWT_VALID_TIME_ACTIVATE_ACCOUNT = int(os.environ["JWT_VALID_TIME_ACTIVATE_ACCOUNT"])
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = os.environ["JWT_ALGORITHM"]


class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        self.auto_error = auto_error
        super(JWTBearer, self).__init__(auto_error=auto_error)

    async def __call__(self, request: Request):
        credentials: HTTPAuthorizationCredentials | None = await super(
            JWTBearer, self
        ).__call__(request)
        if credentials:
            if not credentials.scheme == "Bearer":
                raise HTTPException(
                    status_code=403, detail="Invalid authentication scheme."
                )
            token = decodeJWT(credentials.credentials)
            if token == None:
                raise HTTPException(
                    status_code=403, detail="Invalid token or expired token."
                )
            if token.is_access_token != True:
                raise HTTPException(
                    status_code=403, detail="Invalid token or expired token."
                )
            return token
        elif not self.auto_error:
            return None
        else:
            raise HTTPException(status_code=403, detail="Invalid authorization code.")


def createToken(id: str, valid_time: int, is_access_token: bool):
    payload = {
        "id": id,
        "is_access_token": is_access_token,
        "expires": time.time() + valid_time,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def decodeJWT(token: str) -> Type[schemas.AuthSchema] | None:
    try:
        decoded_token = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if decoded_token["expires"] < time.time():
            return None
        ret = schemas.AuthSchema
        ret.id = decoded_token["id"]
        ret.is_access_token = decoded_token["is_access_token"]
        return ret
    except:
        return None


def generateToken(account: schemas.AccountOut):
    reponse = schemas.TokenSchema
    reponse.access_token = createToken(
        id=str(account.id),
        valid_time=JWT_VALID_TIME_ACCESS,
        is_access_token=True,
    )
    reponse.refresh_token = createToken(
        id=str(account.id),
        valid_time=JWT_VALID_TIME_REFRESH,
        is_access_token=False,
    )
    return reponse


def generate_refresh_token(old_token: str, decoded_token: Type[schemas.AuthSchema]):
    reponse = schemas.TokenSchema
    reponse.access_token = createToken(
        id=decoded_token.id,
        valid_time=JWT_VALID_TIME_ACCESS,
        is_access_token=True,
    )
    reponse.refresh_token = old_token
    return reponse
