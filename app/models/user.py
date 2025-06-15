from sqlmodel import SQLModel, Field, Relationship, Column, DateTime, UUID
from datetime import datetime, timezone, timedelta
from typing import Optional, List, TYPE_CHECKING
from enum import Enum
import uuid

if TYPE_CHECKING:
    from app.models.location import LocationUpdate
    from app.models.emergency import EmergencyAlert

class UserRole(str, Enum):
    PASSENGER = "passenger"
    DRIVER = "driver"

class UserSessionBase(SQLModel):
    role: UserRole
    emergency_contact: Optional[str] = None  # Encrypted phone number
    is_active: bool = True

class UserSession(UserSessionBase, table=True):
    
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(UUID(as_uuid=True), primary_key=True)
    )
    session_token: str = Field(unique=True, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True))
    )
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=4),
        sa_column=Column(DateTime(timezone=True))
    )
    last_seen: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), onupdate=datetime.now(timezone.utc))
    )
    
    # Relationships
    locations: List["LocationUpdate"] = Relationship(back_populates="session")
    emergency_alerts: List["EmergencyAlert"] = Relationship(back_populates="session")
    
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

class UserSessionCreate(UserSessionBase):
    pass

class UserSessionRead(UserSessionBase):
    id: uuid.UUID
    session_token: str
    created_at: datetime
    expires_at: datetime
    last_seen: datetime

class UserSessionUpdate(SQLModel):
    role: Optional[UserRole] = None
    emergency_contact: Optional[str] = None
    is_active: Optional[bool] = None
    last_seen: Optional[datetime] = None