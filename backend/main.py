"""
Swiss Transport Planner - Main FastAPI Application

Production-grade Swiss public transport web app combining:
- Route planning via OJP (timetable-only)
- Live disruption monitoring via SIRI-SX
- Delay information via GTFS-RT
- Heuristic delay prediction using road traffic data
"""
import asyncio
import logging
from datetime import datetime
from typing import List, Optional, AsyncGenerator
from contextlib import asynccontextmanager
import json

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import BaseModel

from config import get_settings
from models import (
    Location, Trip, TripSearchResult, Disruption,
    TripRequest, LocationSearchRequest, SSEEvent,
    DelayPrediction
)
from ojp_client import search_locations, search_trips
from realtime_client import (
    fetch_siri_sx_disruptions,
    fetch_gtfs_rt_delays,
    get_disruptions_for_route
)
from traffic_client import fetch_traffic_situations, fetch_traffic_lights
from prediction_engine import predict_delays_for_trip

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Background scheduler for data refresh
scheduler = AsyncIOScheduler()

# In-memory store for latest data (for SSE broadcasting)
_latest_disruptions: List[Disruption] = []
_latest_traffic = {}
_subscribers: List[asyncio.Queue] = []


async def refresh_disruptions():
    """Background task to refresh disruption data."""
    global _latest_disruptions
    try:
        _latest_disruptions = await fetch_siri_sx_disruptions()
        await broadcast_event("disruptions_update", {
            "count": len(_latest_disruptions),
            "disruptions": [d.model_dump() for d in _latest_disruptions[:20]]
        })
        logger.info(f"Refreshed disruptions: {len(_latest_disruptions)} active")
    except Exception as e:
        logger.error(f"Error refreshing disruptions: {e}")


async def refresh_traffic():
    """Background task to refresh traffic data."""
    global _latest_traffic
    try:
        situations = await fetch_traffic_situations()
        _latest_traffic = {
            "situations_count": len(situations),
            "last_update": datetime.utcnow().isoformat()
        }
        logger.info(f"Refreshed traffic: {len(situations)} situations")
    except Exception as e:
        logger.error(f"Error refreshing traffic: {e}")


async def broadcast_event(event_type: str, data: dict):
    """Broadcast event to all SSE subscribers."""
    event = SSEEvent(
        event_type=event_type,
        data=data,
        timestamp=datetime.utcnow()
    )
    dead_queues = []
    for queue in _subscribers:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            dead_queues.append(queue)

    for q in dead_queues:
        _subscribers.remove(q)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Start background scheduler
    scheduler.add_job(
        refresh_disruptions,
        'interval',
        seconds=settings.POLL_INTERVAL_DISRUPTIONS,
        id='refresh_disruptions'
    )
    scheduler.add_job(
        refresh_traffic,
        'interval',
        seconds=settings.POLL_INTERVAL_TRAFFIC,
        id='refresh_traffic'
    )
    scheduler.start()

    # Initial data fetch
    await refresh_disruptions()
    await refresh_traffic()

    logger.info("Swiss Transport Planner started")
    yield

    # Cleanup
    scheduler.shutdown()
    logger.info("Swiss Transport Planner stopped")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Swiss public transport planner with real-time updates and delay prediction",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "disruptions_count": len(_latest_disruptions),
        "api_configured": bool(settings.OTD_API_KEY)
    }


# Location search
@app.get("/api/locations", response_model=List[Location])
async def api_search_locations(
    query: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Max results")
):
    """
    Search for locations (stops, stations) by name.

    Returns matching stops from the Swiss public transport network.
    """
    if not settings.OTD_API_KEY:
        raise HTTPException(status_code=503, detail="API key not configured")

    locations = await search_locations(query, limit)
    return locations


# Trip planning
class TripPlanRequest(BaseModel):
    """Request body for trip planning."""
    origin_id: str
    origin_name: str = ""
    destination_id: str
    destination_name: str = ""
    departure_time: Optional[datetime] = None
    num_results: int = 5
    include_predictions: bool = True


@app.post("/api/trips", response_model=TripSearchResult)
async def api_plan_trip(request: TripPlanRequest):
    """
    Plan a trip between two locations.

    Uses OJP for timetable-based routing. Does NOT include real-time
    data in routing - real-time is only used for display/monitoring.

    Optionally includes delay predictions for bus/tram legs.
    """
    if not settings.OTD_API_KEY:
        raise HTTPException(status_code=503, detail="API key not configured")

    result = await search_trips(
        origin_id=request.origin_id,
        destination_id=request.destination_id,
        departure_time=request.departure_time,
        num_results=request.num_results
    )

    # Add delay predictions if requested
    if request.include_predictions:
        for trip in result.trips:
            predictions = await predict_delays_for_trip(trip.legs)
            for leg_idx, prediction in predictions:
                if prediction:
                    trip.legs[leg_idx].delay_prediction = prediction

            # Check for disruptions affecting this trip
            stop_ids = []
            line_refs = []
            for leg in trip.legs:
                stop_ids.append(leg.origin.id)
                stop_ids.append(leg.destination.id)
                for stop in leg.intermediate_stops:
                    stop_ids.append(stop.id)
                if leg.line_number:
                    line_refs.append(leg.line_number)

            disruptions = await get_disruptions_for_route(stop_ids, line_refs)
            if disruptions:
                trip.has_disruptions = True
                trip.disruptions = disruptions[:5]  # Limit to 5

    return result


# Get trip details with predictions
@app.get("/api/trips/{trip_id}/predictions")
async def api_get_trip_predictions(trip_id: str):
    """
    Get delay predictions for a specific trip.

    Note: This endpoint requires the trip to be fetched first via /api/trips.
    In a production system, trips would be cached/stored.
    """
    # For demo purposes, return explanation
    return {
        "message": "Use POST /api/trips with include_predictions=true",
        "prediction_factors": [
            "Traffic situations (accidents, roadworks)",
            "Traffic light congestion (Level of Service)",
            "Queue lengths (spillback)",
            "Peak hour multiplier (5:45-7:00, 16:30-18:00)"
        ],
        "prediction_horizon_minutes": 15
    }


# Disruptions
@app.get("/api/disruptions", response_model=List[Disruption])
async def api_get_disruptions(
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get current disruptions affecting Swiss public transport.

    Data is refreshed every 30 seconds from SIRI-SX.
    """
    return _latest_disruptions[:limit]


@app.get("/api/disruptions/for-route")
async def api_get_disruptions_for_route(
    stop_ids: str = Query(..., description="Comma-separated stop IDs"),
    line_refs: str = Query("", description="Comma-separated line references")
):
    """
    Get disruptions affecting specific stops or lines.
    """
    stops = [s.strip() for s in stop_ids.split(",") if s.strip()]
    lines = [l.strip() for l in line_refs.split(",") if l.strip()]

    disruptions = await get_disruptions_for_route(stops, lines)
    return disruptions


# Traffic data
@app.get("/api/traffic/situations")
async def api_get_traffic_situations(
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get current road traffic situations.

    Includes accidents, roadworks, and other incidents that may
    affect bus/tram services.
    """
    situations = await fetch_traffic_situations()
    return situations[:limit]


@app.get("/api/traffic/lights")
async def api_get_traffic_lights(
    area_id: Optional[str] = Query(None, description="Filter by area ID")
):
    """
    Get traffic light status data.

    Includes Level of Service, queue lengths, and green percentages.
    """
    lights = await fetch_traffic_lights(area_id)
    return lights


# Server-Sent Events for real-time updates
@app.get("/api/events")
async def api_sse_events():
    """
    Server-Sent Events endpoint for real-time updates.

    Streams:
    - disruptions_update: When disruption data is refreshed
    - delay_update: When delay information changes

    Connect using EventSource in browser:
    ```javascript
    const evtSource = new EventSource('/api/events');
    evtSource.onmessage = (event) => console.log(event.data);
    ```
    """
    async def event_generator() -> AsyncGenerator:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        _subscribers.append(queue)

        try:
            # Send initial data
            yield {
                "event": "connected",
                "data": json.dumps({
                    "message": "Connected to Swiss Transport Planner",
                    "timestamp": datetime.utcnow().isoformat()
                })
            }

            # Send current disruptions
            yield {
                "event": "disruptions_update",
                "data": json.dumps({
                    "count": len(_latest_disruptions),
                    "disruptions": [d.model_dump(mode='json') for d in _latest_disruptions[:20]]
                })
            }

            # Stream updates
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {
                        "event": event.event_type,
                        "data": json.dumps(event.data, default=str)
                    }
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {
                        "event": "keepalive",
                        "data": json.dumps({"timestamp": datetime.utcnow().isoformat()})
                    }

        finally:
            if queue in _subscribers:
                _subscribers.remove(queue)

    return EventSourceResponse(event_generator())


# SSE endpoint for specific trip monitoring
@app.get("/api/trips/{trip_id}/monitor")
async def api_monitor_trip(trip_id: str):
    """
    Monitor a specific trip for real-time updates.

    Streams disruptions and delay updates relevant to the trip.
    """
    # For demo - in production, would track specific trip
    return {
        "message": "Use /api/events for general updates",
        "note": "Trip-specific monitoring requires trip data from /api/trips"
    }


# Documentation
@app.get("/api/info")
async def api_info():
    """
    API information and assumptions.
    """
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "data_sources": {
            "routing": "OJP (Open Journey Planner) - timetable only",
            "disruptions": "SIRI-SX / VDV736 - refreshed every 30 seconds",
            "delays": "GTFS-RT Trip Updates",
            "traffic_situations": "DATEX II - road incidents",
            "traffic_lights": "OCIT-C - Level of Service, queue lengths"
        },
        "assumptions": [
            "OJP routing is timetable-only; real-time used for display only",
            "GTFS-RT on OTD does NOT provide vehicle positions, only delays",
            "Delay predictions use heuristic rules based on traffic data",
            "Prediction horizon is 15 minutes, primarily for peak hours",
            "Peak hours: 5:45-7:00 and 16:30-18:00 local time",
            "Traffic data coverage varies by region"
        ],
        "prediction_rules": {
            "traffic_situation_severe": "+8 min",
            "traffic_situation_moderate": "+4 min",
            "traffic_los_f": "+6 min (severe congestion)",
            "traffic_los_e": "+4 min",
            "traffic_los_d": "+2 min",
            "spillback_per_100m": "+1 min",
            "peak_hour_multiplier": "1.5x"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
