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
import os
from datetime import datetime
from typing import List, Optional, AsyncGenerator
from contextlib import asynccontextmanager
import json
import zoneinfo

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
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
    get_disruptions_for_route,
    is_siri_sx_available,
    is_gtfs_rt_available
)
from traffic_client import (
    fetch_traffic_situations,
    fetch_traffic_lights,
    is_traffic_situations_available,
    is_traffic_lights_available
)
from prediction_engine import predict_delays_for_trip

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Timezone
try:
    TIMEZONE = zoneinfo.ZoneInfo(settings.TIMEZONE)
except Exception:
    TIMEZONE = zoneinfo.ZoneInfo("Europe/Zurich")

# Background scheduler for data refresh
scheduler = AsyncIOScheduler(timezone=TIMEZONE)

# In-memory store for latest data (for SSE broadcasting)
_latest_disruptions: List[Disruption] = []
_disruptions_available: bool = False
_latest_traffic_available: bool = False
_subscribers: List[asyncio.Queue] = []


async def refresh_disruptions():
    """Background task to refresh disruption data."""
    global _latest_disruptions, _disruptions_available
    try:
        disruptions, available = await fetch_siri_sx_disruptions()
        _latest_disruptions = disruptions
        _disruptions_available = available
        await broadcast_event("disruptions_update", {
            "count": len(_latest_disruptions),
            "available": _disruptions_available,
            "disruptions": [d.model_dump(mode='json') for d in _latest_disruptions[:20]]
        })
        logger.info(f"Refreshed disruptions: {len(_latest_disruptions)} active, available={_disruptions_available}")
    except Exception as e:
        logger.error(f"Error refreshing disruptions: {e}")
        _disruptions_available = False


async def refresh_traffic():
    """Background task to refresh traffic data."""
    global _latest_traffic_available
    try:
        situations, available = await fetch_traffic_situations()
        _latest_traffic_available = available
        logger.info(f"Refreshed traffic: {len(situations)} situations, available={_latest_traffic_available}")
    except Exception as e:
        logger.error(f"Error refreshing traffic: {e}")
        _latest_traffic_available = False


async def broadcast_event(event_type: str, data: dict):
    """Broadcast event to all SSE subscribers."""
    event = SSEEvent(
        event_type=event_type,
        data=data,
        timestamp=datetime.now(TIMEZONE)
    )
    dead_queues = []
    for queue in _subscribers:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            dead_queues.append(queue)

    for q in dead_queues:
        if q in _subscribers:
            _subscribers.remove(q)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
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

    logger.info(f"Swiss Transport Planner started on port {settings.PORT}")
    yield

    scheduler.shutdown()
    logger.info("Swiss Transport Planner stopped")


app = FastAPI(
    title=settings.APP_NAME,
    description="Swiss public transport planner with real-time updates and delay prediction",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(TIMEZONE).isoformat(),
        "timezone": settings.TIMEZONE,
        "disruptions_count": len(_latest_disruptions),
        "data_availability": {
            "ojp": bool(settings.OTD_OJP_API_KEY),
            "gtfs_rt": is_gtfs_rt_available(),
            "siri_sx": is_siri_sx_available(),
            "traffic_situations": is_traffic_situations_available(),
            "traffic_lights": is_traffic_lights_available()
        }
    }


@app.get("/api/locations", response_model=List[Location])
async def api_search_locations(
    query: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Max results")
):
    """Search for locations (stops, stations) by name."""
    if not settings.OTD_OJP_API_KEY:
        raise HTTPException(status_code=503, detail="OJP API key not configured")

    locations = await search_locations(query, limit)
    return locations


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
    Uses OJP for timetable-based routing. Real-time is only used for display/monitoring.
    """
    if not settings.OTD_OJP_API_KEY:
        raise HTTPException(status_code=503, detail="OJP API key not configured")

    result = await search_trips(
        origin_id=request.origin_id,
        destination_id=request.destination_id,
        departure_time=request.departure_time,
        num_results=request.num_results
    )

    if request.include_predictions:
        for trip in result.trips:
            predictions = await predict_delays_for_trip(trip.legs)
            for leg_idx, prediction in predictions:
                if prediction:
                    trip.legs[leg_idx].delay_prediction = prediction

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
                trip.disruptions = disruptions[:5]

    return result


@app.get("/api/trips/{trip_id}/predictions")
async def api_get_trip_predictions(trip_id: str):
    """Get delay predictions for a specific trip."""
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


@app.get("/api/disruptions")
async def api_get_disruptions(
    limit: int = Query(50, ge=1, le=200)
):
    """Get current disruptions affecting Swiss public transport."""
    return {
        "available": _disruptions_available,
        "count": len(_latest_disruptions),
        "disruptions": [d.model_dump(mode='json') for d in _latest_disruptions[:limit]]
    }


@app.get("/api/disruptions/for-route")
async def api_get_disruptions_for_route(
    stop_ids: str = Query(..., description="Comma-separated stop IDs"),
    line_refs: str = Query("", description="Comma-separated line references")
):
    """Get disruptions affecting specific stops or lines."""
    stops = [s.strip() for s in stop_ids.split(",") if s.strip()]
    lines = [l.strip() for l in line_refs.split(",") if l.strip()]

    disruptions = await get_disruptions_for_route(stops, lines)
    return {
        "available": _disruptions_available,
        "disruptions": disruptions
    }


@app.get("/api/traffic/situations")
async def api_get_traffic_situations(
    limit: int = Query(50, ge=1, le=200)
):
    """Get current road traffic situations."""
    situations, available = await fetch_traffic_situations()
    return {
        "available": available,
        "count": len(situations),
        "situations": situations[:limit]
    }


@app.get("/api/traffic/lights")
async def api_get_traffic_lights(
    area_id: Optional[str] = Query(None, description="Filter by area ID")
):
    """Get traffic light status data."""
    lights, available = await fetch_traffic_lights(area_id)
    return {
        "available": available,
        "count": len(lights),
        "lights": lights
    }


@app.get("/api/events")
async def api_sse_events():
    """
    Server-Sent Events endpoint for real-time updates.
    Heartbeat every ~25 seconds.
    """
    async def event_generator() -> AsyncGenerator:
        queue: asyncio.Queue = asyncio.Queue(maxsize=50)
        _subscribers.append(queue)

        try:
            yield {
                "event": "connected",
                "data": json.dumps({
                    "message": "Connected to Swiss Transport Planner",
                    "timestamp": datetime.now(TIMEZONE).isoformat(),
                    "data_available": {
                        "disruptions": _disruptions_available,
                        "traffic": _latest_traffic_available
                    }
                })
            }

            yield {
                "event": "disruptions_update",
                "data": json.dumps({
                    "count": len(_latest_disruptions),
                    "available": _disruptions_available,
                    "disruptions": [d.model_dump(mode='json') for d in _latest_disruptions[:20]]
                })
            }

            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(),
                        timeout=settings.SSE_HEARTBEAT_INTERVAL
                    )
                    yield {
                        "event": event.event_type,
                        "data": json.dumps(event.data, default=str)
                    }
                except asyncio.TimeoutError:
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps({
                            "timestamp": datetime.now(TIMEZONE).isoformat(),
                            "data_available": {
                                "disruptions": _disruptions_available,
                                "traffic": _latest_traffic_available
                            }
                        })
                    }

        finally:
            if queue in _subscribers:
                _subscribers.remove(queue)

    return EventSourceResponse(event_generator())


@app.get("/api/trips/{trip_id}/monitor")
async def api_monitor_trip(trip_id: str):
    """Monitor a specific trip for real-time updates."""
    return {
        "message": "Use /api/events for general updates",
        "note": "Trip-specific monitoring requires trip data from /api/trips"
    }


@app.get("/api/info")
async def api_info():
    """API information and assumptions."""
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "timezone": settings.TIMEZONE,
        "data_sources": {
            "routing": "OJP (Open Journey Planner) - timetable only",
            "disruptions": "SIRI-SX / VDV736 - refreshed every 30 seconds",
            "delays": "GTFS-RT Trip Updates",
            "traffic_situations": "DATEX II - road incidents",
            "traffic_lights": "OCIT-C - Level of Service, queue lengths"
        },
        "data_availability": {
            "ojp": bool(settings.OTD_OJP_API_KEY),
            "gtfs_rt": is_gtfs_rt_available(),
            "siri_sx": is_siri_sx_available(),
            "traffic_situations": is_traffic_situations_available(),
            "traffic_lights": is_traffic_lights_available()
        },
        "assumptions": [
            "OJP routing is timetable-only; real-time used for display only",
            "GTFS-RT on OTD does NOT provide vehicle positions, only delays",
            "Delay predictions use heuristic rules based on traffic data",
            "Prediction horizon is 15 minutes, primarily for peak hours",
            "Peak hours: 5:45-7:00 and 16:30-18:00 Europe/Zurich",
            "Traffic data coverage varies by region",
            "Platform/track info from OJP; fallback gracefully if missing"
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
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT
    )
