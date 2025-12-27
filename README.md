# Swiss Transport Planner

A production-grade Swiss public transport web application combining timetable planning, live operations, disruptions, and heuristic delay prediction — using only official Swiss Open Transport Data (OTD) sources.

## Features

- **Route Planning**: Search routes on the SBB network using OJP (Open Journey Planner)
- **Route Overview**: Detailed information for trains, trams, buses, and funiculars including platform/track numbers
- **Live Disruptions**: Real-time disruption monitoring via SIRI-SX (refreshed every 30 seconds)
- **Delay Prediction**: Heuristic delay prediction for buses and trams using road traffic data

## Data Sources

| Feature | API | Format | Refresh |
|---------|-----|--------|---------|
| Route Planning | OJP | XML | On-demand |
| Delays | GTFS-RT | Protobuf/JSON | 1 min |
| Disruptions | SIRI-SX | XML | 30 sec |
| Traffic Situations | DATEX II | XML | 1 min |
| Traffic Lights | OCIT-C | JSON | 1 min |

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   React Frontend │────▶│  FastAPI Backend │
│   (Vite + TS)    │◀────│   (Python)       │
└─────────────────┘     └────────┬─────────┘
                                 │
     ┌───────────────────────────┼───────────────────────────┐
     │                           │                           │
     ▼                           ▼                           ▼
┌─────────┐              ┌───────────────┐           ┌────────────┐
│   OJP   │              │   SIRI-SX     │           │ DATEX II   │
│ Routing │              │ Disruptions   │           │ Traffic    │
└─────────┘              └───────────────┘           └────────────┘
```

## Prerequisites

- Docker and Docker Compose
- Swiss OTD API Key (get from [API Manager](https://api-manager.opentransportdata.swiss/))

## Local Development

### Using Docker Compose

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/swiss-transport-app.git
   cd swiss-transport-app
   ```

2. Create environment file:
   ```bash
   cp .env.example .env
   # Edit .env and add your OTD_API_KEY
   ```

3. Start the application:
   ```bash
   docker compose up
   ```

4. Access the application:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Manual Development

#### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
export OTD_API_KEY=your_key_here
uvicorn main:app --reload
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

### Location Search
```
GET /api/locations?query=zürich&limit=10
```

### Trip Planning
```
POST /api/trips
{
  "origin_id": "8503000",
  "destination_id": "8507000",
  "departure_time": "2024-01-15T08:00:00",
  "include_predictions": true
}
```

### Disruptions
```
GET /api/disruptions?limit=50
```

### Real-time Events (SSE)
```
GET /api/events
```

## Delay Prediction

The delay prediction engine uses heuristic rules based on road traffic data:

| Factor | Impact |
|--------|--------|
| Severe traffic incident | +8 min |
| Moderate traffic incident | +4 min |
| Level of Service F (severe congestion) | +6 min |
| Level of Service E | +4 min |
| Level of Service D | +2 min |
| Spillback per 100m | +1 min |
| Peak hour multiplier | 1.5x |

**Peak Hours**: 5:45-7:00 and 16:30-18:00

**Prediction Horizon**: 15 minutes (primarily for peak hours)

## Railway Deployment

### Backend Service
1. Create a new Railway project
2. Connect your GitHub repository
3. Set root directory to `backend`
4. Add environment variable: `OTD_API_KEY`
5. Railway will auto-detect the Dockerfile

### Frontend Service
1. Add a new service in the same project
2. Set root directory to `frontend`
3. Add build argument: `VITE_API_URL` = Backend URL
4. Railway will auto-detect the Dockerfile

## Assumptions & Limitations

1. **OJP Routing**: Timetable-only (no real-time in routing calculations)
2. **Vehicle Positions**: GTFS-RT on OTD does NOT provide vehicle positions, only delays
3. **Traffic Data Coverage**: Varies by region; prediction confidence reflects data availability
4. **Delay Prediction**: Heuristic-based, not ML-based; accuracy varies

## Tech Stack

- **Backend**: Python 3.11, FastAPI, httpx, lxml
- **Frontend**: React 18, TypeScript, Vite, TailwindCSS
- **Data**: OJP, GTFS-RT, SIRI-SX, DATEX II, OCIT-C
- **Deployment**: Docker, Railway

## License

MIT

## Acknowledgments

- [Swiss Open Transport Data](https://opentransportdata.swiss/)
- [SBB](https://www.sbb.ch/) for public transport data
- [FEDRO](https://www.astra.admin.ch/) for traffic data
