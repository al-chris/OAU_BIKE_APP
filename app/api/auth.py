from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import select
from jose import JWTError, jwt
from datetime import datetime, timezone, timedelta
from typing import Optional, Any
import secrets

from app.database import SessionDep
from app.models.user import UserSession, UserSessionCreate, UserSessionRead, UserRole
from app.config import settings

router = APIRouter()
security = HTTPBearer()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def get_current_session(
    db: SessionDep,
    credentials: HTTPAuthorizationCredentials = Depends(security)    
) -> UserSession:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        session_token = payload.get("session_token")
        if session_token is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Get session from database
    result = await db.execute(select(UserSession).where(UserSession.session_token == session_token))
    session = result.scalar_one_or_none()
    
    if session is None:
        raise credentials_exception
    
    # Check if session is expired
    if session.is_expired():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired"
        )
    
    # Update last seen
    session.last_seen = datetime.now(timezone.utc)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    return session

class SessionRequest(UserSessionCreate):
    pass

class SessionResponse(UserSessionRead):
    access_token: str
    token_type: str = "bearer"

@router.post("/create-session", response_model=SessionResponse)
async def create_session(
    session_request: SessionRequest,
    db: SessionDep
):
    # Generate unique session token
    session_token = secrets.token_urlsafe(32)
    
    # Create session
    session = UserSession(
        session_token=session_token,
        role=session_request.role,
        emergency_contact=session_request.emergency_contact
    )
    
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    # Create JWT token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"session_token": session_token},
        expires_delta=access_token_expires
    )
    
    return SessionResponse(
        **session.model_dump(),
        access_token=access_token,
        token_type="bearer"
    )

@router.get("/me", response_model=UserSessionRead)
async def get_current_user_session(
    current_session: UserSession = Depends(get_current_session)
):
    return current_session

@router.post("/switch-role")
async def switch_role(
    db: SessionDep,
    new_role: UserRole,
    current_session: UserSession = Depends(get_current_session)
) -> dict[str, Any]:
    current_session.role = new_role
    current_session.last_seen = datetime.now(timezone.utc)
    
    db.add(current_session)
    await db.commit()
    
    return {"message": f"Role switched to {new_role}", "new_role": new_role}

@router.delete("/end-session")
async def end_session(
    db: SessionDep,
    current_session: UserSession = Depends(get_current_session)    
) -> dict[str, str]:
    current_session.is_active = False
    db.add(current_session)
    await db.commit()
    
    return {"message": "Session ended successfully"}