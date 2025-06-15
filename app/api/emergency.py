from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request

from app.database import SessionDep
from app.models.emergency import EmergencyAlert, EmergencyRequest
from app.models.user import UserSession
from app.api.auth import get_current_session
from app.core.emergency_alert import send_emergency_notifications
from app.core.geofencing import get_nearest_landmark
from typing import Any

router = APIRouter()

@router.post("/alert")
async def trigger_emergency_alert(
    db: SessionDep,
    request: Request,
    emergency_data: EmergencyRequest,
    background_tasks: BackgroundTasks,
    current_session: UserSession = Depends(get_current_session)
) -> dict[str, Any]:
    # Get nearest landmark for context
    nearest_landmark = get_nearest_landmark(
        emergency_data.latitude, 
        emergency_data.longitude
    )
    
    # Create emergency alert record
    alert = EmergencyAlert(
        session_id=current_session.id,
        latitude=emergency_data.latitude,
        longitude=emergency_data.longitude,
        alert_type=emergency_data.alert_type,
        message=emergency_data.message or f"Emergency alert near {nearest_landmark}"
    )
    
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    
    # Send notifications in background
    background_tasks.add_task(
        send_emergency_notifications,
        alert_id=alert.id,
        session=current_session,
        location=(emergency_data.latitude, emergency_data.longitude),
        landmark=nearest_landmark
    )
    
    # Notify via WebSocket
    websocket_manager = request.app.state.websocket_manager
    await websocket_manager.broadcast_location_update({
        "type": "emergency_alert",
        "alert_id": str(alert.id),
        "alert_type": emergency_data.alert_type,
        "latitude": emergency_data.latitude,
        "longitude": emergency_data.longitude,
        "landmark": nearest_landmark,
        "timestamp": alert.created_at.isoformat()
    })
    
    return {
        "message": "Emergency alert sent successfully",
        "alert_id": str(alert.id),
        "location": nearest_landmark,
        "authorities_notified": True
    }

@router.get("/alerts/active")
async def get_active_alerts(
    db: SessionDep,
    current_session: UserSession = Depends(get_current_session)
):
    # Only return user's own alerts for privacy
    from sqlmodel import select, desc
    
    result = await db.execute(
        select(EmergencyAlert)
        .where(
            EmergencyAlert.session_id == current_session.id,
            EmergencyAlert.is_resolved == False
        )
        .order_by(desc(EmergencyAlert.created_at))
    )
    
    alerts = result.scalars().all()
    return {"alerts": alerts}

@router.put("/alerts/{alert_id}/resolve")
async def resolve_alert(
    db: SessionDep,
    alert_id: str,
    current_session: UserSession = Depends(get_current_session)
):
    from sqlmodel import select
    from datetime import datetime, timezone
    import uuid
    
    result = await db.execute(
        select(EmergencyAlert)
        .where(
            EmergencyAlert.id == uuid.UUID(alert_id),
            EmergencyAlert.session_id == current_session.id
        )
    )
    
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.is_resolved = True
    alert.resolved_at = datetime.now(timezone.utc)
    
    db.add(alert)
    await db.commit()
    
    return {"message": "Alert resolved successfully"}