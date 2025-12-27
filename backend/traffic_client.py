"""Traffic data client for delay prediction."""
import httpx
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from lxml import etree
import logging
import math
from cachetools import TTLCache

from config import get_settings
from models import TrafficSituation, TrafficLightStatus

logger = logging.getLogger(__name__)
settings = get_settings()

# Cache for traffic data
_traffic_situations_cache: TTLCache = TTLCache(maxsize=1, ttl=settings.CACHE_TTL_TRAFFIC)
_traffic_lights_cache: TTLCache = TTLCache(maxsize=100, ttl=settings.CACHE_TTL_TRAFFIC)


def _build_traffic_situations_request() -> str:
    """Build SOAP request for traffic situations."""
    return f'''<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
    <PullTrafficMessages xmlns="http://opentransportdata.swiss/TDP/Soap_Datex2/Pull/v1">
      <clientIdentification xmlns="http://datex2.eu/schema/2/2_3">
        <country>ch</country>
        <nationalIdentifier>SwissTransportApp</nationalIdentifier>
      </clientIdentification>
      <operatingMode>operatingMode1</operatingMode>
      <requestDate>{datetime.utcnow().isoformat()}Z</requestDate>
      <returnStatus>active</returnStatus>
      <updateMethod>singleElementUpdate</updateMethod>
      <deliveryBreakdown>
        <deliveryLocation>http</deliveryLocation>
      </deliveryBreakdown>
    </PullTrafficMessages>
  </s:Body>
</s:Envelope>'''


async def fetch_traffic_situations() -> List[TrafficSituation]:
    """Fetch current traffic situations (accidents, roadworks, etc.)."""
    if 'situations' in _traffic_situations_cache:
        return _traffic_situations_cache['situations']

    headers = {
        'Authorization': f'Bearer {settings.OTD_API_KEY}',
        'Content-Type': 'application/xml',
        'SOAPAction': 'http://opentransportdata.swiss/TDP/Soap_Datex2/Pull/v1/pullTrafficMessages',
        'User-Agent': 'SwissTransportApp/1.0'
    }

    situations = []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                settings.TRAFFIC_SITUATIONS_ENDPOINT,
                content=_build_traffic_situations_request(),
                headers=headers
            )
            response.raise_for_status()

            root = etree.fromstring(response.content)

            # Parse DATEX II situations - use local-name() to handle namespaces
            for situation in root.xpath('//*[local-name()="situationRecord"]'):
                try:
                    sit_id = situation.get('id', '')

                    # Get description
                    description = ""
                    for value in situation.xpath('.//*[local-name()="generalPublicComment"]//*[local-name()="value"]'):
                        lang = value.get('lang', '')
                        if lang == 'en' or not description:
                            description = value.text or ""
                            if lang == 'en':
                                break

                    # Get coordinates
                    lat = None
                    lon = None
                    lat_elem = situation.xpath('.//*[local-name()="latitude"]')
                    lon_elem = situation.xpath('.//*[local-name()="longitude"]')
                    if lat_elem and lon_elem:
                        try:
                            lat = float(lat_elem[0].text)
                            lon = float(lon_elem[0].text)
                        except:
                            pass

                    # Get severity/impact
                    severity = "normal"
                    impact = situation.xpath('.//*[local-name()="impactType"]')
                    if impact:
                        severity = impact[0].text or "normal"

                    # Get times
                    start_time = None
                    end_time = None
                    start_elem = situation.xpath('.//*[local-name()="overallStartTime"]')
                    end_elem = situation.xpath('.//*[local-name()="overallEndTime"]')
                    if start_elem:
                        try:
                            start_time = datetime.fromisoformat(start_elem[0].text.replace('Z', '+00:00'))
                        except:
                            pass
                    if end_elem:
                        try:
                            end_time = datetime.fromisoformat(end_elem[0].text.replace('Z', '+00:00'))
                        except:
                            pass

                    if sit_id:
                        situations.append(TrafficSituation(
                            id=sit_id,
                            description=description[:500],
                            location_description=description[:200],
                            latitude=lat,
                            longitude=lon,
                            severity=severity,
                            start_time=start_time,
                            end_time=end_time
                        ))

                except Exception as e:
                    logger.warning(f"Error parsing traffic situation: {e}")
                    continue

        _traffic_situations_cache['situations'] = situations

    except Exception as e:
        logger.error(f"Error fetching traffic situations: {e}")

    return situations


async def fetch_traffic_lights(area_id: Optional[str] = None) -> List[TrafficLightStatus]:
    """Fetch traffic light status data."""
    cache_key = f'lights_{area_id or "all"}'
    if cache_key in _traffic_lights_cache:
        return _traffic_lights_cache[cache_key]

    headers = {
        'Authorization': f'Bearer {settings.OTD_API_KEY}',
        'User-Agent': 'SwissTransportApp/1.0',
        'Accept': 'application/json'
    }

    lights = []

    try:
        # First get areas
        async with httpx.AsyncClient(timeout=30.0) as client:
            if area_id:
                # Get snippets for specific area
                url = f"{settings.TRAFFIC_LIGHTS_BASE}/snippets/{area_id}"
            else:
                # Get all areas first
                areas_response = await client.get(
                    f"{settings.TRAFFIC_LIGHTS_BASE}/areas",
                    headers=headers
                )
                if areas_response.status_code == 200:
                    areas_data = areas_response.json()
                    # Return early if we need all - for now just get first area
                    if isinstance(areas_data, list) and len(areas_data) > 0:
                        area_id = areas_data[0].get('areaId', areas_data[0].get('id'))
                        if area_id:
                            url = f"{settings.TRAFFIC_LIGHTS_BASE}/snippets/{area_id}"
                        else:
                            return lights
                    else:
                        return lights
                else:
                    return lights

            # Get snippets (real-time data)
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()

                # Parse snippets - structure depends on API response
                snippets = data if isinstance(data, list) else data.get('snippets', [])

                for snippet in snippets:
                    try:
                        intersection_id = snippet.get('unitId', snippet.get('intersectionId', ''))
                        measurements = snippet.get('measurements', {})

                        # Get Level of Service
                        los = None
                        los_data = measurements.get('LOS', measurements.get('levelOfService'))
                        if los_data:
                            if isinstance(los_data, dict):
                                los = los_data.get('value', los_data.get('LOS'))
                            else:
                                los = str(los_data)

                        # Get spillback length
                        spillback = None
                        spillback_data = measurements.get('SpillbackLength', measurements.get('spillbackLength'))
                        if spillback_data:
                            if isinstance(spillback_data, dict):
                                spillback = spillback_data.get('Length', spillback_data.get('length'))
                            else:
                                spillback = float(spillback_data) if spillback_data else None

                        # Get green percentage
                        green_pct = None
                        green_data = measurements.get('GreenPercentage', measurements.get('greenPercentage'))
                        if green_data:
                            if isinstance(green_data, dict):
                                green_pct = green_data.get('Percentage', green_data.get('percentage'))
                            else:
                                green_pct = float(green_data) if green_data else None

                        # Get coordinates from intersection info if available
                        lat = snippet.get('latitude')
                        lon = snippet.get('longitude')

                        if intersection_id:
                            lights.append(TrafficLightStatus(
                                intersection_id=intersection_id,
                                area_id=area_id or "",
                                name=snippet.get('name'),
                                level_of_service=los,
                                spillback_length_meters=spillback,
                                green_percentage=green_pct,
                                latitude=lat,
                                longitude=lon
                            ))

                    except Exception as e:
                        logger.warning(f"Error parsing traffic light: {e}")
                        continue

        _traffic_lights_cache[cache_key] = lights

    except Exception as e:
        logger.error(f"Error fetching traffic lights: {e}")

    return lights


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers."""
    R = 6371  # Earth's radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat / 2) ** 2 + \
        math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


async def get_traffic_near_route(
    route_points: List[Tuple[float, float]],
    radius_km: float = 0.5
) -> Tuple[List[TrafficSituation], List[TrafficLightStatus]]:
    """Get traffic situations and light status near a route."""
    situations = await fetch_traffic_situations()
    lights = await fetch_traffic_lights()

    relevant_situations = []
    relevant_lights = []

    for sit in situations:
        if sit.latitude and sit.longitude:
            for lat, lon in route_points:
                if haversine_distance(sit.latitude, sit.longitude, lat, lon) <= radius_km:
                    relevant_situations.append(sit)
                    break

    for light in lights:
        if light.latitude and light.longitude:
            for lat, lon in route_points:
                if haversine_distance(light.latitude, light.longitude, lat, lon) <= radius_km:
                    relevant_lights.append(light)
                    break

    return relevant_situations, relevant_lights
