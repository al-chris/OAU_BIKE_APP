from sqlmodel import SQLModel, Field, Column, DateTime, Relationship
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from app.models.user import UserSession

class EmergencyAlertBase(SQLModel):
    latitude: float
    longitude: float
    alert_type: str = "panic"  # panic, medical, security
    message: Optional[str] = None

class EmergencyAlert(EmergencyAlertBase, table=True):
    
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    session_id: uuid.UUID = Field(foreign_key="usersession.id")
    is_resolved: bool = False
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True))
    )
    resolved_at: Optional[datetime] = None
    
    # Response tracking
    sms_sent: bool = False
    authorities_notified: bool = False
    
    # Relationships
    session: Optional["UserSession"] = Relationship(back_populates="emergency_alerts")

class EmergencyAlertCreate(EmergencyAlertBase):
    session_id: uuid.UUID

class EmergencyAlertRead(EmergencyAlertBase):
    id: uuid.UUID
    session_id: uuid.UUID
    is_resolved: bool
    created_at: datetime
    resolved_at: Optional[datetime]
    sms_sent: bool
    authorities_notified: bool

class EmergencyRequest(SQLModel):
    latitude: float
    longitude: float
    alert_type: str = "panic"
    message: Optional[str] = None