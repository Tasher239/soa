import json
import logging
from typing import Optional

from redis.sentinel import Sentinel

from app.core.config import settings

logger = logging.getLogger(__name__)


def _make_sentinel_client():
    sentinel = Sentinel(
        [(settings.REDIS_SENTINEL_HOST, settings.REDIS_SENTINEL_PORT)],
        socket_timeout=0.5,
    )
    return sentinel.master_for(settings.REDIS_MASTER_NAME, decode_responses=True)


class FlightCacheService:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = _make_sentinel_client()
        return self._client

    def _flight_key(self, flight_id: int) -> str:
        return f"flight:{flight_id}"

    def _search_key(self, origin: str, destination: str, date: Optional[str]) -> str:
        return f"search:{origin}:{destination}:{date or 'all'}"

    def get_flight(self, flight_id: int) -> Optional[dict]:
        try:
            client = self._get_client()
            data = client.get(self._flight_key(flight_id))
            if data:
                logger.info(f"cache hit: flight:{flight_id}")
                return json.loads(data)
            logger.info(f"cache miss: flight:{flight_id}")
            return None
        except Exception as e:
            logger.warning(f"Redis get_flight error: {e}")
            return None

    def set_flight(self, flight_id: int, data: dict, ttl: Optional[int] = None) -> None:
        try:
            client = self._get_client()
            client.setex(self._flight_key(flight_id), ttl or settings.CACHE_TTL, json.dumps(data))
        except Exception as e:
            logger.warning(f"Redis set_flight error: {e}")

    def get_search(self, origin: str, destination: str, date: Optional[str]) -> Optional[list]:
        try:
            client = self._get_client()
            key = self._search_key(origin, destination, date)
            data = client.get(key)
            if data:
                logger.info(f"cache hit: {key}")
                return json.loads(data)
            logger.info(f"cache miss: {key}")
            return None
        except Exception as e:
            logger.warning(f"Redis get_search error: {e}")
            return None

    def set_search(self, origin: str, destination: str, date: Optional[str], result: list, ttl: Optional[int] = None) -> None:
        try:
            client = self._get_client()
            key = self._search_key(origin, destination, date)
            client.setex(key, ttl or settings.CACHE_TTL, json.dumps(result))
        except Exception as e:
            logger.warning(f"Redis set_search error: {e}")

    def invalidate_flight(self, flight_id: int) -> None:
        try:
            client = self._get_client()
            client.delete(self._flight_key(flight_id))
            logger.info(f"cache invalidated: flight:{flight_id}")
        except Exception as e:
            logger.warning(f"Redis invalidate_flight error: {e}")

    def invalidate_search_by_flight(self, origin: str, destination: str) -> None:
        try:
            client = self._get_client()
            pattern = self._search_key(origin, destination, "*")
            keys = client.keys(pattern)
            if keys:
                client.delete(*keys)
                logger.info(f"cache invalidated: {len(keys)} search keys for {origin}->{destination}")
        except Exception as e:
            logger.warning(f"Redis invalidate_search error: {e}")


cache_service = FlightCacheService()
