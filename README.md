# OAU Campus Bike Visibility App - Backend

![LOGO](logo.png)

A FastAPI-based backend service providing real-time location visibility for campus bike transportation at Obafemi Awolowo University (OAU). This is a **visibility-only** service, not a ride-matching platform.

## 🚨 Important Safety Notice

This application provides **location visibility ONLY**. It is **NOT** a ride-matching or booking service. Users are 100% responsible for their safety and transportation decisions.

## 🏗️ Architecture

- **Framework**: FastAPI with async/await support
- **Database**: PostgreSQL with SQLModel ORM
- **Real-time**: WebSocket connections for live updates
- **Authentication**: JWT-based session management
- **Notifications**: Multi-channel (SMS, Email, WhatsApp, Push)
- **Geofencing**: OAU campus boundary validation
- **Emergency System**: Comprehensive emergency alert handling

## 📋 Prerequisites

- Python 3.9+
- PostgreSQL 12+
- Redis (optional, for caching)
- SMS service API key (Termii, Africa's Talking, or Twilio)
- SMTP credentials for email notifications

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd oau-bike-app-backend
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

Create `.env` file from template:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Database
DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/oau_bike_app

# Security
SECRET_KEY=your-super-secret-key-for-production-change-this

# OAU Campus Configuration
OAU_CENTER_LAT=7.5227
OAU_CENTER_LNG=4.5198
OAU_RADIUS_KM=5.0

# Emergency Contacts
STUDENT_UNION_PHONE=+234-XXX-XXX-XXXX
CAMPUS_SECURITY_PHONE=+234-XXX-XXX-XXXX
OAU_CLINIC_PHONE=+234-XXX-XXX-XXXX

# SMS Service (choose your provider)
SMS_API_KEY=your-sms-api-key
SMS_API_URL=https://api.termii.com/api/sms/send

# Email Service
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=noreply@oaubikeapp.com
```

### 5. Database Setup

```bash
# Create database
createdb oau_bike_app

# Initialize tables
python -c "
import asyncio
from app.database import create_db_and_tables
asyncio.run(create_db_and_tables())
"
```

### 6. Run Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **WebSocket**: ws://localhost:8000/ws/{session_id}

## 📚 API Documentation

### Authentication Endpoints

```bash
# Create new session
POST /api/auth/create-session
{
    "role": "passenger|driver",
    "emergency_contact": "+234XXXXXXXXX"
}

# Get current session info
GET /api/auth/me

# Switch role
POST /api/auth/switch-role
{
    "new_role": "passenger|driver"
}

# End session
DELETE /api/auth/end-session
```

### Location Endpoints

```bash
# Update location
POST /api/location/update
{
    "latitude": 7.5227,
    "longitude": 4.5198,
    "accuracy": 10.0,
    "bike_availability": "high|medium|low|none"
}

# Get active locations
GET /api/location/active

# Report bike availability
POST /api/location/bike-availability
{
    "latitude": 7.5227,
    "longitude": 4.5198,
    "availability": "high|medium|low|none"
}

# Get campus landmarks
GET /api/location/landmarks
```

### Emergency Endpoints

```bash
# Trigger emergency alert
POST /api/emergency/alert
{
    "latitude": 7.5227,
    "longitude": 4.5198,
    "alert_type": "panic|medical|security",
    "message": "Emergency description"
}

# Get user's alerts
GET /api/emergency/alerts/active

# Resolve alert
PUT /api/emergency/alerts/{alert_id}/resolve
```

## 🔧 Configuration

### Campus Boundaries

The app validates locations within OAU campus boundaries:

```python
# In app/config.py
OAU_CENTER_LAT = 7.5227  # Main Gate coordinates
OAU_CENTER_LNG = 4.5198
OAU_RADIUS_KM = 5.0      # 5km radius from center
```

### Campus Landmarks

Predefined landmarks in `app/core/geofencing.py`:
- Main Gate
- Student Union Building (SUB)
- Mozambique Hostel
- Angola Hostel
- OAU Teaching Hospital
- Sports Complex
- And more...

### Emergency Contacts

Configure in `.env`:
```env
STUDENT_UNION_PHONE=+234-XXX-XXX-XXXX
CAMPUS_SECURITY_PHONE=+234-XXX-XXX-XXXX
OAU_CLINIC_PHONE=+234-XXX-XXX-XXXX
```

## 🔔 Notification Services

### SMS Configuration

**Termii (Recommended for Nigeria):**
```env
SMS_API_KEY=your-termii-api-key
SMS_API_URL=https://api.termii.com/api/sms/send
```

**Africa's Talking:**
```env
SMS_API_KEY=your-africastalking-api-key
SMS_API_URL=https://api.africastalking.com/version1/messaging
```

### Email Configuration

**Gmail SMTP:**
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # Use App Password, not regular password
```

## 🏃‍♂️ Production Deployment

### Using Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Using Gunicorn

```bash
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### Environment Variables for Production

```env
# Use secure secret key
SECRET_KEY=$(openssl rand -hex 32)

# Production database
DATABASE_URL=postgresql+asyncpg://user:pass@db-host:5432/oau_bike_app

# Disable debug features
ENABLE_DETAILED_ANALYTICS=false
```

## 🧪 Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest

# Run with coverage
pytest --cov=app tests/
```

## 📊 Monitoring and Analytics

### Health Check

```bash
GET /health
```

### Real-time Analytics

```bash
# Campus activity stats
GET /api/analytics/real-time

# Demand patterns
GET /api/analytics/demand-patterns

# Safety metrics
GET /api/analytics/safety
```

## 🔒 Security Features

- **Geofencing**: Validates all locations within OAU campus
- **Session-based Auth**: No persistent user accounts
- **Rate Limiting**: Prevents abuse of location updates
- **Emergency Validation**: Verifies emergency alert authenticity
- **Data Privacy**: Minimal data collection, automatic cleanup

## 🚨 Emergency System

### Automatic Notifications

When emergency alert is triggered:
1. **SMS** sent to campus security, student union, and OAU clinic
2. **Email** notifications to campus authorities
3. **User's emergency contact** notified (if provided)
4. **WebSocket broadcast** to nearby app users
5. **Incident documentation** created for follow-up

### Emergency Response Protocol

```python
# Triggered automatically on emergency alert
security_protocol = {
    "actions": [
        "dispatch_security_personnel",
        "alert_nearest_patrol_unit", 
        "activate_emergency_lighting",
        "notify_management"
    ]
}
```

## 🐛 Troubleshooting

### Common Issues

**Database Connection Error:**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Verify connection string
psql postgresql://username:password@localhost:5432/oau_bike_app
```

**SMS Not Sending:**
```bash
# Check API credentials
# Verify phone number format (+234XXXXXXXXX)
# Check SMS service balance/quota
```

**WebSocket Connection Fails:**
```bash
# Check if port 8000 is accessible
# Verify session token is valid
# Check firewall settings
```

### Debug Mode

```bash
# Run with debug logging
uvicorn app.main:app --reload --log-level debug
```

## 📈 Performance Optimization

- **Database Indexing**: Location updates indexed by timestamp
- **Connection Pooling**: AsyncPG connection pool
- **Caching**: Redis for frequently accessed data
- **Rate Limiting**: Prevent API abuse
- **Background Tasks**: Async notification sending

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### Code Standards

- **Python**: Follow PEP 8
- **Type Hints**: Use throughout codebase
- **Async/Await**: For all I/O operations
- **Error Handling**: Comprehensive try/catch blocks
- **Documentation**: Docstrings for all functions

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For support, contact:
- **Technical Issues**: Create GitHub issue
- **Campus Integration**: Contact OAU IT Department
- **Emergency System**: Contact OAU Security

## ⚠️ Disclaimer

This application provides location visibility ONLY. It is NOT a ride-matching service. Users are 100% responsible for their safety, transportation decisions, and interactions with other users. The app developers and OAU are not liable for any incidents during transportation.

---

**Built with ❤️ for the OAU Community**
**Date Created**: June 16, 2025
**Last Updated**: June 16, 2025
**Developer**: al-chris