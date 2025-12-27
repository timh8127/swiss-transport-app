"""Real-time client for GTFS-RT and SIRI-SX data."""
import httpx
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from lxml import etree
import logging
from cachetools import TTLCache

from config import get_settings
from models import Disruption, DisruptionSeverity

logger = logging.getLogger(__name__)
settings = get_settings()

# Cache for disruptions and delays
_disruptions_cache: TTLCache = TTLCache(maxsize=1, ttl=settings.CACHE_TTL_DISRUPTIONS)
_delays_cache: TTLCache = TTLCache(maxsize=1, ttl=60)

# Availability tracking
_gtfs_rt_available: bool = True
_siri_sx_available: bool = True

SIRI_NAMESPACES = {
    'siri': 'http://www.siri.org.uk/siri'
}


def is_gtfs_rt_available() -> bool:
    """Check if GTFS-RT data is available."""
    return _gtfs_rt_available and bool(settings.OTD_GTFSRT_API_KEY)


def is_siri_sx_available() -> bool:
    """Check if SIRI-SX data is available."""
    return _siri_sx_available and bool(settings.OTD_SIRI_SX_API_KEY)


async def fetch_gtfs_rt_delays() -> Tuple[Dict[str, int], bool]:
    """
    Fetch delay information from GTFS-RT.
    Returns tuple of (delays_dict, is_available).

    Note: GTFS-RT on OTD only provides Trip Updates (delays),
    NOT vehicle positions.
    """
    global _gtfs_rt_available

    if 'delays' in _delays_cache:
        return _delays_cache['delays'], _gtfs_rt_available

    if not settings.OTD_GTFSRT_API_KEY:
        logger.warning("OTD_GTFSRT_API_KEY not configured")
        _gtfs_rt_available = False
        return {}, False

    headers = {
        'Authorization': f'Bearer {settings.OTD_GTFSRT_API_KEY}',
        'User-Agent': 'SwissTransportApp/1.0',
        'Accept-Encoding': 'gzip, deflate'
    }

    delays = {}

    try:
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(
                f"{settings.GTFS_RT_ENDPOINT}?format=JSON",
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

            # Parse GTFS-RT JSON format
            if 'Entity' in data:
                for entity in data['Entity']:
                    if 'TripUpdate' in entity:
                        trip_update = entity['TripUpdate']
                        trip_id = trip_update.get('Trip', {}).get('TripId', '')

                        stop_time_updates = trip_update.get('StopTimeUpdate', [])
                        if stop_time_updates:
                            delay_sec = stop_time_updates[0].get('Arrival', {}).get('Delay', 0)
                            if delay_sec == 0:
                                delay_sec = stop_time_updates[0].get('Departure', {}).get('Delay', 0)
                            delays[trip_id] = delay_sec // 60

            _delays_cache['delays'] = delays
            _gtfs_rt_available = True

    except httpx.TimeoutException:
        logger.warning("GTFS-RT request timed out")
        _gtfs_rt_available = False
    except httpx.HTTPStatusError as e:
        logger.error(f"GTFS-RT HTTP error: {e.response.status_code}")
        _gtfs_rt_available = False
    except Exception as e:
        logger.error(f"Error fetching GTFS-RT delays: {e}")
        _gtfs_rt_available = False

    return delays, _gtfs_rt_available


async def fetch_siri_sx_disruptions() -> Tuple[List[Disruption], bool]:
    """
    Fetch disruptions from SIRI-SX endpoint.
    Returns tuple of (disruptions_list, is_available).
    """
    global _siri_sx_available

    if 'disruptions' in _disruptions_cache:
        return _disruptions_cache['disruptions'], _siri_sx_available

    if not settings.OTD_SIRI_SX_API_KEY:
        logger.warning("OTD_SIRI_SX_API_KEY not configured")
        _siri_sx_available = False
        return [], False

    headers = {
        'Authorization': f'Bearer {settings.OTD_SIRI_SX_API_KEY}',
        'User-Agent': 'SwissTransportApp/1.0',
        'Accept': 'application/xml'
    }

    disruptions = []

    try:
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
            response = await client.get(
                settings.SIRI_SX_ENDPOINT,
                headers=headers
            )
            response.raise_for_status()

            root = etree.fromstring(response.content)

            for situation in root.findall('.//siri:PtSituationElement', SIRI_NAMESPACES):
                try:
                    sit_id = situation.findtext('.//siri:SituationNumber', namespaces=SIRI_NAMESPACES) or \
                             situation.findtext('.//siri:ParticipantRef', namespaces=SIRI_NAMESPACES)

                    summary = situation.findtext('.//siri:Summary', namespaces=SIRI_NAMESPACES) or ""
                    description = situation.findtext('.//siri:Description', namespaces=SIRI_NAMESPACES) or summary

                    severity_text = situation.findtext('.//siri:Severity', namespaces=SIRI_NAMESPACES) or "normal"
                    severity_map = {
                        'noImpact': DisruptionSeverity.INFO,
                        'slight': DisruptionSeverity.INFO,
                        'normal': DisruptionSeverity.WARNING,
                        'severe': DisruptionSeverity.SEVERE,
                        'verySevere': DisruptionSeverity.SEVERE
                    }
                    severity = severity_map.get(severity_text.lower(), DisruptionSeverity.WARNING)

                    affected_lines = []
                    affected_stops = []

                    for line_ref in situation.findall('.//siri:LineRef', SIRI_NAMESPACES):
                        if line_ref.text:
                            affected_lines.append(line_ref.text)

                    for stop_ref in situation.findall('.//siri:StopPointRef', SIRI_NAMESPACES):
                        if stop_ref.text:
                            affected_stops.append(stop_ref.text)

                    start_time_str = situation.findtext('.//siri:StartTime', namespaces=SIRI_NAMESPACES)
                    end_time_str = situation.findtext('.//siri:EndTime', namespaces=SIRI_NAMESPACES)

                    start_time = None
                    end_time = None
                    if start_time_str:
                        try:
                            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                        except ValueError:
                            pass
                    if end_time_str:
                        try:
                            end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                        except ValueError:
                            pass

                    if sit_id:
                        disruptions.append(Disruption(
                            id=sit_id,
                            title=summary[:200] if summary else "Disruption",
                            description=description[:1000] if description else "",
                            severity=severity,
                            affected_lines=affected_lines[:20],
                            affected_stops=affected_stops[:20],
                            start_time=start_time,
                            end_time=end_time,
                            is_active=True
                        ))

                except Exception as e:
                    logger.warning(f"Error parsing situation: {e}")
                    continue

        _disruptions_cache['disruptions'] = disruptions
        _siri_sx_available = True

    except httpx.TimeoutException:
        logger.warning("SIRI-SX request timed out")
        _siri_sx_available = False
    except httpx.HTTPStatusError as e:
        logger.error(f"SIRI-SX HTTP error: {e.response.status_code}")
        _siri_sx_available = False
    except Exception as e:
        logger.error(f"Error fetching SIRI-SX disruptions: {e}")
        _siri_sx_available = False

    return disruptions, _siri_sx_available


async def get_disruptions_for_route(stop_ids: List[str], line_refs: List[str]) -> List[Disruption]:
    """Get disruptions affecting specific stops or lines."""
    all_disruptions, _ = await fetch_siri_sx_disruptions()

    stop_set: Set[str] = set(stop_ids)
    line_set: Set[str] = set(line_refs)

    relevant = []
    for d in all_disruptions:
        if set(d.affected_stops) & stop_set or set(d.affected_lines) & line_set:
            relevant.append(d)

    return relevant


async def get_delay_for_trip(trip_id: str) -> int:
    """Get delay in minutes for a specific trip."""
    delays, _ = await fetch_gtfs_rt_delays()
    return delays.get(trip_id, 0)
