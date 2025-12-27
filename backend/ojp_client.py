"""OJP (Open Journey Planner) client for route planning."""
import httpx
from datetime import datetime
from typing import List, Optional
from lxml import etree
import uuid
import logging

from config import get_settings
from models import (
    Location, LocationType, Trip, TripLeg, StopPoint,
    TransportMode, TripSearchResult
)

logger = logging.getLogger(__name__)
settings = get_settings()

# XML Namespaces
NAMESPACES = {
    'ojp': 'http://www.vdv.de/ojp',
    'siri': 'http://www.siri.org.uk/siri'
}


def _mode_from_ojp(ojp_mode: str) -> TransportMode:
    """Convert OJP mode to our TransportMode enum."""
    mode_map = {
        'rail': TransportMode.RAIL,
        'bus': TransportMode.BUS,
        'tram': TransportMode.TRAM,
        'metro': TransportMode.METRO,
        'funicular': TransportMode.FUNICULAR,
        'water': TransportMode.FERRY,
        'telecabin': TransportMode.CABLEWAY,
        'cableway': TransportMode.CABLEWAY,
        'walk': TransportMode.WALK,
    }
    return mode_map.get(ojp_mode.lower(), TransportMode.UNKNOWN)


def _build_location_request(query: str, limit: int = 10) -> str:
    """Build OJP LocationInformationRequest XML."""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<ojp:OJP xmlns:ojp="http://www.vdv.de/ojp" xmlns:siri="http://www.siri.org.uk/siri" version="1.0">
  <ojp:OJPRequest>
    <siri:RequestTimestamp>{datetime.utcnow().isoformat()}Z</siri:RequestTimestamp>
    <siri:MessageIdentifier>{uuid.uuid4()}</siri:MessageIdentifier>
    <ojp:OJPLocationInformationRequest>
      <siri:RequestTimestamp>{datetime.utcnow().isoformat()}Z</siri:RequestTimestamp>
      <ojp:InitialInput>
        <ojp:LocationName>{query}</ojp:LocationName>
      </ojp:InitialInput>
      <ojp:Restrictions>
        <ojp:Type>stop</ojp:Type>
        <ojp:NumberOfResults>{limit}</ojp:NumberOfResults>
      </ojp:Restrictions>
    </ojp:OJPLocationInformationRequest>
  </ojp:OJPRequest>
</ojp:OJP>'''


def _build_trip_request(
    origin_id: str,
    destination_id: str,
    departure_time: Optional[datetime] = None,
    num_results: int = 5
) -> str:
    """Build OJP TripRequest XML."""
    dep_time = departure_time or datetime.utcnow()
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<ojp:OJP xmlns:ojp="http://www.vdv.de/ojp" xmlns:siri="http://www.siri.org.uk/siri" version="1.0">
  <ojp:OJPRequest>
    <siri:RequestTimestamp>{datetime.utcnow().isoformat()}Z</siri:RequestTimestamp>
    <siri:MessageIdentifier>{uuid.uuid4()}</siri:MessageIdentifier>
    <ojp:OJPTripRequest>
      <siri:RequestTimestamp>{datetime.utcnow().isoformat()}Z</siri:RequestTimestamp>
      <ojp:Origin>
        <ojp:PlaceRef>
          <ojp:StopPlaceRef>{origin_id}</ojp:StopPlaceRef>
        </ojp:PlaceRef>
        <ojp:DepArrTime>{dep_time.isoformat()}</ojp:DepArrTime>
      </ojp:Origin>
      <ojp:Destination>
        <ojp:PlaceRef>
          <ojp:StopPlaceRef>{destination_id}</ojp:StopPlaceRef>
        </ojp:PlaceRef>
      </ojp:Destination>
      <ojp:Params>
        <ojp:NumberOfResults>{num_results}</ojp:NumberOfResults>
        <ojp:IncludeTrackSections>true</ojp:IncludeTrackSections>
        <ojp:IncludeTurnDescription>false</ojp:IncludeTurnDescription>
        <ojp:IncludeIntermediateStops>true</ojp:IncludeIntermediateStops>
      </ojp:Params>
    </ojp:OJPTripRequest>
  </ojp:OJPRequest>
</ojp:OJP>'''


async def _make_ojp_request(xml_body: str) -> etree._Element:
    """Make request to OJP API."""
    if not settings.OTD_OJP_API_KEY:
        raise ValueError("OTD_OJP_API_KEY not configured")

    headers = {
        'Content-Type': 'application/xml',
        'Authorization': f'Bearer {settings.OTD_OJP_API_KEY}',
        'User-Agent': 'SwissTransportApp/1.0'
    }

    async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
        response = await client.post(
            settings.OJP_ENDPOINT,
            content=xml_body,
            headers=headers
        )
        response.raise_for_status()
        return etree.fromstring(response.content)


def _parse_location(loc_elem: etree._Element) -> Optional[Location]:
    """Parse a location element from OJP response."""
    try:
        # Try to get StopPlace first
        stop_place = loc_elem.find('.//ojp:StopPlace', NAMESPACES)
        if stop_place is not None:
            stop_id = stop_place.findtext('ojp:StopPlaceRef', namespaces=NAMESPACES) or \
                      stop_place.findtext('.//siri:StopPointRef', namespaces=NAMESPACES)
            name = stop_place.findtext('.//ojp:Text', namespaces=NAMESPACES)

            # Get coordinates
            lat = stop_place.findtext('.//ojp:Latitude', namespaces=NAMESPACES)
            lon = stop_place.findtext('.//ojp:Longitude', namespaces=NAMESPACES)

            # Get locality
            locality = stop_place.findtext('.//ojp:TopographicPlaceName/ojp:Text', namespaces=NAMESPACES)

            if stop_id and name:
                return Location(
                    id=stop_id,
                    name=name,
                    type=LocationType.STOP,
                    latitude=float(lat) if lat else None,
                    longitude=float(lon) if lon else None,
                    locality=locality
                )
    except Exception as e:
        logger.warning(f"Error parsing location: {e}")
    return None


def _parse_stop_point(elem: etree._Element, prefix: str = '') -> Optional[StopPoint]:
    """Parse a stop point from leg."""
    try:
        stop_ref = elem.findtext(f'.//ojp:StopPointRef', namespaces=NAMESPACES) or \
                   elem.findtext(f'.//siri:StopPointRef', namespaces=NAMESPACES)
        name = elem.findtext('.//ojp:StopPointName/ojp:Text', namespaces=NAMESPACES) or \
               elem.findtext('.//ojp:Text', namespaces=NAMESPACES)

        # Platform/Track info
        platform = elem.findtext('.//ojp:PlannedQuay/ojp:Text', namespaces=NAMESPACES) or \
                   elem.findtext('.//ojp:EstimatedQuay/ojp:Text', namespaces=NAMESPACES)

        # Times
        scheduled = elem.findtext('.//ojp:TimetabledTime', namespaces=NAMESPACES)
        estimated = elem.findtext('.//ojp:EstimatedTime', namespaces=NAMESPACES)

        # Coordinates
        lat = elem.findtext('.//ojp:Latitude', namespaces=NAMESPACES)
        lon = elem.findtext('.//ojp:Longitude', namespaces=NAMESPACES)

        if stop_ref and name and scheduled:
            scheduled_dt = datetime.fromisoformat(scheduled.replace('Z', '+00:00'))
            estimated_dt = datetime.fromisoformat(estimated.replace('Z', '+00:00')) if estimated else None

            delay = 0
            if estimated_dt:
                delay = int((estimated_dt - scheduled_dt).total_seconds() / 60)

            return StopPoint(
                id=stop_ref,
                name=name,
                platform=platform,
                scheduled_time=scheduled_dt,
                estimated_time=estimated_dt,
                delay_minutes=delay,
                latitude=float(lat) if lat else None,
                longitude=float(lon) if lon else None
            )
    except Exception as e:
        logger.warning(f"Error parsing stop point: {e}")
    return None


def _parse_trip_leg(leg_elem: etree._Element, leg_idx: int) -> Optional[TripLeg]:
    """Parse a single trip leg."""
    try:
        # Determine mode
        timed_leg = leg_elem.find('.//ojp:TimedLeg', NAMESPACES)
        transfer_leg = leg_elem.find('.//ojp:TransferLeg', NAMESPACES)
        continuous_leg = leg_elem.find('.//ojp:ContinuousLeg', NAMESPACES)

        if timed_leg is not None:
            # Public transport leg
            service = timed_leg.find('.//ojp:Service', NAMESPACES)
            mode_elem = service.findtext('.//ojp:PtMode', namespaces=NAMESPACES) if service else None
            mode = _mode_from_ojp(mode_elem) if mode_elem else TransportMode.UNKNOWN

            line_name = service.findtext('.//ojp:PublishedLineName/ojp:Text', namespaces=NAMESPACES) if service else None
            line_number = service.findtext('.//ojp:LineRef', namespaces=NAMESPACES) if service else None
            destination_text = service.findtext('.//ojp:DestinationText/ojp:Text', namespaces=NAMESPACES) if service else None
            operator = service.findtext('.//ojp:OperatorRef', namespaces=NAMESPACES) if service else None

            # Board and Alight
            board = timed_leg.find('.//ojp:LegBoard', NAMESPACES)
            alight = timed_leg.find('.//ojp:LegAlight', NAMESPACES)

            origin = _parse_stop_point(board) if board is not None else None
            destination = _parse_stop_point(alight) if alight is not None else None

            # Intermediate stops
            intermediate = []
            for inter in timed_leg.findall('.//ojp:LegIntermediates', NAMESPACES):
                stop = _parse_stop_point(inter)
                if stop:
                    intermediate.append(stop)

            if origin and destination:
                duration = int((destination.scheduled_time - origin.scheduled_time).total_seconds() / 60)

                return TripLeg(
                    leg_id=f"leg_{leg_idx}",
                    mode=mode,
                    line_name=line_name,
                    line_number=line_number,
                    destination_text=destination_text,
                    operator=operator,
                    origin=origin,
                    destination=destination,
                    intermediate_stops=intermediate,
                    duration_minutes=max(1, duration),
                    has_realtime=mode in [TransportMode.BUS, TransportMode.TRAM]
                )

        elif transfer_leg is not None or continuous_leg is not None:
            # Walking leg
            leg_data = transfer_leg if transfer_leg is not None else continuous_leg

            start_elem = leg_data.find('.//ojp:LegStart', NAMESPACES)
            end_elem = leg_data.find('.//ojp:LegEnd', NAMESPACES)

            # Parse times
            start_time_str = leg_data.findtext('.//ojp:TimeWindowStart', namespaces=NAMESPACES)
            end_time_str = leg_data.findtext('.//ojp:TimeWindowEnd', namespaces=NAMESPACES)
            duration_str = leg_data.findtext('.//ojp:Duration', namespaces=NAMESPACES)

            # Default times if not found
            now = datetime.utcnow()
            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00')) if start_time_str else now
            end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00')) if end_time_str else now

            # Parse duration (PT5M format)
            duration_minutes = 5
            if duration_str:
                import re
                match = re.search(r'PT(\d+)M', duration_str)
                if match:
                    duration_minutes = int(match.group(1))

            # Get location names
            start_name = start_elem.findtext('.//ojp:Text', namespaces=NAMESPACES) if start_elem is not None else "Start"
            end_name = end_elem.findtext('.//ojp:Text', namespaces=NAMESPACES) if end_elem is not None else "End"

            origin = StopPoint(
                id="walk_start",
                name=start_name,
                scheduled_time=start_time,
                delay_minutes=0
            )
            destination = StopPoint(
                id="walk_end",
                name=end_name,
                scheduled_time=end_time,
                delay_minutes=0
            )

            return TripLeg(
                leg_id=f"leg_{leg_idx}",
                mode=TransportMode.WALK,
                origin=origin,
                destination=destination,
                intermediate_stops=[],
                duration_minutes=duration_minutes,
                has_realtime=False
            )

    except Exception as e:
        logger.warning(f"Error parsing trip leg: {e}")
    return None


def _parse_trip(trip_elem: etree._Element, trip_idx: int) -> Optional[Trip]:
    """Parse a complete trip."""
    try:
        trip_id = trip_elem.findtext('.//ojp:TripId', namespaces=NAMESPACES) or f"trip_{trip_idx}"

        legs = []
        for idx, leg_elem in enumerate(trip_elem.findall('.//ojp:TripLeg', NAMESPACES)):
            leg = _parse_trip_leg(leg_elem, idx)
            if leg:
                legs.append(leg)

        if not legs:
            return None

        # Calculate trip summary
        departure = legs[0].origin.scheduled_time
        arrival = legs[-1].destination.scheduled_time
        duration = int((arrival - departure).total_seconds() / 60)
        transfers = sum(1 for leg in legs if leg.mode != TransportMode.WALK) - 1

        return Trip(
            trip_id=trip_id,
            legs=legs,
            departure_time=departure,
            arrival_time=arrival,
            duration_minutes=max(1, duration),
            num_transfers=max(0, transfers),
            has_disruptions=False,
            disruptions=[]
        )
    except Exception as e:
        logger.warning(f"Error parsing trip: {e}")
    return None


async def search_locations(query: str, limit: int = 10) -> List[Location]:
    """Search for locations by name."""
    xml_request = _build_location_request(query, limit)

    try:
        root = await _make_ojp_request(xml_request)

        locations = []
        for loc_result in root.findall('.//ojp:Location', NAMESPACES):
            location = _parse_location(loc_result)
            if location:
                locations.append(location)

        return locations
    except Exception as e:
        logger.error(f"Error searching locations: {e}")
        return []


async def search_trips(
    origin_id: str,
    destination_id: str,
    departure_time: Optional[datetime] = None,
    num_results: int = 5
) -> TripSearchResult:
    """Search for trips between two locations."""
    xml_request = _build_trip_request(origin_id, destination_id, departure_time, num_results)

    try:
        root = await _make_ojp_request(xml_request)

        trips = []
        for idx, trip_elem in enumerate(root.findall('.//ojp:TripResult', NAMESPACES)):
            trip = _parse_trip(trip_elem, idx)
            if trip:
                trips.append(trip)

        return TripSearchResult(
            trips=trips,
            search_time=datetime.utcnow()
        )
    except Exception as e:
        logger.error(f"Error searching trips: {e}")
        return TripSearchResult(trips=[], search_time=datetime.utcnow())
