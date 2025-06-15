from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import select, desc
from typing import List, Any
from datetime import datetime, timezone, timedelta

from app.database import SessionDep
from app.models.location import (
    LocationUpdate, LocationUpdateCreate, LocationResponse,
    BikeAvailability
)
from app.models.user import UserSession
from app.core.geofencing import is_within_oau_campus, get_nearest_landmark
from app.api.auth import get_current_session

router = APIRouter()

class LocationUpdateRequest(LocationUpdateCreate):
    pass

@router.post("/update")
async def update_location(
    db: SessionDep,
    request: Request,
    location_data: LocationUpdateRequest,
    current_session: UserSession = Depends(get_current_session)
) -> dict[str, Any]:
    # Verify location is within OAU campus
    if not is_within_oau_campus(location_data.latitude, location_data.longitude):
        raise HTTPException(
            status_code=400, 
            detail="Location is outside OAU campus boundaries"
        )
    
    # Get nearest landmark for context
    nearest_landmark = get_nearest_landmark(location_data.latitude, location_data.longitude)
    
    # Create location update
    location_update = LocationUpdate(
        session_id=current_session.id,
        latitude=location_data.latitude,
        longitude=location_data.longitude,
        bike_availability=location_data.bike_availability,
        location_context=f"Near {nearest_landmark}"
    )
    
    db.add(location_update)
    
    # Update session last_seen
    current_session.last_seen = datetime.now(timezone.utc)
    db.add(current_session)
    
    await db.commit()
    await db.refresh(location_update)
    
    # Broadcast to WebSocket clients
    websocket_manager = request.app.state.websocket_manager
    await websocket_manager.broadcast_location_update({
        "type": "location_update",
        "session_id": str(current_session.id),
        "role": current_session.role,
        "latitude": location_data.latitude,
        "longitude": location_data.longitude,
        "bike_availability": location_data.bike_availability,
        "landmark": nearest_landmark,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    return {
        "message": "Location updated successfully",
        "nearest_landmark": nearest_landmark
    }

@router.get("/active", response_model=List[LocationResponse])
async def get_active_locations(
    db: SessionDep,
    current_session: UserSession = Depends(get_current_session)
) -> list[Any]:
    # Get all active sessions within last 5 minutes
    recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    
    # Query active sessions
    active_sessions_result = await db.execute(
        select(UserSession).where(
            UserSession.is_active == True,
            UserSession.last_seen >= recent_cutoff,
            UserSession.id != current_session.id  # Exclude current user
        )
    )
    active_sessions = active_sessions_result.scalars().all()
    
    locations: list[LocationResponse] = []
    for session in active_sessions:
        # Get latest location for each session
        latest_location_result = await db.execute(
            select(LocationUpdate)
            .where(LocationUpdate.session_id == session.id)
            .order_by(desc(LocationUpdate.timestamp))
            .limit(1)
        )
        latest_location = latest_location_result.scalar_one_or_none()
        
        if latest_location:
            locations.append(LocationResponse(
                id=str(session.id),
                role=session.role,
                latitude=latest_location.latitude,
                longitude=latest_location.longitude,
                bike_availability=latest_location.bike_availability,
                last_updated=latest_location.timestamp
            ))
    
    return locations

@router.get("/landmarks")
async def get_campus_landmarks() -> dict[str, Any]:
    """Get OAU campus landmarks for reference"""
    from app.core.geofencing import OAU_LANDMARKS
    return {"landmarks": OAU_LANDMARKS}

@router.post("/bike-availability")
async def report_bike_availability(
    db: SessionDep,
    latitude: float,
    longitude: float,
    availability: BikeAvailability,
    current_session: UserSession = Depends(get_current_session)
) -> dict[str, Any]:
    # Verify location is within campus
    if not is_within_oau_campus(latitude, longitude):
        raise HTTPException(
            status_code=400,
            detail="Location is outside OAU campus boundaries"
        )
    
    # Create location update with bike availability
    location_update = LocationUpdate(
        session_id=current_session.id,
        latitude=latitude,
        longitude=longitude,
        bike_availability=availability,
        location_context=f"Bike availability report: {availability}"
    )
    
    db.add(location_update)
    await db.commit()
    
    return {
        "message": "Bike availability reported successfully",
        "availability": availability,
        "location": get_nearest_landmark(latitude, longitude)
    }