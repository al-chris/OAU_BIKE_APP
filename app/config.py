from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str =""
    
    # Security
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 240  # 4 hours
    
    # OAU Campus Boundaries
    OAU_CENTER_LAT: float = 7.5227
    OAU_CENTER_LNG: float = 4.5198
    OAU_RADIUS_KM: float = 5.0
    
    # Emergency Contacts
    STUDENT_UNION_PHONE: str = "+234-xxx-xxx-xxxx"
    CAMPUS_SECURITY_PHONE: str = "+234-xxx-xxx-xxxx"
    OAU_CLINIC_PHONE: str = "+234-xxx-xxx-xxxx"
    
    # SMS Service (for emergency alerts)
    SMS_API_KEY: str = "your-sms-api-key"
    SMS_API_URL: str = "https://api.smsservice.com/send"
    
    # WebSocket
    WEBSOCKET_PING_INTERVAL: int = 30
    WEBSOCKET_PING_TIMEOUT: int = 10
    
    class Config:
        env_file = ".env"

settings = Settings()