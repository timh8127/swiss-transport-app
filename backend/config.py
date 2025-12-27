"""Configuration management for Swiss Transport App."""
import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Separate API Keys for each OTD service
    OTD_OJP_API_KEY: str = ""
    OTD_GTFSRT_API_KEY: str = ""
    OTD_SIRI_SX_API_KEY: str = ""
    OTD_TRAFFIC_SITUATIONS_API_KEY: str = ""
    OTD_TRAFFIC_LIGHTS_API_KEY: str = ""

    # API Endpoints
    OJP_ENDPOINT: str = "https://api.opentransportdata.swiss/ojp2020"
    GTFS_RT_ENDPOINT: str = "https://api.opentransportdata.swiss/la/gtfs-rt"
    SIRI_SX_ENDPOINT: str = "https://api.opentransportdata.swiss/la/siri-sx-unplanned"
    TRAFFIC_LIGHTS_BASE: str = "https://api.opentransportdata.swiss/TDP/Rest_OcitC/Read/v1"
    TRAFFIC_SITUATIONS_ENDPOINT: str = "https://api.opentransportdata.swiss/TDP/Soap_Datex2/TrafficSituations/Pull"

    # Server settings
    PORT: int = int(os.environ.get("PORT", 8000))
    HOST: str = "0.0.0.0"
    TIMEZONE: str = "Europe/Zurich"

    # App settings
    APP_NAME: str = "Swiss Transport Planner"
    DEBUG: bool = False
    CORS_ORIGINS: str = "*"

    # Timeout settings (seconds)
    HTTP_TIMEOUT: float = 10.0
    SOAP_TIMEOUT: float = 5.0  # DATEX II SOAP requests
    SSE_HEARTBEAT_INTERVAL: int = 25  # seconds

    # Cache settings (seconds)
    CACHE_TTL_ROUTES: int = 300
    CACHE_TTL_DISRUPTIONS: int = 30
    CACHE_TTL_TRAFFIC: int = 60
    CACHE_TTL_DATEX: int = 60  # DATEX II cache

    # Polling intervals (seconds)
    POLL_INTERVAL_DISRUPTIONS: int = 30
    POLL_INTERVAL_TRAFFIC: int = 60

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
