"""The numbers Prometheus scrapes from /metrics."""
from prometheus_client import REGISTRY

from tests.conftest import as_


def calls(method: str, route: str, status: int) -> float:
    labels = {"method": method, "route": route, "status": str(status)}
    return REGISTRY.get_sample_value("http_requests_total", labels) or 0.0


def waiting(status: str) -> float | None:
    return REGISTRY.get_sample_value("serviceops_requests", {"status": status})


def test_metrics_are_plain_text_for_people_and_openmetrics_for_prometheus(client):
    plain = client.get("/metrics")
    assert plain.status_code == 200
    assert plain.headers["content-type"].startswith("text/plain")
    assert 'serviceops_requests{status="new"} 0.0' in plain.text

    scraped = client.get("/metrics", headers={"Accept": "application/openmetrics-text;version=1.0.0"})
    assert scraped.headers["content-type"].startswith("application/openmetrics-text")
    assert scraped.text.rstrip().endswith("# EOF")


def test_calls_are_counted_by_route_pattern_not_by_id(client):
    route = "/api/requests/{request_id}/{action}"
    before = calls("POST", route, 200)
    request_id = client.post("/api/requests", json={"title": "Monitor", "category": "hardware"}, headers=as_("asha")).json()["id"]
    client.post(f"/api/requests/{request_id}/triage", json={"priority": "low"}, headers=as_("ravi"))

    assert calls("POST", route, 200) == before + 1
    # One series for every request id would grow forever.
    assert calls("POST", f"/api/requests/{request_id}/triage", 200) == 0


def test_refused_steps_are_counted_under_their_status(client):
    route = "/api/requests/{request_id}/{action}"
    before = calls("POST", route, 403)
    request_id = client.post("/api/requests", json={"title": "Monitor", "category": "hardware"}, headers=as_("asha")).json()["id"]
    refused = client.post(f"/api/requests/{request_id}/approve", json={}, headers=as_("asha"))

    assert refused.status_code == 403
    assert calls("POST", route, 403) == before + 1


def test_unknown_paths_share_one_series(client):
    before = calls("GET", "unmatched", 404)
    client.get("/no/such/page")
    client.get("/another/missing/page")
    assert calls("GET", "unmatched", 404) == before + 2


def test_requests_by_status_come_from_the_database(client):
    assert waiting("new") == 0
    for title in ("Laptop", "VPN access"):
        client.post("/api/requests", json={"title": title, "category": "access"}, headers=as_("asha"))
    assert waiting("new") == 2
    assert waiting("done") == 0


def test_metrics_are_not_in_the_api_docs(client):
    assert "/metrics" not in client.get("/openapi.json").json()["paths"]
