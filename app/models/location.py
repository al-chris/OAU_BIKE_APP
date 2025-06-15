from sqlmodel import SQLModel, Field, Relationship, Column, DateTime
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from enum import Enum
import uuid

if TYPE_CHECKING:
    from app.models.user import UserSession

class BikeAvailability(str, Enum):
    HIGH = "high"
    MEDIUM = "medium" 
    LOW = "low"
    NONE = "none"

class LocationUpdateBase(SQLModel):
    latitude: float
    longitude: float
    bike_availability: Optional[BikeAvailability] = None
    location_context: Optional[str] = None  # JSON string for campus landmarks

class LocationUpdate(LocationUpdateBase, table=True):
    
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    session_id: uuid.UUID = Field(foreign_key="usersession.id")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True))
    )
    
    # Relationships
    session: Optional["UserSession"] = Relationship(back_populates="locations")

class LocationUpdateCreate(LocationUpdateBase):
    session_id: uuid.UUID

class LocationUpdateRead(LocationUpdateBase):
    id: uuid.UUID
    session_id: uuid.UUID
    timestamp: datetime

class LocationResponse(SQLModel):
    id: str
    role: str
    latitude: float
    longitude: float
    bike_availability: Optional[BikeAvailability]
    last_updated: datetime