"""
Delay Prediction Engine for Swiss Transport App.

Uses road traffic data (situations, traffic lights) to predict delays
for bus and tram services along their routes.

Prediction rules are based on:
1. Traffic situations (accidents, roadworks) near route
2. Traffic light congestion (Level of Service, spillback length)
3. Peak hour considerations (5:45-7:00 and 16:30-18:00)
4. Historical patterns (simplified heuristics)
"""
from datetime import datetime, time
from typing import List, Tuple, Optional
import logging

from models import (
    DelayPrediction, TripLeg, TransportMode,
    TrafficSituation, TrafficLightStatus
)
from traffic_client import get_traffic_near_route

logger = logging.getLogger(__name__)

# Peak hour definitions (local time)
MORNING_PEAK_START = time(5, 45)
MORNING_PEAK_END = time(7, 0)
EVENING_PEAK_START = time(16, 30)
EVENING_PEAK_END = time(18, 0)

# Prediction horizon (minutes)
PREDICTION_HORIZON = 15

# Delay prediction rules (in minutes)
RULES = {
    # Traffic situation severity impacts
    'situation_severe': 8,      # Severe incident (accident, major roadwork)
    'situation_moderate': 4,    # Moderate incident
    'situation_minor': 2,       # Minor incident

    # Traffic light impacts based on Level of Service
    'los_f': 6,                 # LOS F (worst) - severe congestion
    'los_e': 4,                 # LOS E - significant delays
    'los_d': 2,                 # LOS D - moderate delays
    'los_c': 1,                 # LOS C - minor delays
    'los_ab': 0,                # LOS A-B - free flow

    # Spillback length impacts (per 100m)
    'spillback_per_100m': 1,

    # Peak hour multiplier
    'peak_multiplier': 1.5,

    # Base delay for buses/trams (slight inherent variability)
    'base_bus': 1,
    'base_tram': 0.5,
}

# Confidence adjustments
CONFIDENCE = {
    'base': 0.7,                    # Base confidence
    'with_traffic_data': 0.15,      # Boost if we have traffic data
    'with_light_data': 0.1,         # Boost if we have traffic light data
    'peak_hour_penalty': -0.1,      # Reduced confidence during peak
    'no_data_penalty': -0.3,        # Penalty if no traffic data
}


def is_peak_hour(dt: datetime) -> bool:
    """Check if given datetime is within peak hours."""
    t = dt.time()
    return (MORNING_PEAK_START <= t <= MORNING_PEAK_END) or \
           (EVENING_PEAK_START <= t <= EVENING_PEAK_END)


def get_los_delay(los: Optional[str]) -> int:
    """Get delay contribution from Level of Service."""
    if not los:
        return 0

    los_upper = los.upper()
    if los_upper == 'F':
        return RULES['los_f']
    elif los_upper == 'E':
        return RULES['los_e']
    elif los_upper == 'D':
        return RULES['los_d']
    elif los_upper == 'C':
        return RULES['los_c']
    else:
        return RULES['los_ab']


def get_situation_delay(severity: str) -> int:
    """Get delay contribution from traffic situation severity."""
    severity_lower = severity.lower()
    if 'severe' in severity_lower or 'danger' in severity_lower:
        return RULES['situation_severe']
    elif 'moderate' in severity_lower or 'normal' in severity_lower:
        return RULES['situation_moderate']
    else:
        return RULES['situation_minor']


def get_spillback_delay(spillback_meters: Optional[float]) -> int:
    """Get delay contribution from spillback length."""
    if not spillback_meters or spillback_meters <= 0:
        return 0
    return int((spillback_meters / 100) * RULES['spillback_per_100m'])


async def predict_delay_for_leg(
    leg: TripLeg,
    prediction_time: Optional[datetime] = None
) -> Optional[DelayPrediction]:
    """
    Predict delay for a single trip leg.

    Only predicts for bus and tram modes, as these are affected by road traffic.
    Rail, funicular, etc. are not affected by road traffic.
    """
    # Only predict for road-based transport
    if leg.mode not in [TransportMode.BUS, TransportMode.TRAM]:
        return None

    now = prediction_time or datetime.utcnow()
    departure = leg.origin.scheduled_time

    # Check if prediction is within horizon
    time_to_departure = (departure - now).total_seconds() / 60
    if time_to_departure < 0 or time_to_departure > PREDICTION_HORIZON:
        # Still provide prediction but with lower confidence
        pass

    # Collect route points for traffic lookup
    route_points: List[Tuple[float, float]] = []

    if leg.origin.latitude and leg.origin.longitude:
        route_points.append((leg.origin.latitude, leg.origin.longitude))

    for stop in leg.intermediate_stops:
        if stop.latitude and stop.longitude:
            route_points.append((stop.latitude, stop.longitude))

    if leg.destination.latitude and leg.destination.longitude:
        route_points.append((leg.destination.latitude, leg.destination.longitude))

    # Initialize prediction
    total_delay = 0
    factors = []
    confidence = CONFIDENCE['base']

    # Apply base delay for mode
    if leg.mode == TransportMode.BUS:
        total_delay += RULES['base_bus']
        factors.append("Bus service variability")
    else:
        total_delay += RULES['base_tram']
        factors.append("Tram service variability")

    # Check if we have route coordinates for traffic lookup
    if route_points:
        try:
            situations, lights = await get_traffic_near_route(route_points, radius_km=0.3)

            # Process traffic situations
            if situations:
                confidence += CONFIDENCE['with_traffic_data']
                for sit in situations:
                    delay_contrib = get_situation_delay(sit.severity)
                    if delay_contrib > 0:
                        total_delay += delay_contrib
                        factors.append(f"Traffic: {sit.description[:50]}...")

            # Process traffic lights
            if lights:
                confidence += CONFIDENCE['with_light_data']
                for light in lights:
                    # LOS contribution
                    los_delay = get_los_delay(light.level_of_service)
                    if los_delay > 0:
                        total_delay += los_delay
                        factors.append(f"Congestion at {light.name or light.intersection_id}")

                    # Spillback contribution
                    spillback_delay = get_spillback_delay(light.spillback_length_meters)
                    if spillback_delay > 0:
                        total_delay += spillback_delay
                        factors.append(f"Queue at {light.name or light.intersection_id}")

        except Exception as e:
            logger.warning(f"Error getting traffic data for prediction: {e}")
            confidence += CONFIDENCE['no_data_penalty']
            factors.append("Limited traffic data available")
    else:
        confidence += CONFIDENCE['no_data_penalty']
        factors.append("No coordinates available for traffic lookup")

    # Apply peak hour multiplier
    is_peak = is_peak_hour(departure)
    if is_peak:
        total_delay = int(total_delay * RULES['peak_multiplier'])
        confidence += CONFIDENCE['peak_hour_penalty']
        factors.append("Peak hour traffic")

    # Ensure confidence is within bounds
    confidence = max(0.1, min(1.0, confidence))

    # Round delay to nearest minute
    total_delay = max(0, round(total_delay))

    return DelayPrediction(
        predicted_delay_minutes=total_delay,
        confidence_score=round(confidence, 2),
        factors=factors[:5],  # Limit to top 5 factors
        is_peak_hour=is_peak,
        prediction_time=now
    )


async def predict_delays_for_trip(
    legs: List[TripLeg],
    prediction_time: Optional[datetime] = None
) -> List[Tuple[int, Optional[DelayPrediction]]]:
    """
    Predict delays for all legs in a trip.

    Returns list of (leg_index, prediction) tuples.
    Only bus/tram legs will have predictions.
    """
    results = []
    now = prediction_time or datetime.utcnow()

    for idx, leg in enumerate(legs):
        prediction = await predict_delay_for_leg(leg, now)
        results.append((idx, prediction))

    return results
