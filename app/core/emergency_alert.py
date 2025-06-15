import asyncio
import json
import aiohttp
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.config import settings
from app.models.user import UserSession
from app.models.emergency import EmergencyAlert
from app.core.geofencing import get_nearest_landmark
from app.utils.notifications import SMSService, EmailService

class EmergencyAlertService:
    def __init__(self):
        self.sms_service = SMSService()
        self.email_service = EmailService()
    
    async def handle_emergency_alert(
        self,
        alert: EmergencyAlert,
        session: UserSession,
        location: tuple,
        landmark: str
    ):
        """
        Comprehensive emergency alert handling
        """
        try:
            # Prepare alert data
            alert_data: dict[str, Any] = {
                "alert_id": str(alert.id),
                "alert_type": alert.alert_type,
                "location": {
                    "latitude": location[0],
                    "longitude": location[1],
                    "landmark": landmark
                },
                "timestamp": alert.created_at.isoformat(),
                "message": alert.message,
                "session_id": str(session.id)
            }
            
            # Execute all alert actions concurrently
            await asyncio.gather(
                self._send_sms_alerts(alert_data, session),
                self._notify_campus_authorities(alert_data),
                self._send_email_notifications(alert_data, session),
                self._log_emergency_event(alert_data),
                return_exceptions=True
            )
            
            return True
            
        except Exception as e:
            print(f"Emergency alert handling failed: {e}")
            return False
    
    async def _send_sms_alerts(self, alert_data: Dict[str, Any], session: UserSession):
        """Send SMS alerts to emergency contacts"""
        try:
            # Campus authority numbers
            authority_numbers: list[str] = [
                settings.STUDENT_UNION_PHONE,
                settings.CAMPUS_SECURITY_PHONE,
                settings.OAU_CLINIC_PHONE
            ]
            
            # User's emergency contact
            if session.emergency_contact:
                authority_numbers.append(session.emergency_contact)
            
            # Prepare SMS message
            message = self._format_emergency_sms(alert_data)
            
            # Send to all contacts
            sms_tasks = [
                self.sms_service.send_sms(number, message)
                for number in authority_numbers
            ]
            
            await asyncio.gather(*sms_tasks, return_exceptions=True)
            
        except Exception as e:
            print(f"SMS alert failed: {e}")
    
    async def _notify_campus_authorities(self, alert_data: Dict[str, Any]):
        """Send detailed notification to campus authorities"""
        try:
            # Format detailed alert for authorities
            authority_message = self._format_authority_alert(alert_data)
            
            # Send to multiple channels
            await asyncio.gather(
                self._send_to_security_api(alert_data),
                self._send_to_student_union_system(alert_data),
                self._create_incident_report(alert_data),
                return_exceptions=True
            )
            
        except Exception as e:
            print(f"Authority notification failed: {e}")
    
    async def _send_email_notifications(self, alert_data: Dict[str, Any], session: UserSession):
        """Send email notifications for record keeping"""
        try:
            # Campus security email
            security_emails: list[str] = [
                "security@oauife.edu.ng",
                "studentaffairs@oauife.edu.ng"
            ]
            
            email_subject = f"🚨 EMERGENCY ALERT - {alert_data['alert_type'].upper()}"
            email_body = self._format_emergency_email(alert_data)
            
            for email in security_emails:
                await self.email_service.send_email(
                    to_email=email,
                    subject=email_subject,
                    body=email_body
                )
                
        except Exception as e:
            print(f"Email notification failed: {e}")
    
    async def _log_emergency_event(self, alert_data: Dict[str, Any]):
        """Log emergency event for analytics and follow-up"""
        try:
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "emergency_alert",
                "alert_data": alert_data,
                "response_time": datetime.now(timezone.utc).isoformat()
            }
            
            # Log to file/database for audit trail
            print(f"EMERGENCY LOG: {json.dumps(log_entry, indent=2)}")
            
        except Exception as e:
            print(f"Emergency logging failed: {e}")
    
    def _format_emergency_sms(self, alert_data: Dict[str, Any]) -> str:
        """Format SMS message for emergency contacts"""
        location = alert_data["location"]
        timestamp = datetime.fromisoformat(alert_data["timestamp"].replace('Z', '+00:00'))
        
        return f"""🚨 OAU CAMPUS EMERGENCY ALERT
Type: {alert_data['alert_type'].upper()}
Location: {location['landmark']}
Time: {timestamp.strftime('%H:%M %d/%m/%Y')}
Alert ID: {alert_data['alert_id'][:8]}
Message: {alert_data.get('message', 'No additional message')}

Please respond immediately."""
    
    def _format_authority_alert(self, alert_data: Dict[str, Any]) -> str:
        """Format detailed alert for campus authorities"""
        location = alert_data["location"]
        
        return f"""
EMERGENCY ALERT DETAILS
======================
Alert ID: {alert_data['alert_id']}
Type: {alert_data['alert_type']}
Time: {alert_data['timestamp']}

LOCATION:
- Landmark: {location['landmark']}
- Coordinates: {location['latitude']}, {location['longitude']}

MESSAGE: {alert_data.get('message', 'No additional message')}

ACTION REQUIRED: Immediate response and assistance needed.
"""
    
    def _format_emergency_email(self, alert_data: Dict[str, Any]) -> str:
        """Format email notification with full details"""
        location = alert_data["location"]
        
        return f"""
<h2>🚨 EMERGENCY ALERT - OAU CAMPUS</h2>

<p><strong>Alert Type:</strong> {alert_data['alert_type'].upper()}</p>
<p><strong>Time:</strong> {alert_data['timestamp']}</p>
<p><strong>Alert ID:</strong> {alert_data['alert_id']}</p>

<h3>Location Details:</h3>
<ul>
<li><strong>Landmark:</strong> {location['landmark']}</li>
<li><strong>Coordinates:</strong> {location['latitude']}, {location['longitude']}</li>
</ul>

<h3>Message:</h3>
<p>{alert_data.get('message', 'No additional message provided')}</p>

<h3>Required Action:</h3>
<p>Immediate response and assistance required. Please coordinate with campus security and emergency services.</p>

<hr>
<small>This is an automated emergency alert from the OAU Campus Bike App system.</small>
"""
    
    async def _send_to_security_api(self, alert_data: Dict):
        """Send alert to campus security system API (if available)"""
        try:
            # Placeholder for campus security API integration
            # Replace with actual campus security system endpoint
            security_api_url = "https://security.oauife.edu.ng/api/alerts"
            
            async with aiohttp.ClientSession() as session:
                await session.post(
                    security_api_url,
                    json=alert_data,
                    headers={"Authorization": "Bearer your-api-key"}
                )
                
        except Exception as e:
            print(f"Security API notification failed: {e}")
    
    async def _send_to_student_union_system(self, alert_data: Dict[str, Any]):
        """Send alert to student union notification system"""
        try:
            # Placeholder for student union system integration
            # This could be their WhatsApp bot, Telegram channel, etc.
            union_webhook = "https://studentunion.oauife.edu.ng/emergency"
            
            formatted_message = f"""
*EMERGENCY ALERT*
Type: {alert_data['alert_type']}
Location: {alert_data['location']['landmark']}
Time: {alert_data['timestamp']}
Message: {alert_data.get('message', 'N/A')}
"""
            
            async with aiohttp.ClientSession() as session:
                await session.post(
                    union_webhook,
                    json={"message": formatted_message}
                )
                
        except Exception as e:
            print(f"Student union notification failed: {e}")
    
    async def _create_incident_report(self, alert_data: Dict[str, Any]):
        """Create formal incident report for campus administration"""
        try:
            incident_report: dict[str, Any] = {
                "report_id": f"INC-{alert_data['alert_id'][:8]}",
                "type": "emergency_alert",
                "category": alert_data['alert_type'],
                "location": alert_data['location'],
                "timestamp": alert_data['timestamp'],
                "description": alert_data.get('message', 'Emergency alert triggered'),
                "status": "active",
                "priority": "high",
                "reporter": "campus_bike_app",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Log incident report (could be saved to database or sent to management system)
            print(f"INCIDENT REPORT CREATED: {json.dumps(incident_report, indent=2)}")
            
        except Exception as e:
            print(f"Incident report creation failed: {e}")

# Global instance
emergency_service = EmergencyAlertService()

async def send_emergency_notifications(
    alert_id: str,
    session: UserSession, 
    location: tuple,
    landmark: str
):
    """
    Main function to handle emergency notifications
    Called from the emergency API endpoint
    """
    try:
        # Get alert from database
        from app.database import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(EmergencyAlert).where(EmergencyAlert.id == alert_id)
            )
            alert = result.scalar_one_or_none()
            
            if alert:
                success = await emergency_service.handle_emergency_alert(
                    alert, session, location, landmark
                )
                
                # Update alert status
                alert.authorities_notified = success
                alert.sms_sent = success
                db.add(alert)
                await db.commit()
                
                return success
            
    except Exception as e:
        print(f"Emergency notification failed: {e}")
        return False