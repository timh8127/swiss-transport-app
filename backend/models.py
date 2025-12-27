"""Data models for Swiss Transport App."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class TransportMode(str, Enum):
    """Transport mode types."""
    RAIL = "rail"
    BUS = "bus"
    TRAM = "tram"
    METRO = "metro"
    FUNICULAR = "funicular"
    FERRY = "ferry"
    CABLEWAY = "cableway"
    WALK = "walk"
    UNKNOWN = "unknown"


class LocationType(str, Enum):
    """Location type for search."""
    STOP = "stop"
    ADDRESS = "address"
    POI = "poi"
    COORDINATE = "coordinate"


# Request Models
class LocationSearchRequest(BaseModel):
    """Request for location search."""
    query: str = Field(..., min_length=2, description="Search query")
    limit: int = Field(default=10, ge=1, le=50)


class TripRequest(BaseModel):
    """Request for trip planning."""
    origin_id: str = Field(..., description="Origin stop ID (e.g., 8503000 for Zürich HB)")
    origin_name: str = Field(default="", description="Origin name for display")
    destination_id: str = Field(..., description="Destination stop ID")
    destination_name: str = Field(default="", description="Destination name for display")
    departure_time: Optional[datetime] = Field(default=None, description="Desired departure time")
    arrival_time: Optional[datetime] = Field(default=None, description="Desired arrival time")
    num_results: int = Field(default=5, ge=1, le=10)


# Response Models
class Location(BaseModel):
    """A location (stop, address, POI)."""
    id: str
    name: str
    type: LocationType
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    locality: Optional[str] = None


class StopPoint(BaseModel):
    """A stop point in a leg."""
    id: str
    name: str
    platform: Optional[str] = None
    scheduled_time: datetime
    estimated_time: Optional[datetime] = None
    delay_minutes: int = 0
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class TripLeg(BaseModel):
    """A single leg of a trip."""
    leg_id: str
    mode: TransportMode
    line_name: Optional[str] = None
    line_number: Optional[str] = None
    destination_text: Optional[str] = None  # e.g., "Direction: Zürich HB"
    operator: Optional[str] = None
    origin: StopPoint
    destination: StopPoint
    intermediate_stops: List[StopPoint] = []
    duration_minutes: int
    has_realtime: bool = False
    delay_prediction: Optional["DelayPrediction"] = None


class Trip(BaseModel):
    """A complete trip with multiple legs."""
    trip_id: str
    legs: List[TripLeg]
    departure_time: datetime
    arrival_time: datetime
    duration_minutes: int
    num_transfers: int
    has_disruptions: bool = False
    disruptions: List["Disruption"] = []


class TripSearchResult(BaseModel):
    """Result of trip search."""
    trips: List[Trip]
    search_time: datetime


# Disruption Models
class DisruptionSeverity(str, Enum):
    """Severity of disruption."""
    INFO = "info"
    WARNING = "warning"
    SEVERE = "severe"


class Disruption(BaseModel):
    """A disruption/incident."""
    id: str
    title: str
    description: str
    severity: DisruptionSeverity
    affected_lines: List[str] = []
    affected_stops: List[str] = []
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    is_active: bool = True


# Delay Prediction Models
class DelayPrediction(BaseModel):
    """Predicted delay for a leg."""
    predicted_delay_minutes: int
    confidence_score: float = Field(ge=0.0, le=1.0)
    factors: List[str] = []  # Contributing factors
    is_peak_hour: bool = False
    prediction_time: datetime


class TrafficSituation(BaseModel):
    """Road traffic situation affecting routes."""
    id: str
    description: str
    location_description: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    severity: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class TrafficLightStatus(BaseModel):
    """Traffic light intersection status."""
    intersection_id: str
    area_id: str
    name: Optional[str] = None
    level_of_service: Optional[str] = None  # A-F
    spillback_length_meters: Optional[float] = None
    green_percentage: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


# SSE Event Models
class SSEEvent(BaseModel):
    """Server-Sent Event payload."""
    event_type: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Update TripLeg to resolve forward reference
TripLeg.model_rebuild()
