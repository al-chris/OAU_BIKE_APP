import asyncio
import aiohttp
import aiosmtplib
import json
import logging
from typing import List, Dict, Optional, Union
from datetime import datetime, timezone
from abc import ABC, abstractmethod
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotificationService(ABC):
    """Abstract base class for notification services"""
    
    @abstractmethod
    async def send_notification(self, recipient: str, message: str, **kwargs) -> bool:
        pass

class SMSService(NotificationService):
    """SMS notification service with multiple provider support"""
    
    def __init__(self):
        self.api_key = settings.SMS_API_KEY
        self.api_url = settings.SMS_API_URL
        self.provider = self._detect_provider()
        
    def _detect_provider(self) -> str:
        """Detect SMS provider based on API URL"""
        if "termii" in self.api_url.lower():
            return "termii"
        elif "africastalking" in self.api_url.lower():
            return "africastalking"
        elif "twilio" in self.api_url.lower():
            return "twilio"
        else:
            return "generic"
    
    async def send_sms(
        self, 
        phone_number: str, 
        message: str, 
        sender_id: str = "OAU-BIKE"
    ) -> bool:
        """
        Send SMS to a phone number
        
        Args:
            phone_number: Recipient phone number (e.g., +2348012345678)
            message: SMS message content
            sender_id: Sender ID displayed to recipient
        """
        try:
            # Format phone number
            formatted_number = self._format_phone_number(phone_number)
            
            # Prepare payload based on provider
            payload = self._prepare_sms_payload(formatted_number, message, sender_id)
            
            # Send SMS
            success = await self._send_sms_request(payload)
            
            if success:
                logger.info(f"SMS sent successfully to {formatted_number[:8]}****")
            else:
                logger.error(f"Failed to send SMS to {formatted_number[:8]}****")
                
            return success
            
        except Exception as e:
            logger.error(f"SMS sending error: {e}")
            return False
    
    async def send_bulk_sms(
        self, 
        phone_numbers: List[str], 
        message: str,
        sender_id: str = "OAU-BIKE"
    ) -> Dict[str, bool]:
        """
        Send SMS to multiple recipients
        
        Returns:
            Dict mapping phone numbers to success status
        """
        results = {}
        
        # Send SMS to all numbers concurrently
        tasks = [
            self.send_sms(phone, message, sender_id) 
            for phone in phone_numbers
        ]
        
        sms_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for phone, result in zip(phone_numbers, sms_results):
            if isinstance(result, Exception):
                results[phone] = False
                logger.error(f"Bulk SMS error for {phone}: {result}")
            else:
                results[phone] = result
        
        success_count = sum(1 for success in results.values() if success)
        logger.info(f"Bulk SMS: {success_count}/{len(phone_numbers)} sent successfully")
        
        return results
    
    def _format_phone_number(self, phone_number: str) -> str:
        """Format phone number to international format"""
        # Remove all non-numeric characters except +
        cleaned = ''.join(c for c in phone_number if c.isdigit() or c == '+')
        
        # Handle Nigerian numbers
        if cleaned.startswith('0'):
            # Convert 0801... to +2348801...
            cleaned = '+234' + cleaned[1:]
        elif cleaned.startswith('234') and not cleaned.startswith('+'):
            # Convert 234801... to +234801...
            cleaned = '+' + cleaned
        elif not cleaned.startswith('+'):
            # Assume Nigerian number, add +234
            cleaned = '+234' + cleaned
            
        return cleaned
    
    def _prepare_sms_payload(self, phone_number: str, message: str, sender_id: str) -> Dict:
        """Prepare SMS payload based on provider"""
        if self.provider == "termii":
            return {
                "to": phone_number,
                "from": sender_id,
                "sms": message,
                "type": "plain",
                "api_key": self.api_key,
                "channel": "generic"
            }
        elif self.provider == "africastalking":
            return {
                "username": "sandbox",  # or your username
                "to": phone_number,
                "message": message,
                "from": sender_id
            }
        elif self.provider == "twilio":
            return {
                "To": phone_number,
                "From": sender_id,
                "Body": message
            }
        else:
            # Generic format
            return {
                "to": phone_number,
                "message": message,
                "from": sender_id,
                "api_key": self.api_key
            }
    
    async def _send_sms_request(self, payload: Dict) -> bool:
        """Send HTTP request to SMS provider"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # Add provider-specific headers
            if self.provider == "africastalking":
                headers["apiKey"] = self.api_key
            elif self.provider == "twilio":
                # Twilio uses Basic Auth
                import base64
                credentials = base64.b64encode(f"{self.api_key}:token".encode()).decode()
                headers["Authorization"] = f"Basic {credentials}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    response_text = await response.text()
                    
                    if response.status == 200:
                        response_data = await response.json()
                        return self._parse_sms_response(response_data)
                    else:
                        logger.error(f"SMS API error: {response.status} - {response_text}")
                        return False
                        
        except asyncio.TimeoutError:
            logger.error("SMS request timeout")
            return False
        except Exception as e:
            logger.error(f"SMS request error: {e}")
            return False
    
    def _parse_sms_response(self, response_data: Dict) -> bool:
        """Parse SMS provider response to determine success"""
        if self.provider == "termii":
            return response_data.get("message_id") is not None
        elif self.provider == "africastalking":
            return "SMSMessageData" in response_data
        elif self.provider == "twilio":
            return response_data.get("status") in ["queued", "sent"]
        else:
            # Generic success indicators
            return (
                response_data.get("success", False) or
                response_data.get("status") == "success" or
                "message_id" in response_data
            )
    
    async def send_emergency_sms(
        self, 
        phone_numbers: List[str], 
        alert_data: Dict
    ) -> Dict[str, bool]:
        """
        Send emergency SMS with high priority
        
        Args:
            phone_numbers: List of emergency contact numbers
            alert_data: Emergency alert information
        """
        emergency_message = self._format_emergency_message(alert_data)
        
        # Send with high priority
        results = await self.send_bulk_sms(
            phone_numbers, 
            emergency_message,
            sender_id="OAU-EMRG"
        )
        
        # Log emergency SMS results
        logger.critical(f"Emergency SMS sent to {len(phone_numbers)} contacts")
        for phone, success in results.items():
            if not success:
                logger.critical(f"FAILED to send emergency SMS to {phone}")
        
        return results
    
    def _format_emergency_message(self, alert_data: Dict) -> str:
        """Format emergency alert message for SMS"""
        location = alert_data.get("location", {})
        timestamp = datetime.now(timezone.utc).strftime("%H:%M %d/%m/%Y")
        
        return f"""🚨 OAU EMERGENCY ALERT
                Type: {alert_data.get('alert_type', 'Unknown').upper()}
                Location: {location.get('landmark', 'Unknown')}
                Time: {timestamp}
                Alert ID: {alert_data.get('alert_id', '')[:8]}

                IMMEDIATE RESPONSE REQUIRED
                Contact Campus Security: {settings.CAMPUS_SECURITY_PHONE}"""

    async def send_notification(self, recipient: str, message: str, **kwargs) -> bool:
        """Implementation of abstract send_notification method"""
        sender_id = kwargs.get('sender_id', 'OAU-BIKE')
        return await self.send_sms(recipient, message, sender_id)

class EmailService(NotificationService):
    """Email notification service"""
    
    def __init__(self):
        self.smtp_host = getattr(settings, 'SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = getattr(settings, 'SMTP_PORT', 587)
        self.smtp_username = getattr(settings, 'SMTP_USERNAME', '')
        self.smtp_password = getattr(settings, 'SMTP_PASSWORD', '')
        self.from_email = getattr(settings, 'FROM_EMAIL', 'noreply@oaubikeapp.com')
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        attachments: Optional[List[Dict]] = None
    ) -> bool:
        """
        Send email notification
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Plain text email body
            html_body: HTML email body (optional)
            attachments: List of attachment dicts (optional)
        """
        try:
                        
            # Create message
            message = MIMEMultipart('alternative')
            message['From'] = self.from_email
            message['To'] = to_email
            message['Subject'] = subject
            
            # Add plain text part
            text_part = MIMEText(body, 'plain')
            message.attach(text_part)
            
            # Add HTML part if provided
            if html_body:
                html_part = MIMEText(html_body, 'html')
                message.attach(html_part)
            
            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    self._add_attachment(message, attachment)
            
            # Send email
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                start_tls=True,
                username=self.smtp_username,
                password=self.smtp_password,
            )
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Email sending error to {to_email}: {e}")
            return False
    
    async def send_bulk_email(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> Dict[str, bool | BaseException]:
        """Send email to multiple recipients"""
        tasks = [
            self.send_email(email, subject, body, html_body)
            for email in recipients
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            email: result if not isinstance(result, Exception) else False
            for email, result in zip(recipients, results)
        }
    
    def _add_attachment(self, message: MIMEMultipart, attachment: Dict):
        """Add attachment to email message"""
        try:
            filename = attachment['filename']
            content = attachment['content']
            
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(content)
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {filename}'
            )
            message.attach(part)
            
        except Exception as e:
            logger.error(f"Error adding attachment {attachment.get('filename', 'unknown')}: {e}")
    
    async def send_emergency_email(
        self,
        recipients: List[str],
        alert_data: Dict
    ) -> Dict[str, bool | BaseException]:
        """Send emergency notification email"""
        subject = f"🚨 OAU CAMPUS EMERGENCY - {alert_data.get('alert_type', 'Unknown').upper()}"
        
        # Plain text body
        plain_body = self._format_emergency_email_text(alert_data)
        
        # HTML body
        html_body = self._format_emergency_email_html(alert_data)
        
        results = await self.send_bulk_email(
            recipients,
            subject,
            plain_body,
            html_body
        )
        
        logger.critical(f"Emergency email sent to {len(recipients)} recipients")
        return results
    
    def _format_emergency_email_text(self, alert_data: Dict) -> str:
        """Format emergency email as plain text"""
        location = alert_data.get("location", {})
        timestamp = datetime.now(timezone.utc).strftime("%H:%M on %d/%m/%Y")
        
        return f"""
OAU CAMPUS EMERGENCY ALERT

Alert Type: {alert_data.get('alert_type', 'Unknown').upper()}
Time: {timestamp}
Alert ID: {alert_data.get('alert_id', 'Unknown')}

LOCATION DETAILS:
- Landmark: {location.get('landmark', 'Unknown')}
- Coordinates: {location.get('latitude', 'N/A')}, {location.get('longitude', 'N/A')}

MESSAGE: {alert_data.get('message', 'No additional message provided')}

IMMEDIATE ACTION REQUIRED:
Please coordinate response with campus security and emergency services.

Emergency Contacts:
- Campus Security: {settings.CAMPUS_SECURITY_PHONE}
- Student Union: {settings.STUDENT_UNION_PHONE}
- OAU Clinic: {settings.OAU_CLINIC_PHONE}

---
This is an automated emergency alert from the OAU Campus Bike App system.
Generated at: {datetime.now(timezone.utc).isoformat()}
"""
    
    def _format_emergency_email_html(self, alert_data: Dict) -> str:
        """Format emergency email as HTML"""
        location = alert_data.get("location", {})
        timestamp = datetime.now(timezone.utc).strftime("%H:%M on %d/%m/%Y")
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>OAU Emergency Alert</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .alert-header {{ background-color: #dc3545; color: white; padding: 15px; border-radius: 5px; }}
        .alert-content {{ padding: 20px; border: 2px solid #dc3545; border-radius: 5px; margin-top: 10px; }}
        .location-info {{ background-color: #f8f9fa; padding: 10px; border-radius: 3px; margin: 10px 0; }}
        .contacts {{ background-color: #e9ecef; padding: 15px; border-radius: 3px; margin-top: 20px; }}
        .urgent {{ color: #dc3545; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="alert-header">
        <h1>🚨 OAU CAMPUS EMERGENCY ALERT</h1>
    </div>
    
    <div class="alert-content">
        <h2 class="urgent">Alert Type: {alert_data.get('alert_type', 'Unknown').upper()}</h2>
        <p><strong>Time:</strong> {timestamp}</p>
        <p><strong>Alert ID:</strong> {alert_data.get('alert_id', 'Unknown')}</p>
        
        <div class="location-info">
            <h3>Location Details:</h3>
            <ul>
                <li><strong>Landmark:</strong> {location.get('landmark', 'Unknown')}</li>
                <li><strong>Coordinates:</strong> {location.get('latitude', 'N/A')}, {location.get('longitude', 'N/A')}</li>
            </ul>
        </div>
        
        <h3>Message:</h3>
        <p>{alert_data.get('message', 'No additional message provided')}</p>
        
        <h2 class="urgent">IMMEDIATE ACTION REQUIRED</h2>
        <p>Please coordinate response with campus security and emergency services immediately.</p>
        
        <div class="contacts">
            <h3>Emergency Contacts:</h3>
            <ul>
                <li><strong>Campus Security:</strong> {settings.CAMPUS_SECURITY_PHONE}</li>
                <li><strong>Student Union:</strong> {settings.STUDENT_UNION_PHONE}</li>
                <li><strong>OAU Clinic:</strong> {settings.OAU_CLINIC_PHONE}</li>
            </ul>
        </div>
    </div>
    
    <hr>
    <small>
        This is an automated emergency alert from the OAU Campus Bike App system.<br>
        Generated at: {datetime.now(timezone.utc).isoformat()}
    </small>
</body>
</html>
"""
    async def send_notification(self, recipient: str, message: str, **kwargs) -> bool:
        """Implementation of abstract send_notification method"""
        subject = kwargs.get('subject', 'OAU Campus Bike App Notification')
        html_body = kwargs.get('html_body', None)
        attachments = kwargs.get('attachments', None)
        
        return await self.send_email(
            to_email=recipient,
            subject=subject,
            body=message,
            html_body=html_body,
            attachments=attachments
        )

class WhatsAppService(NotificationService):
    """WhatsApp notification service (using WhatsApp Business API)"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'WHATSAPP_API_KEY', '')
        self.api_url = getattr(settings, 'WHATSAPP_API_URL', '')
        self.phone_number_id = getattr(settings, 'WHATSAPP_PHONE_ID', '')
    
    async def send_whatsapp_message(
        self,
        recipient: str,
        message: str,
        message_type: str = "text"
    ) -> bool:
        """Send WhatsApp message"""
        try:
            if not all([self.api_key, self.api_url, self.phone_number_id]):
                logger.warning("WhatsApp service not properly configured")
                return False
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "messaging_product": "whatsapp",
                "to": self._format_phone_number(recipient),
                "type": message_type,
                "text": {"body": message}
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/{self.phone_number_id}/messages",
                    json=payload,
                    headers=headers
                ) as response:
                    
                    if response.status == 200:
                        logger.info(f"WhatsApp message sent to {recipient[:8]}****")
                        return True
                    else:
                        logger.error(f"WhatsApp API error: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"WhatsApp sending error: {e}")
            return False
    
    def _format_phone_number(self, phone_number: str) -> str:
        """Format phone number for WhatsApp (remove + sign)"""
        cleaned = ''.join(c for c in phone_number if c.isdigit())
        if not cleaned.startswith('234') and len(cleaned) == 11:
            cleaned = '234' + cleaned[1:]
        return cleaned
    
    async def send_notification(self, recipient: str, message: str, **kwargs) -> bool:
        """Implementation of abstract send_notification method"""
        message_type = kwargs.get('message_type', 'text')
        return await self.send_whatsapp_message(recipient, message, message_type)

class PushNotificationService(NotificationService):
    """Push notification service for mobile apps"""
    
    def __init__(self):
        self.fcm_server_key = getattr(settings, 'FCM_SERVER_KEY', '')
        self.fcm_url = "https://fcm.googleapis.com/fcm/send"
    
    async def send_push_notification(
        self,
        device_tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict] = None
    ) -> Dict[str, bool]:
        """Send push notification to mobile devices"""
        try:
            if not self.fcm_server_key:
                logger.warning("FCM not configured")
                return {token: False for token in device_tokens}
            
            headers = {
                "Authorization": f"key={self.fcm_server_key}",
                "Content-Type": "application/json"
            }
            
            results = {}
            
            for token in device_tokens:
                payload = {
                    "to": token,
                    "notification": {
                        "title": title,
                        "body": body,
                        "sound": "default"
                    },
                    "data": data or {},
                    "priority": "high"
                }
                
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            self.fcm_url,
                            json=payload,
                            headers=headers
                        ) as response:
                            results[token] = response.status == 200
                            
                except Exception as e:
                    logger.error(f"Push notification error for token {token[:10]}...: {e}")
                    results[token] = False
            
            return results
            
        except Exception as e:
            logger.error(f"Push notification service error: {e}")
            return {token: False for token in device_tokens}
        
    async def send_notification(self, recipient: str, message: str, **kwargs) -> bool:
        """Implementation of abstract send_notification method for single device"""
        title = kwargs.get('title', 'OAU Campus Bike App')
        data = kwargs.get('data', None)
        
        # Send to single device token
        results = await self.send_push_notification(
            device_tokens=[recipient],
            title=title,
            body=message,
            data=data
        )
        
        return results.get(recipient, False)

class NotificationManager:
    """Centralized notification management"""
    
    def __init__(self):
        self.sms_service = SMSService()
        self.email_service = EmailService()
        self.whatsapp_service = WhatsAppService()
        self.push_service = PushNotificationService()
    
    async def send_multi_channel_notification(
        self,
        recipients: Dict[str, List[str]],  # {"sms": [...], "email": [...], "whatsapp": [...]}
        message_data: Dict,
        notification_type: str = "general"
    ) -> Dict[str, Dict[str, bool]]:
        """
        Send notification through multiple channels
        
        Args:
            recipients: Dict with channel names and recipient lists
            message_data: Message content and metadata
            notification_type: Type of notification (general, emergency, alert)
        """
        results = {}
        
        # Determine message content based on type
        if notification_type == "emergency":
            message_content = self._prepare_emergency_content(message_data)
        else:
            message_content = self._prepare_general_content(message_data)
        
        # Send SMS notifications
        if recipients.get("sms"):
            if notification_type == "emergency":
                results["sms"] = await self.sms_service.send_emergency_sms(
                    recipients["sms"], message_data
                )
            else:
                results["sms"] = await self.sms_service.send_bulk_sms(
                    recipients["sms"], message_content["sms"]
                )
        
        # Send Email notifications
        if recipients.get("email"):
            if notification_type == "emergency":
                results["email"] = await self.email_service.send_emergency_email(
                    recipients["email"], message_data
                )
            else:
                results["email"] = await self.email_service.send_bulk_email(
                    recipients["email"],
                    message_content["email_subject"],
                    message_content["email_body"]
                )
        
        # Send WhatsApp notifications
        if recipients.get("whatsapp"):
            whatsapp_results = {}
            for recipient in recipients["whatsapp"]:
                success = await self.whatsapp_service.send_whatsapp_message(
                    recipient, message_content["whatsapp"]
                )
                whatsapp_results[recipient] = success
            results["whatsapp"] = whatsapp_results
        
        # Send Push notifications
        if recipients.get("push"):
            results["push"] = await self.push_service.send_push_notification(
                recipients["push"],
                message_content["push_title"],
                message_content["push_body"],
                message_data
            )
        
        # Log notification summary
        self._log_notification_summary(results, notification_type)
        
        return results
    
    def _prepare_emergency_content(self, message_data: Dict) -> Dict[str, str]:
        """Prepare content for emergency notifications"""
        # Emergency content is handled by individual service methods
        return {}
    
    def _prepare_general_content(self, message_data: Dict) -> Dict[str, str]:
        """Prepare content for general notifications"""
        title = message_data.get("title", "OAU Campus Bike App Notification")
        body = message_data.get("message", "You have a new notification")
        
        return {
            "sms": f"{title}\n\n{body}",
            "email_subject": title,
            "email_body": body,
            "whatsapp": f"*{title}*\n\n{body}",
            "push_title": title,
            "push_body": body
        }
    
    def _log_notification_summary(self, results: Dict, notification_type: str):
        """Log summary of notification results"""
        total_sent = 0
        total_failed = 0
        
        for channel, channel_results in results.items():
            if isinstance(channel_results, dict):
                sent = sum(1 for success in channel_results.values() if success)
                failed = len(channel_results) - sent
                total_sent += sent
                total_failed += failed
                
                logger.info(f"{channel.upper()}: {sent} sent, {failed} failed")
        
        log_level = logger.critical if notification_type == "emergency" else logger.info
        log_level(f"Notification summary - Type: {notification_type}, Sent: {total_sent}, Failed: {total_failed}")

# Global notification manager instance
notification_manager = NotificationManager()