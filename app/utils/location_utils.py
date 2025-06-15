import asyncio
import math
import json
from typing import List, Dict, Tuple, Optional, Union
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from enum import Enum

import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, desc, and_, or_, func

from app.models.location import LocationUpdate, BikeAvailability
from app.models.user import UserSession, UserRole
from app.core.geofencing import (
    calculate_distance, 
    get_nearest_landmark, 
    determine_campus_zone,
    OAU_LANDMARKS
)

class LocationAccuracy(str, Enum):
    HIGH = "high"      # < 10 meters
    MEDIUM = "medium"  # 10-50 meters  
    LOW = "low"        # > 50 meters
    UNKNOWN = "unknown"

@dataclass
class LocationPoint:
    """Structured location data point"""
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    timestamp: Optional[datetime] = None
    altitude: Optional[float] = None
    heading: Optional[float] = None
    speed: Optional[float] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
    
    @property
    def accuracy_level(self) -> LocationAccuracy:
        """Determine accuracy level based on accuracy value"""
        if self.accuracy is None:
            return LocationAccuracy.UNKNOWN
        elif self.accuracy < 10:
            return LocationAccuracy.HIGH
        elif self.accuracy < 50:
            return LocationAccuracy.MEDIUM
        else:
            return LocationAccuracy.LOW
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "accuracy": self.accuracy,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "altitude": self.altitude,
            "heading": self.heading,
            "speed": self.speed,
            "accuracy_level": self.accuracy_level.value
        }

class LocationCluster:
    """Represent a cluster of nearby locations"""
    
    def __init__(self, center_lat: float, center_lng: float, radius: float = 100):
        self.center_lat = center_lat
        self.center_lng = center_lng
        self.radius = radius  # meters
        self.locations: List[LocationPoint] = []
        self.user_count = 0
        self.last_updated = datetime.now(timezone.utc)
    
    def add_location(self, location: LocationPoint):
        """Add location to cluster"""
        distance = calculate_distance(
            location.latitude, location.longitude,
            self.center_lat, self.center_lng
        ) * 1000  # Convert to meters
        
        if distance <= self.radius:
            self.locations.append(location)
            self.user_count += 1
            self.last_updated = datetime.now(timezone.utc)
            return True
        return False
    
    def get_density(self) -> float:
        """Calculate user density (users per square meter)"""
        area = math.pi * (self.radius ** 2)
        return self.user_count / area if area > 0 else 0
    
    def to_dict(self) -> Dict:
        """Convert cluster to dictionary"""
        return {
            "center": {"lat": self.center_lat, "lng": self.center_lng},
            "radius": self.radius,
            "user_count": self.user_count,
            "density": self.get_density(),
            "last_updated": self.last_updated.isoformat(),
            "locations": [loc.to_dict() for loc in self.locations[-10:]]  # Last 10 locations
        }

class LocationService:
    """Advanced location processing and analysis service"""
    
    def __init__(self):
        self.location_cache = {}
        self.cluster_cache = {}
        self.route_cache = {}
    
    async def process_location_update(
        self,
        session_id: str,
        location: LocationPoint,
        bike_availability: Optional[BikeAvailability] = None,
        db: Optional[AsyncSession] = None
    ) -> Dict:
        """
        Process and enrich location update with additional context
        
        Returns:
            Enriched location data with landmarks, zones, and recommendations
        """
        try:
            # Basic location validation
            if not self._is_valid_location(location):
                raise ValueError("Invalid location coordinates")
            
            # Get location context
            context = await self._get_location_context(location)
            
            # Analyze nearby activity
            nearby_activity = await self._analyze_nearby_activity(location, db) if db else {}
            
            # Get movement pattern (if historical data available)
            movement_pattern = await self._analyze_movement_pattern(session_id, location, db) if db else {}
            
            # Generate recommendations
            recommendations = await self._generate_location_recommendations(
                location, context, nearby_activity, bike_availability
            )
            
            # Cache location for future analysis
            self._cache_location(session_id, location)
            
            return {
                "location": location.to_dict(),
                "context": context,
                "nearby_activity": nearby_activity,
                "movement_pattern": movement_pattern,
                "recommendations": recommendations,
                "processed_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "location": location.to_dict(),
                "processed_at": datetime.now(timezone.utc).isoformat()
            }
    
    async def get_optimal_pickup_locations(
        self,
        passenger_location: LocationPoint,
        max_distance: float = 1000,  # meters
        db: Optional[AsyncSession] = None
    ) -> List[Dict]:
        """
        Find optimal pickup locations based on driver availability and accessibility
        
        Args:
            passenger_location: Passenger's current location
            max_distance: Maximum search distance in meters
            db: Database session for real-time data
        """
        try:
            optimal_locations = []
            
            # Get nearby landmarks as potential pickup points
            nearby_landmarks = self._get_landmarks_within_radius(
                passenger_location, max_distance
            )
            
            # Get current driver locations if DB available
            if db:
                driver_locations = await self._get_nearby_drivers(
                    passenger_location, max_distance, db
                )
            else:
                driver_locations = []
            
            # Analyze each potential pickup location
            for landmark in nearby_landmarks:
                location_score = await self._calculate_pickup_score(
                    landmark, passenger_location, driver_locations
                )
                
                optimal_locations.append({
                    "landmark": landmark,
                    "score": location_score["total_score"],
                    "distance": location_score["distance"],
                    "available_drivers": location_score["driver_count"],
                    "accessibility": location_score["accessibility"],
                    "safety_rating": location_score["safety"],
                    "estimated_wait_time": location_score["wait_time"]
                })
            
            # Sort by score (highest first)
            optimal_locations.sort(key=lambda x: x["score"], reverse=True)
            
            return optimal_locations[:10]  # Top 10 recommendations
            
        except Exception as e:
            return [{"error": str(e)}]
    
    async def generate_campus_activity_map(
        self,
        time_window: int = 60,  # minutes
        db: Optional[AsyncSession] = None
    ) -> Dict:
        """
        Generate real-time campus activity map with clusters and hotspots
        
        Args:
            time_window: Time window in minutes for activity analysis
            db: Database session
        """
        try:
            if not db:
                return {"error": "Database session required"}
            
            # Get recent location updates
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=time_window)
            
            location_result = await db.execute(
                select(LocationUpdate, UserSession.role)
                .join(UserSession)
                .where(
                    and_(
                        LocationUpdate.timestamp >= cutoff_time,
                        UserSession.is_active == True
                    )
                )
            )
            
            location_data = list(location_result.scalars().all())
            
            # Create location clusters
            clusters = self._create_location_clusters(location_data)
            
            # Identify hotspots
            hotspots = self._identify_activity_hotspots(location_data)
            
            # Calculate zone activity
            zone_activity = self._calculate_zone_activity(location_data)
            
            # Generate traffic flow analysis
            traffic_flow = await self._analyze_traffic_flow(location_data)
            
            return {
                "time_window_minutes": time_window,
                "total_active_users": len(location_data),
                "clusters": [cluster.to_dict() for cluster in clusters],
                "hotspots": hotspots,
                "zone_activity": zone_activity,
                "traffic_flow": traffic_flow,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def calculate_route_efficiency(
        self,
        start_location: LocationPoint,
        end_location: LocationPoint,
        waypoints: Optional[List[LocationPoint]] = None
    ) -> Dict:
        """
        Calculate route efficiency and provide optimization suggestions
        
        Args:
            start_location: Route starting point
            end_location: Route destination
            waypoints: Optional intermediate points
        """
        try:
            # Calculate direct distance
            direct_distance = calculate_distance(
                start_location.latitude, start_location.longitude,
                end_location.latitude, end_location.longitude
            )
            
            # Calculate route with waypoints if provided
            if waypoints:
                total_route_distance = 0
                current_point = start_location
                
                for waypoint in waypoints:
                    segment_distance = calculate_distance(
                        current_point.latitude, current_point.longitude,
                        waypoint.latitude, waypoint.longitude
                    )
                    total_route_distance += segment_distance
                    current_point = waypoint
                
                # Add final segment to destination
                final_segment = calculate_distance(
                    current_point.latitude, current_point.longitude,
                    end_location.latitude, end_location.longitude
                )
                total_route_distance += final_segment
            else:
                total_route_distance = direct_distance
            
            # Calculate efficiency metrics
            efficiency_ratio = direct_distance / total_route_distance if total_route_distance > 0 else 0
            detour_distance = total_route_distance - direct_distance
            detour_percentage = (detour_distance / direct_distance) * 100 if direct_distance > 0 else 0
            
            # Estimated travel time (assuming average bike speed of 15 km/h)
            estimated_time_minutes = (total_route_distance / 15) * 60
            
            # Generate route optimization suggestions
            suggestions = self._generate_route_suggestions(
                start_location, end_location, waypoints, efficiency_ratio
            )
            
            return {
                "direct_distance_km": round(direct_distance, 2),
                "route_distance_km": round(total_route_distance, 2),
                "detour_distance_km": round(detour_distance, 2),
                "detour_percentage": round(detour_percentage, 1),
                "efficiency_ratio": round(efficiency_ratio, 3),
                "estimated_time_minutes": round(estimated_time_minutes, 1),
                "efficiency_rating": self._get_efficiency_rating(efficiency_ratio),
                "suggestions": suggestions,
                "calculated_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _is_valid_location(self, location: LocationPoint) -> bool:
        """Validate location coordinates"""
        return (
            -90 <= location.latitude <= 90 and
            -180 <= location.longitude <= 180
        )
    
    async def _get_location_context(self, location: LocationPoint) -> Dict:
        """Get contextual information about a location"""
        try:
            # Get nearest landmark
            nearest_landmark = get_nearest_landmark(location.latitude, location.longitude)
            
            # Get campus zone
            campus_zone = determine_campus_zone(location.latitude, location.longitude)
            
            # Get nearby landmarks within 500m
            nearby_landmarks = self._get_landmarks_within_radius(location, 500)
            
            # Determine location type (academic, residential, recreational, etc.)
            location_type = self._determine_location_type(location)
            
            return {
                "nearest_landmark": nearest_landmark,
                "campus_zone": campus_zone,
                "nearby_landmarks": [lm["name"] for lm in nearby_landmarks[:5]],
                "location_type": location_type,
                "accessibility": self._assess_accessibility(location),
                "safety_features": self._identify_safety_features(location)
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _analyze_nearby_activity(
        self, 
        location: LocationPoint, 
        db: AsyncSession,
        radius: float = 500  # meters
    ) -> Dict:
        """Analyze activity in the vicinity of a location"""
        try:
            # Get recent activity within radius
            recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
            
            # This is a simplified query - in production you'd use PostGIS for spatial queries
            all_recent_locations = await db.execute(
                select(LocationUpdate, UserSession.role)
                .join(UserSession)
                .where(LocationUpdate.timestamp >= recent_cutoff)
            )
            
            nearby_locations = []
            for loc_update, user_role in all_recent_locations.scalars().all():
                distance = calculate_distance(
                    location.latitude, location.longitude,
                    loc_update.latitude, loc_update.longitude
                ) * 1000  # Convert to meters
                
                if distance <= radius:
                    nearby_locations.append({
                        "distance": distance,
                        "role": user_role,
                        "timestamp": loc_update.timestamp,
                        "bike_availability": loc_update.bike_availability
                    })
            
            # Analyze the nearby activity
            driver_count = sum(1 for loc in nearby_locations if loc["role"] == UserRole.DRIVER)
            passenger_count = sum(1 for loc in nearby_locations if loc["role"] == UserRole.PASSENGER)
            
            # Bike availability analysis
            bike_reports = [loc["bike_availability"] for loc in nearby_locations if loc["bike_availability"]]
            bike_status = self._analyze_bike_availability(bike_reports)
            
            return {
                "radius_meters": radius,
                "total_nearby_users": len(nearby_locations),
                "drivers_nearby": driver_count,
                "passengers_nearby": passenger_count,
                "driver_passenger_ratio": driver_count / max(passenger_count, 1),
                "bike_availability_status": bike_status,
                "activity_level": self._determine_activity_level(len(nearby_locations)),
                "last_activity": max([loc["timestamp"] for loc in nearby_locations]) if nearby_locations else None
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _analyze_movement_pattern(
        self,
        session_id: str,
        current_location: LocationPoint,
        db: AsyncSession
    ) -> Dict:
        """Analyze user's movement pattern"""
        try:
            # Get user's recent location history
            recent_locations = await db.execute(
                select(LocationUpdate)
                .where(LocationUpdate.session_id == session_id)
                .order_by(desc(LocationUpdate.timestamp))
                .limit(10)
            )
            
            locations = list(recent_locations.scalars().all())
            
            if len(locations) < 2:
                return {"status": "insufficient_data"}
            
            # Calculate movement metrics
            total_distance = 0
            speeds = []
            
            for i in range(len(locations) - 1):
                loc1 = locations[i]
                loc2 = locations[i + 1]
                
                distance = calculate_distance(
                    loc1.latitude, loc1.longitude,
                    loc2.latitude, loc2.longitude
                )
                
                time_diff = (loc1.timestamp - loc2.timestamp).total_seconds() / 3600  # hours
                speed = distance / time_diff if time_diff > 0 else 0
                
                total_distance += distance
                if speed < 50:  # Filter out unrealistic speeds
                    speeds.append(speed)
            
            avg_speed = sum(speeds) / len(speeds) if speeds else 0
            
            # Determine movement pattern
            movement_type = self._classify_movement_pattern(avg_speed, total_distance, len(locations))
            
            return {
                "total_distance_km": round(total_distance, 2),
                "average_speed_kmh": round(avg_speed, 1),
                "movement_type": movement_type,
                "location_changes": len(locations),
                "time_span_minutes": (locations[0].timestamp - locations[-1].timestamp).total_seconds() / 60,
                "is_stationary": avg_speed < 1,
                "estimated_mode": self._estimate_transport_mode(avg_speed)
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _generate_location_recommendations(
        self,
        location: LocationPoint,
        context: Dict,
        nearby_activity: Dict,
        bike_availability: Optional[BikeAvailability]
    ) -> List[str]:
        """Generate location-based recommendations for users"""
        recommendations = []
        
        try:
            # Recommendations based on bike availability
            if bike_availability == BikeAvailability.NONE:
                recommendations.append("No bikes available at current location. Consider moving to nearby landmarks.")
            elif bike_availability == BikeAvailability.LOW:
                recommendations.append("Limited bikes available. Book quickly or consider alternative locations.")
            elif bike_availability == BikeAvailability.HIGH:
                recommendations.append("Good bike availability at your location.")
            
            # Recommendations based on nearby activity
            if nearby_activity.get("drivers_nearby", 0) == 0:
                recommendations.append("No drivers nearby. You may experience longer wait times.")
            elif nearby_activity.get("driver_passenger_ratio", 0) > 2:
                recommendations.append("Good driver availability in your area.")
            
            # Recommendations based on location context
            location_type = context.get("location_type", "unknown")
            if location_type == "academic" and datetime.now(timezone.utc).hour in [8, 9, 16, 17]:
                recommendations.append("Peak academic hours - expect higher demand.")
            elif location_type == "residential" and datetime.now(timezone.utc).hour in [7, 8, 18, 19]:
                recommendations.append("Peak residential movement time - plan accordingly.")
            
            # Safety recommendations
            if datetime.now(timezone.utc).hour >= 20 or datetime.now(timezone.utc).hour <= 6:
                recommendations.append("Late hours - prioritize well-lit, populated pickup locations.")
            
            # Weather-based recommendations (simplified)
            # In production, you'd integrate with weather API
            recommendations.append("Check weather conditions before traveling.")
            
            return recommendations
            
        except Exception as e:
            return [f"Error generating recommendations: {str(e)}"]
    
    def _get_landmarks_within_radius(
        self, 
        location: LocationPoint, 
        radius_meters: float
    ) -> List[Dict]:
        """Get landmarks within specified radius"""
        nearby_landmarks = []
        
        for landmark_id, landmark_data in OAU_LANDMARKS.items():
            distance = calculate_distance(
                location.latitude, location.longitude,
                landmark_data["lat"], landmark_data["lng"]
            ) * 1000  # Convert to meters
            
            if distance <= radius_meters:
                nearby_landmarks.append({
                    **landmark_data,
                    "id": landmark_id,
                    "distance_meters": round(distance, 0)
                })
        
        # Sort by distance
        nearby_landmarks.sort(key=lambda x: x["distance_meters"])
        return nearby_landmarks
    
    async def _get_nearby_drivers(
        self,
        location: LocationPoint,
        radius_meters: float,
        db: AsyncSession
    ) -> List[Dict]:
        """Get nearby drivers within radius"""
        try:
            recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
            
            # Get active driver sessions
            driver_result = await db.execute(
                select(LocationUpdate, UserSession.id)
                .join(UserSession)
                .where(
                    and_(
                        UserSession.role == UserRole.DRIVER,
                        UserSession.is_active == True,
                        UserSession.last_seen >= recent_cutoff
                    )
                )
                .order_by(desc(LocationUpdate.timestamp))
            )
            
            nearby_drivers = []
            processed_sessions = set()
            
            for loc_update, session_id in driver_result.scalars().all():
                if session_id in processed_sessions:
                    continue
                
                distance = calculate_distance(
                    location.latitude, location.longitude,
                    loc_update.latitude, loc_update.longitude
                ) * 1000  # Convert to meters
                
                if distance <= radius_meters:
                    nearby_drivers.append({
                        "session_id": str(session_id),
                        "distance_meters": round(distance, 0),
                        "last_seen": loc_update.timestamp,
                        "location": {
                            "lat": loc_update.latitude,
                            "lng": loc_update.longitude
                        }
                    })
                    processed_sessions.add(session_id)
            
            return nearby_drivers
            
        except Exception as e:
            return []
    
    def _cache_location(self, session_id: str, location: LocationPoint):
        """Cache location for future analysis"""
        if session_id not in self.location_cache:
            self.location_cache[session_id] = []
        
        self.location_cache[session_id].append(location)
        
        # Keep only last 50 locations per session
        if len(self.location_cache[session_id]) > 50:
            self.location_cache[session_id] = self.location_cache[session_id][-50:]
    
    def _determine_location_type(self, location: LocationPoint) -> str:
        """Determine the type of location based on nearby landmarks"""
        nearby_landmarks = self._get_landmarks_within_radius(location, 200)
        
        if not nearby_landmarks:
            return "general"
        
        # Count landmark types
        type_counts = {}
        for landmark in nearby_landmarks:
            landmark_type = landmark.get("type", "unknown")
            type_counts[landmark_type] = type_counts.get(landmark_type, 0) + 1
        
        # Return most common type
        if type_counts:
            return max(type_counts.items(), key=lambda x: x[1])[0]
        
        return "general"
    
    def _assess_accessibility(self, location: LocationPoint) -> str:
        """Assess location accessibility (simplified)"""
        # In a real implementation, this would check:
        # - Road access
        # - Pedestrian paths
        # - Bike lane availability
        # - Terrain difficulty
        
        # For now, return based on proximity to major landmarks
        major_landmarks = self._get_landmarks_within_radius(location, 100)
        
        if len(major_landmarks) >= 2:
            return "high"
        elif len(major_landmarks) == 1:
            return "medium"
        else:
            return "low"
    
    def _identify_safety_features(self, location: LocationPoint) -> List[str]:
        """Identify safety features near location"""
        safety_features = []
        
        # Check proximity to well-lit areas (major landmarks are usually well-lit)
        nearby_landmarks = self._get_landmarks_within_radius(location, 150)
        
        for landmark in nearby_landmarks:
            if landmark["type"] in ["entrance", "building", "hospital"]:
                safety_features.append("Well-lit area nearby")
                break
        
        # Check for security presence
        security_landmarks = ["main_gate", "back_gate", "teaching_hospital", "sub"]
        for landmark in nearby_landmarks:
            if landmark["id"] in security_landmarks:
                safety_features.append("Security presence nearby")
                break
        
        # Check for populated areas
        if len(nearby_landmarks) >= 3:
            safety_features.append("Populated area")
        
        return list(set(safety_features))  # Remove duplicates
    
    def _analyze_bike_availability(self, bike_reports: List[BikeAvailability]) -> str:
        """Analyze bike availability from multiple reports"""
        if not bike_reports:
            return "unknown"
        
        # Count each availability level
        counts = {}
        for report in bike_reports:
            counts[report.value] = counts.get(report.value, 0) + 1
        
        # Return most common report
        if counts:
            return max(counts.items(), key=lambda x: x[1])[0]
        
        return "unknown"
    
    def _determine_activity_level(self, user_count: int) -> str:
        """Determine activity level based on user count"""
        if user_count >= 10:
            return "high"
        elif user_count >= 5:
            return "medium"
        elif user_count >= 1:
            return "low"
        else:
            return "none"
    
    def _classify_movement_pattern(
        self, 
        avg_speed: float, 
        total_distance: float, 
        location_count: int
    ) -> str:
        """Classify user movement pattern"""
        if avg_speed < 1 and total_distance < 0.1:
            return "stationary"
        elif avg_speed < 5:
            return "walking"
        elif 5 <= avg_speed <= 20:
            return "cycling"
        elif avg_speed > 20:
            return "vehicle"
        else:
            return "unknown"
    
    def _estimate_transport_mode(self, avg_speed: float) -> str:
        """Estimate mode of transportation"""
        if avg_speed < 2:
            return "on_foot"
        elif 2 <= avg_speed <= 8:
            return "bicycle"
        elif 8 <= avg_speed <= 25:
            return "motorcycle"
        elif avg_speed > 25:
            return "car"
        else:
            return "unknown"
    
    def _create_location_clusters(self, location_data: List) -> List[LocationCluster]:
        """Create location clusters from activity data"""
        clusters = []
        processed_locations = set()
        
        for i, (loc_update, user_role) in enumerate(location_data):
            if i in processed_locations:
                continue
            
            # Create new cluster
            cluster = LocationCluster(
                loc_update.latitude, 
                loc_update.longitude,
                radius=100  # 100 meter radius
            )
            
            location_point = LocationPoint(
                loc_update.latitude,
                loc_update.longitude,
                timestamp=loc_update.timestamp
            )
            cluster.add_location(location_point)
            processed_locations.add(i)
            
            # Add nearby locations to cluster
            for j, (other_loc, other_role) in enumerate(location_data):
                if j in processed_locations:
                    continue
                
                other_point = LocationPoint(
                    other_loc.latitude,
                    other_loc.longitude,
                    timestamp=other_loc.timestamp
                )
                
                if cluster.add_location(other_point):
                    processed_locations.add(j)
            
            # Only keep clusters with multiple users
            if cluster.user_count >= 2:
                clusters.append(cluster)
        
        return clusters
    
    def _identify_activity_hotspots(self, location_data: List) -> List[Dict]:
        """Identify activity hotspots"""
        # Group locations by landmarks
        landmark_activity = {}
        
        for loc_update, user_role in location_data:
            landmark = get_nearest_landmark(loc_update.latitude, loc_update.longitude)
            
            if landmark not in landmark_activity:
                landmark_activity[landmark] = {
                    "drivers": 0,
                    "passengers": 0,
                    "total": 0,
                    "locations": []
                }
            
            landmark_activity[landmark]["total"] += 1
            landmark_activity[landmark]["locations"].append({
                "lat": loc_update.latitude,
                "lng": loc_update.longitude,
                "role": user_role,
                "timestamp": loc_update.timestamp
            })
            
            if user_role == UserRole.DRIVER:
                landmark_activity[landmark]["drivers"] += 1
            else:
                landmark_activity[landmark]["passengers"] += 1
        
        # Convert to list and sort by activity
        hotspots = []
        for landmark, activity in landmark_activity.items():
            if activity["total"] >= 3:  # Minimum threshold for hotspot
                hotspots.append({
                    "landmark": landmark,
                    "total_activity": activity["total"],
                    "drivers": activity["drivers"],
                    "passengers": activity["passengers"],
                    "ratio": activity["drivers"] / max(activity["passengers"], 1),
                    "activity_level": self._determine_activity_level(activity["total"])
                })
        
        hotspots.sort(key=lambda x: x["total_activity"], reverse=True)
        return hotspots[:10]  # Top 10 hotspots
    
    def _calculate_zone_activity(self, location_data: List) -> Dict:
        """Calculate activity by campus zone"""
        zone_activity = {}
        
        for loc_update, user_role in location_data:
            zone = determine_campus_zone(loc_update.latitude, loc_update.longitude)
            
            if zone not in zone_activity:
                zone_activity[zone] = {"drivers": 0, "passengers": 0, "total": 0}
            
            zone_activity[zone]["total"] += 1
            if user_role == UserRole.DRIVER:
                zone_activity[zone]["drivers"] += 1
            else:
                zone_activity[zone]["passengers"] += 1
        
        return zone_activity
    
    async def _analyze_traffic_flow(self, location_data: List) -> Dict:
        """Analyze traffic flow patterns (simplified)"""
        # In a real implementation, this would analyze movement between zones
        # For now, return basic flow metrics
        
        total_movements = len(location_data)
        unique_locations = len(set((loc.latitude, loc.longitude) for loc, _ in location_data))
        
        return {
            "total_movements": total_movements,
            "unique_locations": unique_locations,
            "movement_density": total_movements / max(unique_locations, 1),
            "flow_analysis": "Basic flow analysis - upgrade needed for detailed patterns"
        }
    
    async def _calculate_pickup_score(
        self,
        landmark: Dict,
        passenger_location: LocationPoint,
        driver_locations: List[Dict]
    ) -> Dict:
        """Calculate pickup location score based on multiple factors"""
        
        # Distance score (closer is better)
        distance_km = landmark["distance_meters"] / 1000
        distance_score = max(0, 100 - (distance_km * 50))  # Penalize distant locations
        
        # Driver availability score
        nearby_drivers = sum(
            1 for driver in driver_locations 
            if driver["distance_meters"] <= 500  # Within 500m of landmark
        )
        driver_score = min(100, nearby_drivers * 25)  # Max 100 points
        
        # Accessibility score (based on landmark type)
        accessibility_scores = {
            "entrance": 90,
            "building": 80,
            "hall": 75,
            "faculty": 85,
            "hostel": 70,
            "sports": 60,
            "hospital": 95,
            "library": 85,
            "food": 65,
            "service": 70,
            "religious": 60
        }
        accessibility_score = accessibility_scores.get(landmark.get("type", "unknown"), 50)
        
        # Safety score (major landmarks are safer)
        safety_landmarks = ["main_gate", "sub", "teaching_hospital", "central_library"]
        safety_score = 90 if landmark.get("id") in safety_landmarks else 70
        
        # Calculate estimated wait time (simplified)
        if nearby_drivers > 0:
            wait_time = max(2, 10 - (nearby_drivers * 2))  # 2-8 minutes
        else:
            wait_time = 15  # 15 minutes if no nearby drivers
        
        # Total weighted score
        total_score = (
            distance_score * 0.3 +
            driver_score * 0.4 +
            accessibility_score * 0.2 +
            safety_score * 0.1
        )
        
        return {
            "total_score": round(total_score, 1),
            "distance": distance_km,
            "driver_count": nearby_drivers,
            "accessibility": accessibility_score,
            "safety": safety_score,
            "wait_time": wait_time
        }
    
    def _generate_route_suggestions(
        self,
        start: LocationPoint,
        end: LocationPoint,
        waypoints: Optional[List[LocationPoint]],
        efficiency_ratio: float
    ) -> List[str]:
        """Generate route optimization suggestions"""
        suggestions = []
        
        if efficiency_ratio < 0.8:
            suggestions.append("Route has significant detours. Consider optimizing waypoints.")
        
        if efficiency_ratio > 0.95:
            suggestions.append("Very efficient route with minimal detours.")
        
        # Distance-based suggestions
        direct_distance = calculate_distance(
            start.latitude, start.longitude,
            end.latitude, end.longitude
        )
        
        if direct_distance > 3:
            suggestions.append("Long distance route. Consider breaking into segments.")
        
        if waypoints and len(waypoints) > 5:
            suggestions.append("Many waypoints detected. Consider reducing stops for efficiency.")
        
        # Time-based suggestions
        current_hour = datetime.now(timezone.utc).hour
        if 7 <= current_hour <= 9 or 16 <= current_hour <= 18:
            suggestions.append("Peak hours detected. Allow extra travel time.")
        
        return suggestions
    
    def _get_efficiency_rating(self, efficiency_ratio: float) -> str:
        """Get efficiency rating based on ratio"""
        if efficiency_ratio >= 0.95:
            return "Excellent"
        elif efficiency_ratio >= 0.85:
            return "Good"
        elif efficiency_ratio >= 0.70:
            return "Fair"
        else:
            return "Poor"

# Global location service instance
location_service = LocationService()