"""
Core modules for OAU Campus Bike Visibility App

This package contains the core business logic and utilities:
- geofencing: Campus boundary checking and landmark identification
- emergency_alert: Emergency notification and response system  
- analytics: Usage analytics and demand pattern analysis
"""

from .geofencing import (
    is_within_oau_campus,
    get_nearest_landmark,
    get_landmarks_by_type,
    get_nearby_landmarks,
    validate_coordinates,
    determine_campus_zone,
    OAU_LANDMARKS
)

from .emergency_alert import (
    emergency_service,
    send_emergency_notifications
)

from .analytics import (
    campus_analytics
)

__all__ = [
    # Geofencing
    "is_within_oau_campus",
    "get_nearest_landmark", 
    "get_landmarks_by_type",
    "get_nearby_landmarks",
    "validate_coordinates",
    "determine_campus_zone",
    "OAU_LANDMARKS",
    
    # Emergency
    "emergency_service",
    "send_emergency_notifications",
    
    # Analytics
    "campus_analytics"
]