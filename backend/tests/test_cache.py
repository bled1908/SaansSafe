import json
from datetime import timedelta

import pytest
from support import NOW, FakeDynamoClient, make_series

from saanssafe.cache import (
    SCHEMA_VERSION,
    CacheError,
    CachedSeries,
    DynamoReadingCache,
    cache_key,
    round_coordinate,
    series_from_json,
    series_to_json,
)
from saanssafe.readings import ReadingSeries


def test_cache_key_rounds_to_two_decimals():
    assert cache_key("open-meteo", 28.6139, 77.209) == "open-meteo#28.61#77.21"
    assert cache_key("open-meteo", -0.001, -0.004) == "open-meteo#0.00#0.00"  # no "-0.00"


def test_round_coordinate_normalizes_negative_zero():
    assert str(round_coordinate(-0.001)) == "0.0"


def test_series_json_round_trip_preserves_missing_values():
    series = make_series(hours=5, pm2_5=None, nh3=None)
    restored = series_from_json(series_to_json(series))
    assert restored == series
    assert restored.readings[0].pm2_5 is None


def test_empty_series_round_trip():
    empty = ReadingSeries(1.0, 2.0, "open-meteo", ())
    assert series_from_json(series_to_json(empty)) == empty


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["hours"]["pm10"].pop(),          # ragged columns
        lambda d: d.update(start=None),               # readings without a start time
        lambda d: d["hours"]["pm10"].__setitem__(0, -1),  # invalid concentration
        lambda d: d.pop("hours"),
    ],
)
def test_series_from_json_rejects_corrupt_payload(mutate):
    data = json.loads(series_to_json(make_series(hours=3)))
    mutate(data)
    with pytest.raises((ValueError, KeyError, TypeError)):
        series_from_json(json.dumps(data))


def test_put_writes_expected_item_with_ttl():
    client = FakeDynamoClient()
    cache = DynamoReadingCache(client, "AqiCache", retention=timedelta(hours=24))
    cache.put("open-meteo#28.61#77.21", CachedSeries(make_series(hours=3), NOW))
    _, kwargs = client.calls[0]
    item = kwargs["Item"]
    fetched = int(NOW.timestamp())
    assert kwargs["TableName"] == "AqiCache"
    assert item["pk"] == {"S": "open-meteo#28.61#77.21"}
    assert item["fetched_at"] == {"N": str(fetched)}
    assert item["expires_at"] == {"N": str(fetched + 86400)}
    assert item["schema_version"] == {"N": str(SCHEMA_VERSION)}
    assert json.loads(item["payload"]["S"])["source"] == "open-meteo"


def test_put_then_get_round_trip():
    client = FakeDynamoClient()
    cache = DynamoReadingCache(client, "AqiCache")
    original = CachedSeries(make_series(hours=4), NOW.replace(microsecond=0))
    cache.put("k", original)
    restored = cache.get("k")
    assert restored == CachedSeries(original.series, NOW.replace(microsecond=0))
    assert client.calls[-1] == ("get_item", {"TableName": "AqiCache", "Key": {"pk": {"S": "k"}}})


def test_get_missing_item_returns_none():
    assert DynamoReadingCache(FakeDynamoClient(), "AqiCache").get("k") is None


def test_get_other_schema_version_is_a_miss():
    client = FakeDynamoClient()
    cache = DynamoReadingCache(client, "AqiCache")
    cache.put("k", CachedSeries(make_series(hours=2), NOW))
    client.item["schema_version"] = {"N": "999"}
    assert cache.get("k") is None


def test_get_corrupt_item_raises_cache_error():
    client = FakeDynamoClient(item={"pk": {"S": "k"}, "schema_version": {"N": "1"}})
    with pytest.raises(CacheError, match="Corrupt"):
        DynamoReadingCache(client, "AqiCache").get("k")


@pytest.mark.parametrize("op", ["get", "put"])
def test_client_errors_become_cache_errors(op):
    class ThrottledError(Exception):
        pass

    cache = DynamoReadingCache(FakeDynamoClient(error=ThrottledError("slow down")), "AqiCache")
    with pytest.raises(CacheError, match="ThrottledError"):
        if op == "get":
            cache.get("k")
        else:
            cache.put("k", CachedSeries(make_series(hours=1), NOW))


def test_table_name_required():
    with pytest.raises(ValueError):
        DynamoReadingCache(FakeDynamoClient(), "")
