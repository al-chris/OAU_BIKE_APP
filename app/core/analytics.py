import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func, and_
import json

from app.models.location import LocationUpdate, BikeAvailability
from app.models.user import UserSession, UserRole
from app.models.emergency import EmergencyAlert
from app.core.geofencing import OAU_LANDMARKS, get_nearest_landmark, determine_campus_zone

class CampusAnalytics:
    def __init__(self):
        self.cache = {}
        self.cache_expiry = {}
    
    async def get_real_time_stats(self, db: AsyncSession) -> Dict:
        """Get current real-time campus transportation statistics"""
        now = datetime.now(timezone.utc)
        active_cutoff = now - timedelta(minutes=5)
        
        # Active sessions count
        active_sessions_result = await db.execute(
            select(func.count(UserSession.id))
            .where(
                and_(
                    UserSession.is_active == True,
                    UserSession.last_seen >= active_cutoff
                )
            )
        )
        total_active = active_sessions_result.scalar_one_or_none() or 0
        
        # Role breakdown
        drivers_result = await db.execute(
            select(func.count(UserSession.id))
            .where(
                and_(
                    UserSession.is_active == True,
                    UserSession.last_seen >= active_cutoff,
                    UserSession.role == UserRole.DRIVER
                )
            )
        )
        active_drivers = drivers_result.scalar_one_or_none() or 0
        
        passengers_result = await db.execute(
            select(func.count(UserSession.id))
            .where(
                and_(
                    UserSession.is_active == True,
                    UserSession.last_seen >= active_cutoff,
                    UserSession.role == UserRole.PASSENGER
                )
            )
        )
        active_passengers = passengers_result.scalar_one_or_none() or 0
        
        # Bike availability stats
        bike_stats = await self._get_bike_availability_stats(db)
        
        return {
            "timestamp": now.isoformat(),
            "active_users": {
                "total": total_active,
                "drivers": active_drivers,
                "passengers": active_passengers,
                "ratio": round(active_passengers / max(active_drivers, 1), 2)
            },
            "bike_availability": bike_stats,
            "peak_hours": await self._identify_peak_hours(db),
            "popular_locations": await self._get_popular_locations(db)
        }
    
    async def get_demand_patterns(
        self, 
        db: AsyncSession, 
        days_back: int = 7
    ) -> Dict:
        """Analyze passenger demand patterns over time"""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)
        
        # Hourly demand pattern
        hourly_demand = await self._analyze_hourly_demand(db, start_date, end_date)
        
        # Daily demand pattern
        daily_demand = await self._analyze_daily_demand(db, start_date, end_date)
        
        # Location-based demand
        location_demand = await self._analyze_location_demand(db, start_date, end_date)
        
        # Predictive insights
        predictions = await self._generate_demand_predictions(db)
        
        return {
            "analysis_period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days_back
            },
            "hourly_patterns": hourly_demand,
            "daily_patterns": daily_demand,
            "location_patterns": location_demand,
            "predictions": predictions,
            "insights": await self._generate_insights(hourly_demand, daily_demand, location_demand)
        }
    
    async def get_campus_heatmap_data(
        self, 
        db: AsyncSession,
        time_range: int = 60  # minutes
    ) -> Dict[str, Any]:
        """Generate heatmap data for campus activity"""
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=time_range)
        
        # Get location updates within time range
        location_result = await db.execute(
            select(LocationUpdate)
            .where(LocationUpdate.timestamp >= start_time)
        )
        locations = location_result.scalars().all()
        
        # Group locations by zones and landmarks
        zone_activity = {}
        landmark_activity = {}
        
        for location in locations:
            # Zone activity
            zone = determine_campus_zone(location.latitude, location.longitude)
            zone_activity[zone] = zone_activity.get(zone, 0) + 1
            
            # Landmark activity
            landmark = get_nearest_landmark(location.latitude, location.longitude)
            landmark_activity[landmark] = landmark_activity.get(landmark, 0) + 1
        
        # Generate heatmap points
        heatmap_points = []
        for location in locations:
            heatmap_points.append({
                "lat": location.latitude,
                "lng": location.longitude,
                "intensity": 1,
                "timestamp": location.timestamp.isoformat()
            })
        
        return {
            "time_range_minutes": time_range,
            "total_data_points": len(locations),
            "zone_activity": zone_activity,
            "landmark_activity": landmark_activity,
            "heatmap_points": heatmap_points,
            "activity_summary": {
                "most_active_zone": max(zone_activity.items(), key=lambda x: x[1])[0] if zone_activity else None,
                "most_active_landmark": max(landmark_activity.items(), key=lambda x: x[1])[0] if landmark_activity else None
            }
        }
    
    async def get_safety_analytics(self, db: AsyncSession) -> Dict[str, Any]:
        """Analyze safety-related metrics and emergency patterns"""
        # Emergency alerts in last 30 days
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        
        emergency_result = await db.execute(
            select(EmergencyAlert)
            .where(EmergencyAlert.created_at >= thirty_days_ago)
        )
        recent_emergencies = list(emergency_result.scalars().all())
        
        # Emergency patterns
        emergency_by_type = {}
        emergency_by_location = {}
        emergency_by_hour = {}
        
        for alert in recent_emergencies:
            # By type
            emergency_by_type[alert.alert_type] = emergency_by_type.get(alert.alert_type, 0) + 1
            
            # By location
            location = get_nearest_landmark(alert.latitude, alert.longitude)
            emergency_by_location[location] = emergency_by_location.get(location, 0) + 1
            
            # By hour
            hour = alert.created_at.hour
            emergency_by_hour[hour] = emergency_by_hour.get(hour, 0) + 1
        
        # Safety score calculation
        safety_score = await self._calculate_safety_score(db, recent_emergencies)
        
        return {
            "period_days": 30,
            "total_emergencies": len(recent_emergencies),
            "emergency_patterns": {
                "by_type": emergency_by_type,
                "by_location": emergency_by_location,
                "by_hour": emergency_by_hour
            },
            "safety_metrics": {
                "safety_score": safety_score,
                "response_rate": self._calculate_response_rate(recent_emergencies),
                "resolution_time": self._calculate_avg_resolution_time(recent_emergencies)
            },
            "recommendations": await self._generate_safety_recommendations(emergency_by_location, emergency_by_hour)
        }
    
    async def _get_bike_availability_stats(self, db: AsyncSession) -> Dict:
        """Get current bike availability statistics across campus"""
        recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        
        availability_result = await db.execute(
            select(LocationUpdate.bike_availability, func.count(LocationUpdate.id))
            .where(
                and_(
                    LocationUpdate.timestamp >= recent_cutoff,
                    LocationUpdate.bike_availability != None
                )
            )
            .group_by(LocationUpdate.bike_availability)
        )
        
        availability_data = availability_result.scalars().all()
        total_reports = sum(count for _, count in availability_data)
        
        if total_reports == 0:
            return {"status": "no_recent_data"}
        
        stats = {}
        for availability, count in availability_data:
            stats[availability.value] = {
                "count": count,
                "percentage": round((count / total_reports) * 100, 1)
            }
        
        return {
            "total_reports": total_reports,
            "distribution": stats,
            "overall_status": self._determine_overall_bike_status(stats)
        }
    
    async def _identify_peak_hours(self, db: AsyncSession) -> List[Dict]:
        """Identify peak usage hours"""
        # Get last 7 days of data
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        
        hourly_result = await db.execute(
            select(
                func.extract('hour', LocationUpdate.timestamp).label('hour'),
                func.count(LocationUpdate.id).label('activity_count')
            )
            .where(LocationUpdate.timestamp >= week_ago)
            .group_by(func.extract('hour', LocationUpdate.timestamp))
            .order_by('activity_count desc')
        )
        
        hourly_data = hourly_result.scalars().all()
        
        return [
            {
                "hour": int(hour),
                "activity_count": count,
                "time_range": f"{int(hour):02d}:00-{int(hour)+1:02d}:00"
            }
            for hour, count in hourly_data[:5]  # Top 5 peak hours
        ]
    
    async def _get_popular_locations(self, db: AsyncSession) -> List[Dict]:
        """Get most popular campus locations"""
        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        
        location_result = await db.execute(
            select(LocationUpdate)
            .where(LocationUpdate.timestamp >= recent_cutoff)
        )
        locations = location_result.scalars().all()
        
        landmark_count = {}
        for location in locations:
            landmark = get_nearest_landmark(location.latitude, location.longitude)
            landmark_count[landmark] = landmark_count.get(landmark, 0) + 1
        
        # Sort by popularity
        popular_locations = sorted(
            landmark_count.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10]
        
        return [
            {
                "location": location,
                "activity_count": count,
                "percentage": round((count / len(locations)) * 100, 1) if locations else 0
            }
            for location, count in popular_locations
        ]
    
    async def _analyze_hourly_demand(
        self, 
        db: AsyncSession, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict:
        """Analyze demand patterns by hour of day"""
        passenger_result = await db.execute(
            select(
                func.extract('hour', UserSession.created_at).label('hour'),
                func.count(UserSession.id).label('passenger_count')
            )
            .where(
                and_(
                    UserSession.created_at >= start_date,
                    UserSession.created_at <= end_date,
                    UserSession.role == UserRole.PASSENGER
                )
            )
            .group_by(func.extract('hour', UserSession.created_at))
            .order_by('hour')
        )
        
        hourly_data = {int(hour): count for hour, count in passenger_result.scalars().all()}
        
        # Fill missing hours with 0
        complete_hourly = {hour: hourly_data.get(hour, 0) for hour in range(24)}
        
        return {
            "hourly_distribution": complete_hourly,
            "peak_hour": max(complete_hourly.items(), key=lambda x: x[1])[0],
            "lowest_hour": min(complete_hourly.items(), key=lambda x: x[1])[0],
            "average_hourly": sum(complete_hourly.values()) / 24
        }
    
    async def _analyze_daily_demand(
        self, 
        db: AsyncSession, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict:
        """Analyze demand patterns by day of week"""
        daily_result = await db.execute(
            select(
                func.extract('dow', UserSession.created_at).label('day_of_week'),
                func.count(UserSession.id).label('passenger_count')
            )
            .where(
                and_(
                    UserSession.created_at >= start_date,
                    UserSession.created_at <= end_date,
                    UserSession.role == UserRole.PASSENGER
                )
            )
            .group_by(func.extract('dow', UserSession.created_at))
            .order_by('day_of_week')
        )
        
        # Map day numbers to day names
        day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        daily_data = {day_names[int(day)]: count for day, count in daily_result.scalars().all()}
        
        return {
            "daily_distribution": daily_data,
            "busiest_day": max(daily_data.items(), key=lambda x: x[1])[0] if daily_data else None,
            "quietest_day": min(daily_data.items(), key=lambda x: x[1])[0] if daily_data else None
        }
    
    async def _analyze_location_demand(
        self, 
        db: AsyncSession, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict:
        """Analyze demand patterns by campus location"""
        location_result = await db.execute(
            select(LocationUpdate)
            .join(UserSession)
            .where(
                and_(
                    LocationUpdate.timestamp >= start_date,
                    LocationUpdate.timestamp <= end_date,
                    UserSession.role == UserRole.PASSENGER
                )
            )
        )
        
        locations = location_result.scalars().all()
        location_demand = {}
        zone_demand = {}
        
        for location in locations:
            # Landmark demand
            landmark = get_nearest_landmark(location.latitude, location.longitude)
            location_demand[landmark] = location_demand.get(landmark, 0) + 1
            
            # Zone demand
            zone = determine_campus_zone(location.latitude, location.longitude)
            zone_demand[zone] = zone_demand.get(zone, 0) + 1
        
        return {
            "location_distribution": dict(sorted(location_demand.items(), key=lambda x: x[1], reverse=True)),
            "zone_distribution": dict(sorted(zone_demand.items(), key=lambda x: x[1], reverse=True)),
            "hotspots": list(sorted(location_demand.items(), key=lambda x: x[1], reverse=True)[:5])
        }
    
    def _determine_overall_bike_status(self, stats: Dict) -> str:
        """Determine overall bike availability status"""
        if not stats:
            return "unknown"
        
        high_percentage = stats.get("high", {}).get("percentage", 0)
        medium_percentage = stats.get("medium", {}).get("percentage", 0)
        low_percentage = stats.get("low", {}).get("percentage", 0)
        none_percentage = stats.get("none", {}).get("percentage", 0)
        
        if high_percentage >= 50:
            return "excellent"
        elif high_percentage + medium_percentage >= 60:
            return "good"
        elif low_percentage + none_percentage >= 60:
            return "poor"
        else:
            return "moderate"
    
    async def _generate_demand_predictions(self, db: AsyncSession) -> Dict:
        """Generate simple demand predictions based on historical patterns"""
        # This is a simplified prediction model
        # In production, you might use more sophisticated ML models
        
        current_hour = datetime.now(timezone.utc).hour
        current_day = datetime.now(timezone.utc).strftime('%A')
        
        # Get historical data for same time
        historical_result = await db.execute(
            select(func.count(UserSession.id))
            .where(
                and_(
                    func.extract('hour', UserSession.created_at) == current_hour,
                    UserSession.role == UserRole.PASSENGER
                )
            )
        )
        
        historical_count = historical_result.scalar_one_or_none() or 0
        
        # Simple prediction based on historical average
        predicted_demand = "low"
        if historical_count > 20:
            predicted_demand = "high"
        elif historical_count > 10:
            predicted_demand = "medium"
        
        return {
            "next_hour_demand": predicted_demand,
            "confidence": "low",  # Simple model has low confidence
            "based_on": f"Historical data for {current_hour}:00 on {current_day}s",
            "recommendation": self._get_demand_recommendation(predicted_demand)
        }
    
    def _get_demand_recommendation(self, predicted_demand: str) -> str:
        """Get recommendation based on predicted demand"""
        recommendations = {
            "high": "More drivers needed. Consider incentivizing driver participation.",
            "medium": "Moderate activity expected. Current driver count should suffice.",
            "low": "Low demand period. Good time for driver breaks or maintenance."
        }
        return recommendations.get(predicted_demand, "Monitor situation closely.")
    
    async def _generate_insights(self, hourly: Dict, daily: Dict, location: Dict) -> List[str]:
        """Generate actionable insights from demand patterns"""
        insights = []
        
        # Peak hour insight
        if hourly.get("peak_hour") is not None:
            peak_hour = hourly["peak_hour"]
            insights.append(f"Peak demand occurs at {peak_hour:02d}:00. Consider increasing driver availability during this time.")
        
        # Day pattern insight
        if daily.get("busiest_day"):
            busiest_day = daily["busiest_day"]
            insights.append(f"{busiest_day} shows highest demand. Plan driver schedules accordingly.")
        
        # Location insight
        if location.get("hotspots"):
            top_location = location["hotspots"][0][0]
            insights.append(f"'{top_location}' is the most popular pickup location. Consider strategic driver positioning.")
        
        return insights
    
    async def _calculate_safety_score(self, db: AsyncSession, recent_emergencies: List) -> float:
        """Calculate campus safety score based on various metrics"""
        base_score = 100.0
        
        # Deduct points for emergencies
        emergency_penalty = len(recent_emergencies) * 5
        
        # Deduct more for unresolved emergencies
        unresolved_count = sum(1 for alert in recent_emergencies if not alert.is_resolved)
        unresolved_penalty = unresolved_count * 10
        
        # Deduct for response time (simplified)
        response_penalty = 0  # Would need more complex calculation
        
        safety_score = max(0, base_score - emergency_penalty - unresolved_penalty - response_penalty)
        return round(safety_score, 1)
    
    def _calculate_response_rate(self, emergencies: List) -> float:
        """Calculate emergency response rate"""
        if not emergencies:
            return 100.0
        
        responded_count = sum(1 for alert in emergencies if alert.authorities_notified)
        return round((responded_count / len(emergencies)) * 100, 1)
    
    def _calculate_avg_resolution_time(self, emergencies: List) -> Optional[float]:
        """Calculate average emergency resolution time in minutes"""
        resolved_emergencies = [alert for alert in emergencies if alert.is_resolved and alert.resolved_at]
        
        if not resolved_emergencies:
            return None
        
        total_resolution_time = 0
        for alert in resolved_emergencies:
            resolution_time = (alert.resolved_at - alert.created_at).total_seconds() / 60
            total_resolution_time += resolution_time
        
        return round(total_resolution_time / len(resolved_emergencies), 1)
    
    async def _generate_safety_recommendations(self, location_patterns: Dict, hour_patterns: Dict) -> List[str]:
        """Generate safety recommendations based on emergency patterns"""
        recommendations = []
        
        # Location-based recommendations
        if location_patterns:
            most_incident_location = max(location_patterns.items(), key=lambda x: x[1])
            recommendations.append(
                f"Increase security presence at {most_incident_location[0]} - highest incident location."
            )
        
        # Time-based recommendations
        if hour_patterns:
            peak_incident_hour = max(hour_patterns.items(), key=lambda x: x[1])
            recommendations.append(
                f"Enhanced monitoring needed around {peak_incident_hour[0]:02d}:00 - peak incident time."
            )
        
        # General recommendations
        recommendations.extend([
            "Ensure emergency contacts are updated and responsive.",
            "Regular safety awareness campaigns for app users.",
            "Consider installing emergency beacons at high-incident locations."
        ])
        
        return recommendations

# Global analytics instance
campus_analytics = CampusAnalytics()