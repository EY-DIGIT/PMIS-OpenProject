from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from .models.user import User, UserStatus
from .services.user_service import (
    UserCreateService,
    UserUpdateService,
    UserLoginService,
    UserLogoutService,
    UserChangePasswordService,
    UserDeleteService,
    UserRegisterService,
)
from .repository import repository


app = FastAPI(title="User Service API")


class PreferencesModel(BaseModel):
    timezone: Optional[str] = None
    theme: Optional[str] = None


class UserCreateRequest(BaseModel):
    login: Optional[str] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    mail: Optional[str] = None
    password: Optional[str] = None
    status: Optional[str] = None
    preferences: Optional[PreferencesModel] = None


class LoginRequest(BaseModel):
    login: str
    password: str
    autologin: Optional[bool] = False


class ChangePasswordRequest(BaseModel):
    current_password: Optional[str]
    new_password: str
    new_password_confirmation: str


def _map_status(status_str: Optional[str]):
    if not status_str:
        return None
    try:
        return UserStatus[status_str.upper()]
    except Exception:
        return None


@app.post('/users', status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreateRequest):
    params: Dict[str, Any] = payload.dict(exclude_none=True)
    # Map preferences nested model to dict
    if 'preferences' in params and params['preferences'] is not None:
        params['preferences'] = params['preferences']

    # Map status
    if 'status' in params:
        mapped = _map_status(params.get('status'))
        if mapped:
            params['status'] = mapped
        else:
            params.pop('status', None)

    service = UserCreateService()
    result = service.call(params)
    if result.is_failure():
        raise HTTPException(status_code=400, detail={'message': result.message, 'errors': result.errors})

    user: User = result.result
    repository.add(user)
    return {'message': result.message, 'user': user.to_dict()}


@app.get('/users/{user_id}')
def get_user(user_id: int):
    user = repository.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return user.to_dict()


@app.put('/users/{user_id}')
def update_user(user_id: int, payload: UserCreateRequest):
    user = repository.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')

    params = payload.dict(exclude_none=True)
    if 'status' in params:
        mapped = _map_status(params.get('status'))
        if mapped:
            params['status'] = mapped
        else:
            params.pop('status', None)

    service = UserUpdateService(model=user)
    result = service.call(params)
    if result.is_failure():
        raise HTTPException(status_code=400, detail={'message': result.message, 'errors': result.errors})

    repository.update(result.result)
    return {'message': result.message, 'user': result.result.to_dict()}


@app.post('/login')
def login(payload: LoginRequest):
    # find user via repository
    user = repository.find_by_login_or_email(payload.login)
    if not user:
        raise HTTPException(status_code=401, detail='Invalid credentials')

    authenticated = User.try_to_login(payload.login, payload.password, user_repository=repository)
    if not authenticated:
        raise HTTPException(status_code=401, detail='Invalid credentials')

    login_service = UserLoginService(authenticated)
    result = login_service.call(autologin=payload.autologin)
    if result.is_failure():
        raise HTTPException(status_code=500, detail={'message': result.message})

    # persist updated user state (e.g., last_login_on)
    repository.update(authenticated)

    return {'message': result.message, 'user': authenticated.to_dict(), 'session': login_service.get_session_data()}


@app.post('/users/{user_id}/logout')
def logout(user_id: int):
    user = repository.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')

    service = UserLogoutService(user, session_data={})
    result = service.call()
    return {'message': result.message}


@app.post('/users/{user_id}/change_password')
def change_password(user_id: int, payload: ChangePasswordRequest):
    user = repository.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')

    service = UserChangePasswordService(user)
    result = service.call(payload.current_password, payload.new_password, payload.new_password_confirmation)
    if result.is_failure():
        raise HTTPException(status_code=400, detail={'message': result.message, 'errors': result.errors})

    repository.update(user)
    return {'message': result.message, 'user': user.to_dict()}


@app.delete('/users/{user_id}')
def delete_user(user_id: int):
    user = repository.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')

    service = UserDeleteService(model=user)
    result = service.destroy()
    if result.is_failure():
        raise HTTPException(status_code=400, detail={'message': result.message, 'errors': result.errors})

    # update repository record
    repository.update(result.result)
    return {'message': result.message, 'user': result.result.to_dict()}


@app.post('/register')
def register(payload: UserCreateRequest):
    params: Dict[str, Any] = payload.dict(exclude_none=True)
    service = UserRegisterService()
    result = service.call(params)
    if result.is_failure():
        raise HTTPException(status_code=400, detail={'message': result.message, 'errors': result.errors})

    user = result.result
    repository.add(user)
    return {'message': result.message, 'user': user.to_dict()}
