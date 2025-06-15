import math
import json
from typing import Tuple, List, Dict, Any, Optional
from datetime import datetime
from app.config import settings

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points using Haversine formula
    Returns distance in kilometers
    """
    R = 6371  # Earth's radius in kilometers
    
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c

def is_within_oau_campus(latitude: float, longitude: float) -> bool:
    """
    Check if coordinates are within OAU campus boundaries
    Uses multiple validation methods for accuracy
    """
    # Primary check: Distance from campus center
    distance_from_center = calculate_distance(
        latitude, longitude,
        settings.OAU_CENTER_LAT, settings.OAU_CENTER_LNG
    )
    
    if distance_from_center > settings.OAU_RADIUS_KM:
        return False
    
    # Secondary check: Polygon boundary (more precise)
    return is_within_oau_polygon(latitude, longitude)

def is_within_oau_polygon(latitude: float, longitude: float) -> bool:
    """
    Check if point is within OAU campus polygon boundary
    More precise boundary checking
    """
    # OAU Campus boundary polygon (approximate coordinates)
    # You should replace these with actual surveyed coordinates
    oau_polygon = [
        (7.5150, 4.5100),  # Southwest corner
        (7.5300, 4.5050),  # Northwest corner  
        (7.5380, 4.5200),  # Northeast corner
        (7.5350, 4.5300),  # East boundary
        (7.5250, 4.5350),  # Southeast corner
        (7.5100, 4.5250),  # South boundary
        (7.5150, 4.5100),  # Close polygon
    ]
    
    return point_in_polygon(latitude, longitude, oau_polygon)

def point_in_polygon(lat: float, lon: float, polygon: List[Tuple[float, float]]) -> bool:
    """
    Ray casting algorithm to determine if point is inside polygon
    """
    x, y = lon, lat
    n = len(polygon)
    inside = False
    
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    
    return inside

# OAU Campus Landmarks with precise coordinates
OAU_LANDMARKS: dict[str, dict[str, Any]] = {
    # Main Campus Buildings
    "main_gate": {
        "lat": 7.5227, "lng": 4.5198, 
        "name": "Main Gate",
        "type": "entrance",
        "description": "Primary campus entrance"
    },
    "sub": {
        "lat": 7.5245, "lng": 4.5203, 
        "name": "Student Union Building (SUB)",
        "type": "building",
        "description": "Student activities center"
    },
    "oduduwa_hall": {
        "lat": 7.5234, "lng": 4.5189, 
        "name": "Oduduwa Hall",
        "type": "hall",
        "description": "Main auditorium"
    },
    
    # Academic Buildings
    "futa": {
        "lat": 7.5256, "lng": 4.5210,
        "name": "Faculty of Technology",
        "type": "faculty",
        "description": "Engineering and Technology faculty"
    },
    "science_complex": {
        "lat": 7.5240, "lng": 4.5220,
        "name": "Science Complex",
        "type": "faculty", 
        "description": "Pure and Applied Sciences"
    },
    "arts_theatre": {
        "lat": 7.5230, "lng": 4.5180,
        "name": "Arts Theatre",
        "type": "theatre",
        "description": "Creative Arts faculty"
    },
    
    # Student Hostels
    "mozambique_hostel": {
        "lat": 7.5280, "lng": 4.5167, 
        "name": "Mozambique Hostel",
        "type": "hostel",
        "description": "Student accommodation"
    },
    "angola_hostel": {
        "lat": 7.5289, "lng": 4.5134, 
        "name": "Angola Hostel",
        "type": "hostel",
        "description": "Student accommodation"
    },
    "madagascar_hostel": {
        "lat": 7.5295, "lng": 4.5145,
        "name": "Madagascar Hostel", 
        "type": "hostel",
        "description": "Student accommodation"
    },
    "awolowo_hall": {
        "lat": 7.5270, "lng": 4.5150,
        "name": "Awolowo Hall",
        "type": "hostel",
        "description": "Premier student hall"
    },
    
    # Essential Services
    "sports_complex": {
        "lat": 7.5198, "lng": 4.5234, 
        "name": "Sports Complex",
        "type": "sports",
        "description": "Sports and recreational facilities"
    },
    "teaching_hospital": {
        "lat": 7.5345, "lng": 4.5123, 
        "name": "OAU Teaching Hospital (OAUTHC)",
        "type": "hospital",
        "description": "Medical center"
    },
    "central_library": {
        "lat": 7.5250, "lng": 4.5200,
        "name": "Hezekiah Oluwasanmi Library",
        "type": "library",
        "description": "Main university library"
    },
    
    # Gates and Entrances
    "back_gate": {
        "lat": 7.5320, "lng": 4.5180,
        "name": "Back Gate",
        "type": "entrance",
        "description": "Secondary campus entrance"
    },
    "coop_gate": {
        "lat": 7.5200, "lng": 4.5280,
        "name": "Cooperative Gate", 
        "type": "entrance",
        "description": "Residential area entrance"
    },
    
    # Popular Spots
    "buka_junction": {
        "lat": 7.5260, "lng": 4.5190,
        "name": "Buka Junction",
        "type": "food",
        "description": "Popular food court area"
    },
    "atm_point": {
        "lat": 7.5235, "lng": 4.5195,
        "name": "Banking Complex",
        "type": "service",
        "description": "ATMs and banking services"
    },
    "chapel_of_wisdom": {
        "lat": 7.5225, "lng": 4.5175,
        "name": "Chapel of Wisdom",
        "type": "religious",
        "description": "University chapel"
    }
}

def get_nearest_landmark(latitude: float, longitude: float, max_distance: float = 1.0) -> str:
    """
    Get the nearest campus landmark to given coordinates
    Args:
        latitude: Current latitude
        longitude: Current longitude  
        max_distance: Maximum distance in km to consider (default 1km)
    """
    min_distance = float('inf')
    nearest_landmark = "Unknown Location"
    nearest_info = None
    
    for landmark_id, landmark_data in OAU_LANDMARKS.items():
        distance = calculate_distance(
            latitude, longitude,
            landmark_data["lat"], landmark_data["lng"]
        )
        
        if distance < min_distance and distance <= max_distance:
            min_distance = distance
            nearest_landmark = landmark_data["name"]
            nearest_info = {
                "name": landmark_data["name"],
                "type": landmark_data["type"],
                "distance": round(distance * 1000, 0),  # Convert to meters
                "description": landmark_data["description"]
            }
    
    if nearest_info:
        if nearest_info["distance"] < 50:  # Less than 50 meters
            return f"At {nearest_landmark}"
        elif nearest_info["distance"] < 200:  # Less than 200 meters
            return f"Near {nearest_landmark}"
        else:
            return f"Close to {nearest_landmark} ({int(nearest_info['distance'])}m)"
    
    return "On Campus (Location Unknown)"

def get_landmarks_by_type(landmark_type: str) -> List[Dict]:
    """Get all landmarks of a specific type"""
    return [
        {**landmark_data, "id": landmark_id}
        for landmark_id, landmark_data in OAU_LANDMARKS.items()
        if landmark_data["type"] == landmark_type
    ]

def get_nearby_landmarks(latitude: float, longitude: float, radius: float = 0.5) -> List[Dict]:
    """
    Get all landmarks within specified radius
    Args:
        latitude: Center latitude
        longitude: Center longitude
        radius: Search radius in kilometers
    """
    nearby = []
    
    for landmark_id, landmark_data in OAU_LANDMARKS.items():
        distance = calculate_distance(
            latitude, longitude,
            landmark_data["lat"], landmark_data["lng"]
        )
        
        if distance <= radius:
            nearby.append({
                **landmark_data,
                "id": landmark_id,
                "distance": round(distance * 1000, 0)  # Distance in meters
            })
    
    # Sort by distance
    nearby.sort(key=lambda x: x["distance"])
    return nearby

def validate_coordinates(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Comprehensive coordinate validation
    Returns validation result with details
    """
    result = {
        "valid": False,
        "within_campus": False,
        "nearest_landmark": None,
        "distance_from_center": None,
        "zone": None,
        "errors": []
    }
    
    # Basic coordinate validation
    if not (-90 <= latitude <= 90):
        result["errors"].append("Invalid latitude: must be between -90 and 90")
    
    if not (-180 <= longitude <= 180):
        result["errors"].append("Invalid longitude: must be between -180 and 180")
        
    if result["errors"]:
        return result
    
    # Check if within campus
    result["within_campus"] = is_within_oau_campus(latitude, longitude)
    result["distance_from_center"] = calculate_distance(
        latitude, longitude, 
        settings.OAU_CENTER_LAT, settings.OAU_CENTER_LNG
    )
    
    if result["within_campus"]:
        result["valid"] = True
        result["nearest_landmark"] = get_nearest_landmark(latitude, longitude)
        result["zone"] = determine_campus_zone(latitude, longitude)
    else:
        result["errors"].append("Location is outside OAU campus boundaries")
    
    return result

def determine_campus_zone(latitude: float, longitude: float) -> str:
    """Determine which zone of campus the coordinates fall into"""
    # Academic zone (center-south)
    if (7.5200 <= latitude <= 7.5260 and 4.5180 <= longitude <= 4.5230):
        return "Academic Zone"
    
    # Hostel zone (north)
    elif (7.5260 <= latitude <= 7.5320 and 4.5120 <= longitude <= 4.5180):
        return "Student Residential Zone"
    
    # Medical zone (northeast)
    elif (7.5320 <= latitude <= 7.5380 and 4.5100 <= longitude <= 4.5150):
        return "Medical Zone"
    
    # Sports/Recreation zone (south)
    elif (7.5180 <= latitude <= 7.5220 and 4.5220 <= longitude <= 4.5280):
        return "Sports & Recreation Zone"
    
    else:
        return "General Campus Area"