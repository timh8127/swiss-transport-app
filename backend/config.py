"""Configuration management for Swiss Transport App."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys for Swiss OTD
    OTD_API_KEY: str = ""

    # API Endpoints
    OJP_ENDPOINT: str = "https://api.opentransportdata.swiss/ojp2020"
    GTFS_RT_ENDPOINT: str = "https://api.opentransportdata.swiss/la/gtfs-rt"
    SIRI_SX_ENDPOINT: str = "https://api.opentransportdata.swiss/la/siri-sx-unplanned"
    TRAFFIC_LIGHTS_BASE: str = "https://api.opentransportdata.swiss/TDP/Rest_OcitC/Read/v1"
    TRAFFIC_SITUATIONS_ENDPOINT: str = "https://api.opentransportdata.swiss/TDP/Soap_Datex2/TrafficSituations/Pull"

    # App settings
    APP_NAME: str = "Swiss Transport Planner"
    DEBUG: bool = False
    CORS_ORIGINS: str = "*"

    # Cache settings (seconds)
    CACHE_TTL_ROUTES: int = 300
    CACHE_TTL_DISRUPTIONS: int = 30
    CACHE_TTL_TRAFFIC: int = 60

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
