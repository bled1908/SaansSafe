"""Provider interface and errors shared by all air-quality data sources."""

from __future__ import annotations

import math
from typing import Protocol

from saanssafe.readings import ReadingSeries


class ProviderError(Exception):
    """Base class for data-provider failures."""


class ProviderUnavailableError(ProviderError):
    """Upstream is unreachable, timed out, rate-limited, or returned a 5xx. Retry later."""


class ProviderRequestError(ProviderError):
    """Upstream rejected our request (4xx). Retrying the same request won't help."""


class ProviderResponseError(ProviderError):
    """Upstream answered, but the response can't be trusted (malformed or unexpected)."""


class AirQualityProvider(Protocol):
    name: str

    def fetch_hourly(self, latitude: float, longitude: float) -> ReadingSeries: ...


def validate_coordinates(latitude: object, longitude: object) -> tuple[float, float]:
    """Return (lat, lon) as floats, or raise ValueError for non-numeric or out-of-range values."""
    for name, value, limit in (("latitude", latitude, 90), ("longitude", longitude, 180)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a number, got {value!r}")
        if not math.isfinite(value) or not -limit <= value <= limit:
            raise ValueError(f"{name} must be within [-{limit}, {limit}], got {value!r}")
    return float(latitude), float(longitude)  # type: ignore[arg-type]
