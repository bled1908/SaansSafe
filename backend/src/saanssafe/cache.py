"""Cache of provider ReadingSeries, keyed by rounded coordinates.

DynamoDB item (table name from configuration, on-demand billing):
    pk              S  "<source>#<lat 2dp>#<lon 2dp>", e.g. "open-meteo#28.61#77.21"
    fetched_at      N  epoch seconds when the provider was called
    expires_at      N  epoch seconds; DynamoDB TTL attribute (cleanup only, not freshness)
    schema_version  N  payload format version
    payload         S  JSON-encoded ReadingSeries (see series_to_json)

Freshness decisions live in the service, based on `fetched_at`. DynamoDB's TTL
deletes items lazily, so an expired item may still be returned.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from saanssafe.aqi import Pollutant
from saanssafe.readings import HOUR, HourlyReading, ReadingSeries

SCHEMA_VERSION = 1
DEFAULT_RETENTION = timedelta(hours=24)
COORDINATE_DECIMALS = 2  # ~1 km; the same rounded point is fetched and cached


class CacheError(Exception):
    """The cache backend failed, or returned an item we can't trust."""


@dataclass(frozen=True)
class CachedSeries:
    series: ReadingSeries
    fetched_at: datetime  # UTC


class ReadingCache(Protocol):
    def get(self, key: str) -> CachedSeries | None: ...

    def put(self, key: str, cached: CachedSeries) -> None: ...


def round_coordinate(value: float) -> float:
    return round(value, COORDINATE_DECIMALS) + 0.0  # "+ 0.0" turns -0.0 into 0.0


def cache_key(source: str, latitude: float, longitude: float) -> str:
    lat, lon = round_coordinate(latitude), round_coordinate(longitude)
    return f"{source}#{lat:.{COORDINATE_DECIMALS}f}#{lon:.{COORDINATE_DECIMALS}f}"


def series_to_json(series: ReadingSeries) -> str:
    start = series.first_time
    return json.dumps(
        {
            "source": series.source,
            "latitude": series.latitude,
            "longitude": series.longitude,
            "start": None if start is None else int(start.timestamp()),
            "hours": {p.value: [r.value(p) for r in series.readings] for p in Pollutant},
        },
        separators=(",", ":"),
    )


def series_from_json(text: str) -> ReadingSeries:
    """Inverse of series_to_json. Raises ValueError/KeyError/TypeError on bad input."""
    data = json.loads(text)
    columns: dict[str, list[Any]] = data["hours"]
    lengths = {len(columns[p.value]) for p in Pollutant}
    if len(lengths) != 1:
        raise ValueError("pollutant columns have different lengths")
    count = lengths.pop()
    start = None if data["start"] is None else datetime.fromtimestamp(data["start"], UTC)
    if count and start is None:
        raise ValueError("missing start time")
    readings = tuple(
        HourlyReading(start + HOUR * i, **{p.value: columns[p.value][i] for p in Pollutant})
        for i in range(count)
    )
    return ReadingSeries(float(data["latitude"]), float(data["longitude"]), data["source"], readings)


class DynamoReadingCache:
    """ReadingCache backed by a DynamoDB table, via an injected low-level boto3 client."""

    def __init__(self, client: Any, table_name: str, retention: timedelta = DEFAULT_RETENTION):
        if not table_name:
            raise ValueError("table_name is required")
        self._client = client
        self._table = table_name
        self._retention = retention

    def get(self, key: str) -> CachedSeries | None:
        try:
            response = self._client.get_item(TableName=self._table, Key={"pk": {"S": key}})
        except Exception as err:  # botocore raises many types; all mean "cache unavailable"
            raise CacheError(f"DynamoDB get_item failed: {type(err).__name__}") from err
        item = response.get("Item")
        if not item:
            return None
        try:
            if int(item["schema_version"]["N"]) != SCHEMA_VERSION:
                return None  # written by another version: treat as a miss
            fetched_at = datetime.fromtimestamp(int(item["fetched_at"]["N"]), UTC)
            series = series_from_json(item["payload"]["S"])
        except (KeyError, TypeError, ValueError) as err:
            raise CacheError(f"Corrupt cache item {key!r}: {err}") from err
        return CachedSeries(series, fetched_at)

    def put(self, key: str, cached: CachedSeries) -> None:
        fetched = int(cached.fetched_at.timestamp())
        item = {
            "pk": {"S": key},
            "fetched_at": {"N": str(fetched)},
            "expires_at": {"N": str(fetched + int(self._retention.total_seconds()))},
            "schema_version": {"N": str(SCHEMA_VERSION)},
            "payload": {"S": series_to_json(cached.series)},
        }
        try:
            self._client.put_item(TableName=self._table, Item=item)
        except Exception as err:
            raise CacheError(f"DynamoDB put_item failed: {type(err).__name__}") from err
