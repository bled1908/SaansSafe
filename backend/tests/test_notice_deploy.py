"""Deployment configuration of the deterministic NoticeFunction (template.yaml) and its
behaviour with exactly the environment the template gives it. Fakes only: no AWS calls."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from notice_support import LAT, LON, aqi_service, full_series

from saanssafe import api, notice_api
from saanssafe.notice_api import NoticeSettings
from saanssafe.notice_facts import ParentNotice
from saanssafe.notice_service import NoticeService
from saanssafe.notice_writer import FakeNoticeWriter

BACKEND = Path(__file__).resolve().parents[1]


class _CfnLoader(yaml.SafeLoader):
    """Reads CloudFormation short-form tags (!Ref, !Sub, !GetAtt) as {"Tag": value}."""


def _tag(loader, suffix, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node)
    else:
        value = loader.construct_mapping(node)
    return {suffix: value}


_CfnLoader.add_multi_constructor("!", _tag)
TEMPLATE = yaml.load((BACKEND / "template.yaml").read_text(encoding="utf-8"), Loader=_CfnLoader)
RESOURCES = TEMPLATE["Resources"]
NOTICE = RESOURCES["NoticeFunction"]["Properties"]
API_FN = RESOURCES["ApiFunction"]["Properties"]
DYNAMO_ONLY = [
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["dynamodb:GetItem", "dynamodb:PutItem"],
                "Resource": {"GetAtt": "AqiCacheTable.Arn"},
            }
        ],
    }
]


def deployed_env():
    """NoticeFunction's environment with template parameter defaults resolved."""
    params = {name: str(p.get("Default")) for name, p in TEMPLATE["Parameters"].items()}
    env = {}
    for key, value in NOTICE["Environment"]["Variables"].items():
        if isinstance(value, dict) and "Ref" in value:
            value = "test-table" if value["Ref"] == "AqiCacheTable" else params[value["Ref"]]
        env[key] = str(value)
    return env


class MemoryCache:
    def __init__(self):
        self.entries = {}

    def get(self, key):
        return self.entries.get(key)

    def put(self, key, cached):
        self.entries[key] = cached


def deployed_service(level="Poor", writer=None, env=None):
    """NoticeService wired like notice_api.build_notice_service, with fakes for AWS/Open-Meteo."""
    settings = NoticeSettings.from_env(env or deployed_env())
    return NoticeService(
        aqi_service(full_series(level)),
        MemoryCache(),
        writer if writer is not None else notice_api.build_writer(settings),
        ai_enabled=settings.ai_enabled,
        ai_timeout_s=settings.ai_timeout_s,
        cache_for=settings.cache_for,
    )


def post(service, body):
    event = {
        "rawPath": "/notice",
        "requestContext": {"http": {"method": "POST"}},
        "body": json.dumps(body),
        "isBase64Encoded": False,
    }
    response = notice_api.handle(event, service)
    return response["statusCode"], json.loads(response["body"])


# --- template.yaml --------------------------------------------------------------------------

def test_post_notice_route_goes_to_the_notice_function():
    assert NOTICE["Events"] == {
        "Notice": {
            "Type": "HttpApi",
            "Properties": {"ApiId": {"Ref": "HttpApi"}, "Path": "/notice", "Method": "POST"},
        }
    }
    assert (NOTICE["Handler"], NOTICE["Runtime"], NOTICE["Architectures"]) == (
        "saanssafe.notice_api.handler", "python3.13", ["arm64"],
    )
    assert 10 <= NOTICE["Timeout"] < 30  # HTTP API integrations time out at 30 s
    assert "NoticeFunctionLogGroup" in RESOURCES


def test_cors_allows_post_and_keeps_get():
    cors = RESOURCES["HttpApi"]["Properties"]["CorsConfiguration"]
    assert cors["AllowMethods"] == ["GET", "POST", "OPTIONS"]
    assert cors["AllowHeaders"] == ["Content-Type"]


def test_notice_function_has_only_dynamodb_permissions_and_no_bedrock():
    assert NOTICE["Policies"] == DYNAMO_ONLY
    assert "bedrock" not in json.dumps(RESOURCES["NoticeFunction"]).lower()
    assert "Layers" not in NOTICE and "Metadata" not in RESOURCES["NoticeFunction"]


def test_notice_function_packages_no_strands():
    code = BACKEND / NOTICE["CodeUri"]
    assert not list(code.rglob("requirements*.txt"))  # nothing is pip-installed into the bundle
    assert (BACKEND / "requirements-notice.txt").exists()  # the optional AI dependency stays outside


def test_ai_wording_is_disabled_and_no_writer_is_built():
    settings = NoticeSettings.from_env(deployed_env())
    assert deployed_env()["NOTICE_AI_ENABLED"] == "false"
    assert settings.ai_enabled is False
    assert notice_api.build_writer(settings) is None


def test_existing_api_function_is_unchanged():
    assert API_FN["Handler"] == "saanssafe.api.handler"
    assert API_FN["Policies"] == DYNAMO_ONLY
    routes = {name: (e["Properties"]["Path"], e["Properties"]["Method"]) for name, e in API_FN["Events"].items()}
    assert routes == {"Health": ("/health", "GET"), "Aqi": ("/aqi", "GET"), "Forecast": ("/forecast", "GET")}
    assert "NOTICE_AI_ENABLED" not in API_FN["Environment"]["Variables"]


def test_handler_import_needs_no_strands_or_bedrock_module():
    code = (
        "import sys, saanssafe.notice_api; "
        "print(sorted(m for m in ('strands', 'pydantic', 'boto3', 'saanssafe.notice_bedrock') "
        "if m in sys.modules))"
    )
    env = {**os.environ, "PYTHONPATH": str(BACKEND / "src")}
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"


# --- Behaviour with the deployed configuration ----------------------------------------------

def test_valid_english_request_is_a_deterministic_template_notice():
    status, body = post(deployed_service(), {"lat": LAT, "lon": LON, "language": "en"})
    assert status == 200
    assert (body["generated_by"], body["model"], body["fallback_reason"]) == ("template", None, "ai_disabled")
    assert body["language"] == "en" and "AQI 249" in body["notice"]["body"]


def test_valid_hindi_request():
    status, body = post(deployed_service(), {"lat": LAT, "lon": LON, "language": "hi"})
    assert status == 200 and body["language"] == "hi" and body["generated_by"] == "template"
    assert "प्रिय अभिभावकगण" in body["notice"]["body"]


def test_optional_school_name():
    request = {"lat": LAT, "lon": LON, "language": "en", "school_name": "St. Mary’s School"}
    status, body = post(deployed_service(), request)
    assert status == 200 and body["school_name"] == "St. Mary’s School"
    assert body["notice"]["sign_off"] == "— St. Mary’s School"


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"lat": LAT, "lon": LON, "language": "fr"}, "invalid_language"),
        ({"lat": 95, "lon": LON, "language": "en"}, "invalid_coordinates"),
        ({"lat": "north", "lon": LON, "language": "en"}, "invalid_coordinates"),
        ({"lat": LAT, "lon": LON, "language": "en", "school_name": "<script>"}, "invalid_school_name"),
    ],
)
def test_invalid_requests_are_400(body, code):
    status, response = post(deployed_service(), body)
    assert (status, response["error"]["code"]) == (400, code)


def test_deterministic_notices_are_cached():
    service = deployed_service()
    first = post(service, {"lat": LAT, "lon": LON, "language": "en"})[1]
    second = post(service, {"lat": LAT, "lon": LON, "language": "en"})[1]
    assert (first["cache"], second["cache"]) == ("miss", "hit")
    assert second["notice"] == first["notice"]


def test_guard_still_protects_the_handler_if_a_writer_is_ever_enabled():
    wrong = FakeNoticeWriter(lambda facts: ParentNotice(facts.language, "t", "AQI 180, forecast", ("x",), "s"))
    service = deployed_service(writer=wrong, env={**deployed_env(), "NOTICE_AI_ENABLED": "true"})
    status, body = post(service, {"lat": LAT, "lon": LON, "language": "en"})
    assert (status, body["generated_by"], body["fallback_reason"]) == (200, "template", "validation_failed")
    assert "AQI 249" in body["notice"]["body"]


def test_aqi_and_forecast_are_unchanged_by_the_notice_function():
    def get(path):
        event = {
            "rawPath": path,
            "requestContext": {"http": {"method": "GET"}},
            "queryStringParameters": {"lat": str(LAT), "lon": str(LON)},
        }
        response = api.handle(event, aqi_service(full_series("Poor")))
        return response["statusCode"], json.loads(response["body"])

    status, body = get("/aqi")
    assert status == 200 and body == api.report_body(aqi_service(full_series("Poor")).current_aqi(LAT, LON))
    status, body = get("/forecast")
    assert status == 200 and body == api.forecast_body(aqi_service(full_series("Poor")).forecast(LAT, LON))
    assert get("/notice")[0] == 404  # ApiFunction never serves /notice
